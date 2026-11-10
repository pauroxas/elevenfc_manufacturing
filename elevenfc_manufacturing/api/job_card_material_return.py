"""11FC Job Card -> original Material Transfer for Manufacture -> draft return.

The original transfer and its row references are mandatory. All quantities are
in Stock UOM. Standard Stock Entry submission/ledger validation remains active.
"""
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.stock.doctype.batch.batch import get_batch_qty
from erpnext.stock.doctype.stock_entry.stock_entry import get_available_materials


RETURN_FIELD = "custom_11fc_return_against_ste"
PURPOSE = "Material Transfer for Manufacture"


def _load_job_card(job_card):
    jc = frappe.get_doc("Job Card", job_card)
    jc.check_permission("read")
    if jc.docstatus == 2 or not jc.work_order or jc.is_subcontracted:
        frappe.throw(_("Returns are not available for this Job Card."))
    wo = frappe.get_doc("Work Order", jc.work_order)
    wo.check_permission("read")
    if wo.docstatus != 1 or wo.status == "Stopped":
        frappe.throw(_("Work Order must be submitted and not stopped."))
    return jc, wo


def _load_source(job_card, original_entry):
    jc, wo = _load_job_card(job_card)
    original = frappe.get_doc("Stock Entry", original_entry)
    original.check_permission("read")
    if (
        original.docstatus != 1
        or original.purpose != PURPOSE
        or cint(original.is_return)
        or original.job_card != jc.name
        or original.work_order != wo.name
        or original.company != wo.company
    ):
        frappe.throw(_("Select a submitted, non-return material transfer for this Job Card."))
    return jc, wo, original


def _already_returned(source_name, exclude_stock_entry=None):
    """Only submitted returns against the exact original Stock Entry row count."""
    rows = frappe.db.sql(
        """
        SELECT sed.ste_detail, SUM(sed.transfer_qty) AS qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE sed.against_stock_entry = %s
          AND se.docstatus = 1
          AND se.purpose = %s
          AND se.is_return = 1
          AND (%s IS NULL OR se.name != %s)
        GROUP BY sed.ste_detail
        """,
        (source_name, PURPOSE, exclude_stock_entry, exclude_stock_entry),
        as_dict=True,
    )
    return {d.ste_detail: flt(d.qty) for d in rows}



def _row_batch_quantities(row):
    """Read actual batch identities on a source/return row.

    An original material transfer usually has an outward Serial and Batch
    Bundle. Older transfers can have only batch_no. Never silently invent a
    batch if the associated bundle has no valid batch entries.
    """
    if row.get("serial_and_batch_bundle"):
        entries = frappe.get_all(
            "Serial and Batch Entry",
            filters={"parent": row.serial_and_batch_bundle},
            fields=["batch_no", "qty"],
        )
        if not entries or any(not entry.batch_no for entry in entries):
            frappe.throw(_("Batch details are missing or invalid in bundle {0}.").format(
                row.serial_and_batch_bundle
            ))
        result = defaultdict(float)
        for entry in entries:
            result[entry.batch_no] += abs(flt(entry.qty))
        if row.get("batch_no") and set(result) != {row.batch_no}:
            frappe.throw(_("Batch field and Serial and Batch Bundle disagree for item {0}.").format(
                row.item_code
            ))
        return dict(result)
    if row.get("batch_no"):
        return {row.batch_no: flt(row.transfer_qty)}
    return {}


def _already_returned_by_batch(source_name, exclude_stock_entry=None):
    """Track submitted returns by ORIGINAL transfer row AND physical batch."""
    rows = frappe.db.sql(
        """
        SELECT sed.ste_detail, sed.batch_no, sed.serial_and_batch_bundle,
               sed.transfer_qty, sed.item_code
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE sed.against_stock_entry = %s
          AND se.docstatus = 1
          AND se.purpose = %s
          AND se.is_return = 1
          AND (%s IS NULL OR se.name != %s)
        """,
        (source_name, PURPOSE, exclude_stock_entry, exclude_stock_entry),
        as_dict=True,
    )
    returned = defaultdict(float)
    for row in rows:
        for batch_no, qty in _row_batch_quantities(row).items():
            returned[(row.ste_detail, batch_no)] += qty
    return returned


def _batch_qty_available(item_code, warehouse, batch_no):
    """Current available physical WIP stock for this specific batch."""
    return max(0, flt(get_batch_qty(
        batch_no=batch_no, item_code=item_code, warehouse=warehouse
    )))


