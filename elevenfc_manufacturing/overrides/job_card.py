"""Client-approved Job Card transfer policy for 11FC.

Only waive the prerequisite to transfer all required raw materials before
working on/submitting a Job Card. Material Transfer for Manufacture Stock
Entries, actual consumption, reservations and stock valuation are untouched.
"""


class JobCardUnderTransferMixin:
    def validate_transfer_qty(self):
        # Preserve ERPNext's normal behavior for specialized Job Cards.
        if (
            self.get("finished_good")
            or self.get("is_corrective_job_card")
            or self.get("is_subcontracted")
            or not self.get("items")
        ):
            return super().validate_transfer_qty()

        # The standard ERPNext method only enforces material-transfer
        # completion. For ordinary cards, both zero and partial transfers
        # are permitted. Other native validations run during on_submit.
        return None

    def validate_semi_finished_goods(self):
        # ERPNext separately checks for zero transferred_qty on semi-FG
        # Job Cards. Temporarily waive this one prerequisite, but keep
        # ALL its other native validations instead of copying them here.
        if not self.get("track_semi_finished_goods") or self.get("is_subcontracted"):
            return super().validate_semi_finished_goods()

        previous = self.skip_material_transfer
        try:
            self.skip_material_transfer = 1
            return super().validate_semi_finished_goods()
        finally:
            self.skip_material_transfer = previous


    def set_transferred_qty_in_job_card_item(self, ste_doc):
        """Calculate NET stock-UOM transfers per Job Card Item.

        ERPNext v16.52's native query includes is_return=1 quantities in its
        gross transfer sum. Returns should reduce the available material, not
        increase it. All normal over-transfer restrictions remain active.
        """
        import frappe
        from frappe import _
        from frappe.utils import flt
        from erpnext.manufacturing.doctype.job_card.job_card import JobCardOverTransferError

        item_ids = {row.get("job_card_item") for row in ste_doc.get("items")
                    if row.get("job_card_item")}
        if not item_ids:
            return

        # Only rows belonging to this Job Card can be recalculated.
        owned = frappe.get_all(
            "Job Card Item",
            filters={"name": ["in", list(item_ids)], "parent": self.name},
            fields=["name", "required_qty", "item_code"],
        )
        owned_map = {d.name: d for d in owned}
        if set(owned_map) != item_ids:
            frappe.throw(_("Stock Entry includes Job Card Item references not belonging to this Job Card."))

        rows = frappe.db.sql(
            """
            SELECT sed.job_card_item,
                SUM(CASE WHEN se.is_return = 1
                    THEN -sed.transfer_qty ELSE sed.transfer_qty END) AS qty
            FROM `tabStock Entry Detail` sed
            INNER JOIN `tabStock Entry` se ON se.name = sed.parent
            WHERE sed.job_card_item IN %(item_ids)s
              AND se.docstatus = 1
              AND se.purpose = 'Material Transfer for Manufacture'
              AND se.job_card = %(job_card)s
            GROUP BY sed.job_card_item
            """,
            {"item_ids": tuple(item_ids), "job_card": self.name},
            as_dict=True,
        )
        net_by_item = {r.job_card_item: flt(r.qty) for r in rows}
        allow_excess = frappe.db.get_single_value("Manufacturing Settings", "job_card_excess_transfer")

        for item_id in item_ids:
            net_qty = flt(net_by_item.get(item_id, 0), 6)
            if net_qty < 0:
                frappe.throw(_("Net transferred quantity cannot be negative for Job Card Item {0}.")
                             .format(item_id))

            if not allow_excess and flt(net_qty - flt(owned_map[item_id].required_qty), 6) > 0:
                frappe.throw(
                    _("Cannot transfer more than Required Qty for Item {0} against Job Card {1}")
                    .format(owned_map[item_id].item_code, self.name),
                    exc=JobCardOverTransferError,
                )
            frappe.db.set_value(
                "Job Card Item", item_id, "transferred_qty", net_qty, update_modified=False
            )

        self.set_status(update_status=True)
