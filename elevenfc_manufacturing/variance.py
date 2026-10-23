"""Job Card material variance calculations and authorization snapshot helpers."""

import hashlib
import json
from collections import defaultdict

import frappe
from frappe.utils import flt


def snapshot_for(data):
    """Deterministic fingerprint; updating a transfer or FG qty invalidates approval."""
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_variance_context(doc):
    planned = defaultdict(float)
    actual = defaultdict(float)
    planned_rows = frappe.get_all(
        "Work Order Item",
        filters={"parent": doc.work_order, "parenttype": "Work Order"},
        fields=["item_code", "required_qty", "operation", "operation_row_id"],
    ) if doc.work_order else []
    wo_qty = flt(frappe.db.get_value("Work Order", doc.work_order, "qty")) if doc.work_order else 0

    if wo_qty:
        for row in planned_rows:
            if doc.is_own_material(row):
                planned[row.item_code] += flt(row.required_qty) / wo_qty * flt(doc.for_quantity)

    for row in frappe.get_all(
        "Job Card Item",
        filters={"parent": doc.name, "parenttype": "Job Card"},
        fields=["item_code", "required_qty", "transferred_qty"],
    ) if doc.name else []:
        actual[row.item_code] += flt(row.transferred_qty)

    items = []
    for item_code in sorted(set(planned) | set(actual)):
        expected = flt(planned.get(item_code, 0), 6)
        moved = flt(actual.get(item_code, 0), 6)
        items.append({
            "item_code": item_code, "planned": expected,
            "transferred": moved, "variance": flt(moved - expected, 6),
        })
    # A missing WO / invalid quantity must never be considered a zero-variance approval case.
    data = {
        "work_order": doc.work_order or "",
        "job_card": doc.name or "",
        "operation": doc.operation or "",
        "operation_row_id": int(doc.operation_row_id or 0),
        "for_quantity": flt(doc.for_quantity, 6),
        "work_order_qty": flt(wo_qty, 6),
        "items": items,
    }
    return {
        "items": items,
        "has_variance": any(item["variance"] != 0 for item in items),
        "snapshot": snapshot_for(data),
        "valid_work_order": bool(doc.work_order and wo_qty > 0 and items),
    }


def approval_is_current(doc, context):
    if not context["has_variance"] or not context["valid_work_order"]:
        return False
    record = frappe.db.get_value(
        "Job Card", doc.name,
        ["custom_11fc_variance_approved", "custom_11fc_variance_snapshot",
         "custom_11fc_variance_approved_by", "custom_11fc_variance_reason"],
        as_dict=True,
    ) if doc.name else None
    return bool(
        record and record.custom_11fc_variance_approved
        and record.custom_11fc_variance_snapshot == context["snapshot"]
        and record.custom_11fc_variance_approved_by
        and record.custom_11fc_variance_reason
    )