def _job_card_available(job_card):
    """Net transferred minus material consumed per Job Card Item."""
    rows = frappe.db.sql(
        """
        SELECT sed.job_card_item,
            SUM(
                CASE
                    WHEN se.purpose = %s AND se.is_return = 0 THEN sed.transfer_qty
                    WHEN se.purpose = %s AND se.is_return = 1 THEN -sed.transfer_qty
                    WHEN se.purpose IN ('Manufacture', 'Material Consumption for Manufacture')
                         AND sed.s_warehouse IS NOT NULL THEN -sed.transfer_qty
                    ELSE 0
                END
            ) AS qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.docstatus = 1
          AND se.job_card = %s
          AND sed.job_card_item IS NOT NULL
          AND sed.job_card_item != ''
          AND se.purpose IN (%s, 'Manufacture', 'Material Consumption for Manufacture')
        GROUP BY sed.job_card_item
        """,
        (PURPOSE, PURPOSE, job_card, PURPOSE),
        as_dict=True,
    )
    return {d.job_card_item: max(0, flt(d.qty)) for d in rows}


def _wip_available(work_order):
    """ERPNext's native availability is net of returns AND manufacturing usage."""
    available = get_available_materials(work_order)
    return {
        key: max(flt(data.qty), 0)
        for key, data in available.items()
    }


def _returnable_rows(source):
    returned = _already_returned(source.name)
    wip = _wip_available(source.work_order)
    jc_available = _job_card_available(source.job_card)
    returned_batches = None
    batch_in_wip = {}
    result = []

    for row in source.items:
        if not row.s_warehouse or not row.t_warehouse or not row.job_card_item or row.is_finished_item:
            continue

        actual_jc_item = frappe.db.get_value(
            "Job Card Item", row.job_card_item,
            ["parent", "item_code"], as_dict=True,
        )
        if (
            not actual_jc_item
            or actual_jc_item.parent != source.job_card
            or actual_jc_item.item_code != (row.original_item or row.item_code)
        ):
            continue

        # Serial-only and serial+batch items require serial identity handling;
        # this enhancement deliberately supports BATCH ONLY (e.g. 11FC inks).
        if frappe.get_cached_value("Item", row.item_code, "has_serial_no"):
            continue
        has_batch = bool(frappe.get_cached_value("Item", row.item_code, "has_batch_no"))

        original_left = max(0, flt(row.transfer_qty) - returned.get(row.name, 0))
        wip_key = (row.item_code, row.t_warehouse, row.original_item or None)
        wip_left = wip.get(wip_key, 0)
        jc_left = jc_available.get(row.job_card_item, 0)

        batch_quantities = {None: flt(row.transfer_qty)}
        if has_batch:
            batch_quantities = _row_batch_quantities(row)
            if not batch_quantities:
                continue
            if returned_batches is None:
                returned_batches = _already_returned_by_batch(source.name)

        for batch_no, batch_original_qty in batch_quantities.items():
            remaining = original_left
            if batch_no:
                remaining = min(
                    remaining,
                    max(0, batch_original_qty - returned_batches.get((row.name, batch_no), 0)),
                )
                key = (row.item_code, row.t_warehouse, batch_no)
                if key not in batch_in_wip:
                    batch_in_wip[key] = _batch_qty_available(*key)
                remaining = min(remaining, batch_in_wip[key])

            maximum = min(remaining, wip_left, jc_left)
            if flt(maximum, 6) <= 0:
                continue

            result.append({
                "source_detail": row.name,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "stock_uom": row.stock_uom,
                "batch_no": batch_no,
                "from_warehouse": row.t_warehouse,
                "to_warehouse": row.s_warehouse,
                "original_qty": flt(batch_original_qty),
                "already_returned": (
                    returned_batches.get((row.name, batch_no), 0) if batch_no else returned.get(row.name, 0)
                ),
                "maximum_qty": flt(maximum, 6),
                "original_item": row.original_item,
                "job_card_item": row.job_card_item,
                "wip_key": wip_key,
            })

    return result

