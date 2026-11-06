"""Allow mixed-Project Sales Orders on a single 11FC Sales Invoice.

ERPNext v16 compares the Sales Invoice header Project against every referenced
Sales Order. That comparison is invalid when the same customer's invoice
contains orders with different Projects, even if each item is correctly
project-tagged. Only that comparison is relaxed for an eligible invoice.
"""

import frappe
from frappe.utils import cint

from erpnext.utilities.transaction_base import TransactionBase


# Mirrors SalesInvoice.validate_with_previous_doc in ERPNext v16.52, except
# the one Sales Order HEADER Project comparison. Keep the other checks.
_MULTI_PROJECT_REFERENCE_RULES = {
    "Sales Order": {
        "ref_dn_field": "sales_order",
        "compare_fields": [
            ["customer", "="],
            ["company", "="],
            ["currency", "="],
        ],
    },
    "Sales Order Item": {
        "ref_dn_field": "so_detail",
        "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
        "is_child_table": True,
        "allow_duplicate_prev_row_id": True,
    },
    "Delivery Note": {
        "ref_dn_field": "delivery_note",
        "compare_fields": [
            ["customer", "="],
            ["company", "="],
            ["project", "="],
            ["currency", "="],
        ],
    },
    "Delivery Note Item": {
        "ref_dn_field": "dn_detail",
        "compare_fields": [["item_code", "="], ["uom", "="], ["conversion_factor", "="]],
        "is_child_table": True,
        "allow_duplicate_prev_row_id": True,
    },
}


class MultiProjectSalesInvoiceMixin:
    """Relax only the parent Project match for eligible mixed-Project SOs."""

    def _mixed_so_item_projects(self):
        """Return a map of original SO Item IDs to Projects, or None.

        A mixed-Project invoice must consist entirely of items taken from two
        or more submitted Sales Orders belonging to the same customer, company
        and currency. Credit notes, POS, internal customer and Delivery Note
        item flows retain ERPNext's regular validation.
        """
        if (
            self.get("is_return")
            or self.get("is_pos")
            or self.get("is_debit_note")
            or self.get("is_internal_customer")
        ):
            return None

        rows = self.get("items") or []
        if not rows or any(
            not row.get("sales_order")
            or not row.get("so_detail")
            or row.get("delivery_note")
            or row.get("dn_detail")
            or row.get("scio_detail")
            for row in rows
        ):
            return None

        order_ids = {row.sales_order for row in rows}
        if len(order_ids) < 2:
            return None

        orders = frappe.get_all(
            "Sales Order",
            filters={"name": ["in", list(order_ids)]},
            fields=["name", "docstatus", "customer", "company", "currency", "project"],
        )
        by_order = {order.name: order for order in orders}
        if len(by_order) != len(order_ids):
            return None

        if any(
            order.docstatus != 1
            or not order.project
            or order.customer != self.get("customer")
            or order.company != self.get("company")
            or order.currency != self.get("currency")
            for order in orders
        ):
            return None

        if len({order.project for order in orders}) < 2:
            return None

        item_ids = {row.so_detail for row in rows}
        original_items = frappe.get_all(
            "Sales Order Item",
            filters={"name": ["in", list(item_ids)]},
            fields=["name", "parent", "project"],
        )
        by_item = {item.name: item for item in original_items}
        if len(by_item) != len(item_ids):
            return None

        projects = {}
        for row in rows:
            original = by_item.get(row.so_detail)
            if not original or original.parent != row.sales_order:
                return None
            projects[row.so_detail] = original.project or by_order[row.sales_order].project

        return projects

    def validate(self):
        projects = self._mixed_so_item_projects()
        if projects is not None:
            # First SO mapping may have filled the Sales Invoice header Project.
            # Leave the header empty; revenue GL entries use item-level Projects.
            self.project = None
            for item in self.get("items"):
                item.project = projects[item.so_detail]

        # All standard Sales Invoice, stock, accounting and tax checks remain.
        return super().validate()

    def validate_with_previous_doc(self):
        if self.get("project") or self._mixed_so_item_projects() is None:
            return super().validate_with_previous_doc()

        # Standard reference matching, except the incompatible SO header Project
        # comparison. Delivery Note validation is still unchanged.
        TransactionBase.validate_with_previous_doc(self, _MULTI_PROJECT_REFERENCE_RULES)

        # Preserve ERPNext's "Maintain Same Sales Rate" setting.
        if (
            cint(frappe.get_single_value("Selling Settings", "maintain_same_sales_rate"))
            and not self.is_return
            and not self.is_internal_customer
        ):
            self.validate_rate_with_reference_doc(
                [
                    ["Sales Order", "sales_order", "so_detail"],
                    ["Delivery Note", "delivery_note", "dn_detail"],
                ]
            )