@frappe.whitelist()
def list_original_transfers(job_card):
    """List only original transfers that have any returnable quantities."""
    _load_job_card(job_card)
    if not frappe.has_permission("Stock Entry", "create"):
        frappe.throw(_("Not permitted to create Stock Entries."), frappe.PermissionError)

    candidates = frappe.get_list(
        "Stock Entry",
        filters={"job_card": job_card, "purpose": PURPOSE, "is_return": 0, "docstatus": 1},
        fields=["name", "posting_date"],
        order_by="posting_date desc, creation desc",
        limit_page_length=200,
    )
    result = []
    for candidate in candidates:
        _jc, _wo, original = _load_source(job_card, candidate.name)
        if _returnable_rows(original):
            result.append({"name": original.name, "posting_date": str(candidate.posting_date or "")})
    return result


@frappe.whitelist()
def get_returnable_rows(job_card, original_entry):
    """Return quantities permitted for each source Stock Entry Detail row."""
    _jc, _wo, source = _load_source(job_card, original_entry)
    return [{key: value for key, value in row.items() if key != "wip_key"}
            for row in _returnable_rows(source)]


def validate_return_doc(doc, lock_source=False):
    """Called during draft validation AND submit for linked 11FC returns."""
    original_name = doc.get(RETURN_FIELD)
    if not original_name:
        return

    if doc.purpose != PURPOSE or not cint(doc.is_return):
        frappe.throw(_("11FC returns must be Material Transfer for Manufacture with Is Return enabled."))
    if not doc.job_card or not doc.work_order or doc.fg_completed_qty:
        frappe.throw(_("Return must reference a Job Card and Work Order, with zero completed quantity."))

    if lock_source:
        # Serialize submissions against the same original transfer; held until
        # the Frappe request's transaction commits to avoid double returns.
        frappe.db.sql("SELECT name FROM `tabStock Entry` WHERE name = %s FOR UPDATE", original_name)

    _jc, _wo, original = _load_source(doc.job_card, original_name)
    if doc.work_order != original.work_order or doc.company != original.company:
        frappe.throw(_("Work Order or Company does not match the original transfer."))

    originals = {row.name: row for row in original.items}
    returned = _already_returned(original_name, exclude_stock_entry=doc.name)
    wip = _wip_available(original.work_order)
    jc_available = _job_card_available(original.job_card)
    requested_by_wip = defaultdict(float)
    requested_by_jc = defaultdict(float)
    requested_by_detail = defaultdict(float)
    requested_by_detail_batch = defaultdict(float)
    requested_by_batch_wip = defaultdict(float)
    original_batch_quantities = {}
    returned_batches = None

    if not doc.items:
        frappe.throw(_("Select at least one raw material to return."))

    for row in doc.items:
        original_row = originals.get(row.ste_detail)
        if (
            not original_row
            or row.against_stock_entry != original_name
            or not original_row.s_warehouse
            or not original_row.t_warehouse
            or not original_row.job_card_item
            or row.job_card_item != original_row.job_card_item
            or row.item_code != original_row.item_code
            or (row.original_item or None) != (original_row.original_item or None)
            or row.s_warehouse != original_row.t_warehouse
            or row.t_warehouse != original_row.s_warehouse
            or cint(row.is_finished_item)
            or flt(row.transfer_qty, 6) <= 0
        ):
            frappe.throw(_("Return row {0} does not match its original transfer line.").format(row.idx))

        if row.stock_uom != original_row.stock_uom:
            frappe.throw(_("Return row {0}: Stock UOM must match original.").format(row.idx))

        if frappe.get_cached_value("Item", row.item_code, "has_serial_no"):
            frappe.throw(_("Serial-numbered items are not supported by this Job Card return workflow."))

        if frappe.get_cached_value("Item", row.item_code, "has_batch_no"):
            if row.ste_detail not in original_batch_quantities:
                original_batch_quantities[row.ste_detail] = _row_batch_quantities(original_row)
            source_batches = original_batch_quantities[row.ste_detail]
            returned_row_batches = _row_batch_quantities(row)
            if len(returned_row_batches) != 1:
                frappe.throw(_("Return row {0} must specify exactly one original batch.").format(row.idx))
            batch_no, batch_qty = next(iter(returned_row_batches.items()))
            if (
                batch_no not in source_batches
                or flt(batch_qty - row.transfer_qty, 6) != 0
            ):
                frappe.throw(_("Return row {0} has a batch or quantity not present in its original transfer.").format(row.idx))
            if returned_batches is None:
                returned_batches = _already_returned_by_batch(original_name, exclude_stock_entry=doc.name)
            requested_by_detail_batch[(row.ste_detail, batch_no)] += flt(row.transfer_qty)
            requested_by_batch_wip[(row.item_code, row.s_warehouse, batch_no)] += flt(row.transfer_qty)
        elif row.get("serial_and_batch_bundle") or row.get("batch_no"):
            frappe.throw(_("Return row {0} uses an unexpected batch reference.").format(row.idx))

        requested_by_detail[row.ste_detail] += flt(row.transfer_qty)
        key = (row.item_code, row.s_warehouse, row.original_item or None)
        requested_by_wip[key] += flt(row.transfer_qty)
        requested_by_jc[row.job_card_item] += flt(row.transfer_qty)

    for detail_name, qty in requested_by_detail.items():
        original_qty = flt(originals[detail_name].transfer_qty)
        available = original_qty - returned.get(detail_name, 0)
        if flt(qty - available, 6) > 0:
            frappe.throw(
                _("Original transfer line {0} has only {1} remaining to return.").format(
                    detail_name, max(0, available)
                )
            )

    for (detail_name, batch_no), qty in requested_by_detail_batch.items():
        available = (
            original_batch_quantities[detail_name][batch_no]
            - returned_batches.get((detail_name, batch_no), 0)
        )
        if flt(qty - available, 6) > 0:
            frappe.throw(_("Original transfer line {0}, Batch {1}, has only {2} remaining to return.").format(
                detail_name, batch_no, max(0, available)
            ))

    for (item_code, warehouse, batch_no), qty in requested_by_batch_wip.items():
        if flt(qty - _batch_qty_available(item_code, warehouse, batch_no), 6) > 0:
            frappe.throw(_("Insufficient available stock of Batch {0} for {1} in {2}.").format(
                batch_no, item_code, warehouse
            ))

    for key, qty in requested_by_wip.items():
        if flt(qty - wip.get(key, 0), 6) > 0:
            frappe.throw(
                _("Insufficient unconsumed WIP material for {0} in {1}.").format(key[0], key[1])
            )

    for job_item, qty in requested_by_jc.items():
        if flt(qty - jc_available.get(job_item, 0), 6) > 0:
            frappe.throw(
                _("Job Card Item {0} has insufficient unconsumed transferred quantity.").format(job_item)
            )


@frappe.whitelist()
def create_draft_return(job_card, original_entry, quantities):
    """Create a draft only; user must review batch/serials and submit in UI."""
    if not frappe.has_permission("Stock Entry", "create"):
        frappe.throw(_("Not permitted to create Stock Entries."), frappe.PermissionError)

    jc, wo, source = _load_source(job_card, original_entry)
    quantities = frappe.parse_json(quantities)
    if not isinstance(quantities, list) or len(quantities) > 100:
        frappe.throw(_("Submit return quantities as a list of source rows."))

    permitted = {
        (d["source_detail"], d.get("batch_no") or None): d
        for d in _returnable_rows(source)
    }
    requested = defaultdict(float)
    for entry in quantities:
        if not isinstance(entry, dict):
            frappe.throw(_("Invalid return quantity row."))
        detail_name = entry.get("source_detail")
        batch_no = entry.get("batch_no") or None
        qty = flt(entry.get("qty"))
        if (detail_name, batch_no) not in permitted or qty <= 0:
            frappe.throw(_("Invalid return quantity or batch for original row {0}.").format(detail_name))
        requested[(detail_name, batch_no)] += qty

    if not requested:
        frappe.throw(_("Enter at least one return quantity."))

    doc = frappe.new_doc("Stock Entry")
    doc.company = source.company
    doc.purpose = PURPOSE
    doc.is_return = 1
    doc.work_order = wo.name
    doc.job_card = jc.name
    doc.from_bom = 1
    doc.bom_no = source.bom_no or wo.bom_no
    doc.fg_completed_qty = 0
    doc.project = source.project
    doc.set(RETURN_FIELD, source.name)
    doc.set_stock_entry_type()

    source_rows = {row.name: row for row in source.items}
    for (detail_name, batch_no), qty in requested.items():
        row = source_rows[detail_name]
        if flt(qty - permitted[(detail_name, batch_no)]["maximum_qty"], 6) > 0:
            frappe.throw(_("Return exceeds the available quantity for {0}, Batch {1}.").format(
                row.item_code, batch_no or "N/A"
            ))

        doc.append("items", {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "description": row.description,
            "qty": qty,
            "uom": row.stock_uom,
            "stock_uom": row.stock_uom,
            "conversion_factor": 1,
            "batch_no": batch_no,
            "use_serial_batch_fields": 1 if batch_no else 0,
            "s_warehouse": row.t_warehouse,
            "t_warehouse": row.s_warehouse,
            "original_item": row.original_item,
            "job_card_item": row.job_card_item,
            "against_stock_entry": source.name,
            "ste_detail": row.name,
            "project": row.project,
            "cost_center": row.cost_center,
        })

    # Permission check and ALL native validations execute on insert.
    doc.insert()
    return {"name": doc.name}


@frappe.whitelist()
def get_job_card_returnable_rows(job_card):
    """Return eligible material rows from ALL submitted transfers for a Job Card.

    The user does not have to select a source Stock Entry. Each row carries its
    original document and line IDs internally for creation/traceability.
    """
    transfers = list_original_transfers(job_card)
    result = []
    for source in transfers:
        rows = get_returnable_rows(job_card, source["name"])
        for row in rows:
            row["original_entry"] = source["name"]
            result.append(row)
    return result


@frappe.whitelist()
def create_draft_returns(job_card, quantities):
    """Make one draft Stock Entry per original source automatically.

    One return Stock Entry can only have a single original source in our
    first release. If rows were selected across several sources, this method
    creates separate drafts in one request. All drafts stay unsubmitted.
    """
    _jc, _wo = _load_job_card(job_card)
    if not frappe.has_permission("Stock Entry", "create"):
        frappe.throw(_("Not permitted to create Stock Entries."), frappe.PermissionError)

    quantities = frappe.parse_json(quantities)
    if not isinstance(quantities, list) or not quantities or len(quantities) > 100:
        frappe.throw(_("Enter return quantities for at least one eligible material row."))

    available_rows = get_job_card_returnable_rows(job_card)
    indexed = {
        (d["original_entry"], d["source_detail"], d.get("batch_no") or None): d
        for d in available_rows
    }
    grouped = defaultdict(lambda: defaultdict(float))
    totals_wip = defaultdict(float)
    totals_job_item = defaultdict(float)
    original_rows = defaultdict(float)
    totals_by_batch = defaultdict(float)

    for entry in quantities:
        if not isinstance(entry, dict):
            frappe.throw(_("Invalid return material row."))

        source = entry.get("original_entry")
        detail = entry.get("source_detail")
        batch_no = entry.get("batch_no") or None
        qty = flt(entry.get("qty"))
        key = (source, detail, batch_no)
        if key not in indexed or qty <= 0:
            frappe.throw(_("An invalid or unavailable material row was selected."))

        info = indexed[key]
        original_rows[key] += qty
        grouped[source][(detail, batch_no)] += qty
        wip_key = (info["item_code"], info["from_warehouse"], info["original_item"] or None)
        totals_wip[wip_key] += qty
        totals_job_item[info["job_card_item"]] += qty
        if batch_no:
            totals_by_batch[(info["item_code"], info["from_warehouse"], batch_no)] += qty

    # Each original line, WIP material and Job Card Item must be checked
    # cumulatively across ALL selected rows/sources.
    for key, qty in original_rows.items():
        if flt(qty - indexed[key]["maximum_qty"], 6) > 0:
            frappe.throw(_("Return quantity exceeds the available amount for an original transfer line."))

    wip = _wip_available(_wo.name)
    by_jc = _job_card_available(job_card)
    for (item_code, warehouse, batch_no), qty in totals_by_batch.items():
        if flt(qty - _batch_qty_available(item_code, warehouse, batch_no), 6) > 0:
            frappe.throw(_("Total selected return quantity exceeds available WIP stock for Batch {0}.").format(
                batch_no
            ))
    for key, qty in totals_wip.items():
        if flt(qty - wip.get(key, 0), 6) > 0:
            frappe.throw(_("Total selected return quantity exceeds unconsumed WIP material."))
    for key, qty in totals_job_item.items():
        if flt(qty - by_jc.get(key, 0), 6) > 0:
            frappe.throw(_("Total selected return quantity exceeds the Job Card's eligible material."))

    created = []
    for source_name, detail_quantities in grouped.items():
        response = create_draft_return(
            job_card, source_name,
            [
                {"source_detail": detail, "batch_no": batch_no, "qty": qty}
                for (detail, batch_no), qty in detail_quantities.items()
            ],
        )
        created.append(response["name"])
    return {"names": created}
