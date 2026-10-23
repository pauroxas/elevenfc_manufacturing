"""11FC cumulative over-transfer controls for Material Transfer for Manufacture."""
import hashlib
import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

ROLE = "11FC Over-Transfer Approver"
PURPOSE = "Material Transfer for Manufacture"
FIELDS = ("custom_11fc_ot_approved", "custom_11fc_ot_approved_by",
          "custom_11fc_ot_approved_on", "custom_11fc_ot_reason",
          "custom_11fc_ot_snapshot")


def num(value):
    return flt(value, 6)


def eligible(doc):
    return bool(doc.purpose == PURPOSE and doc.work_order and not doc.is_return)


def posted_transfers(wo, exclude):
    rows = frappe.db.sql("""
        SELECT se.job_card, detail.item_code,
               SUM(CASE WHEN se.is_return = 1
                        THEN -detail.transfer_qty ELSE detail.transfer_qty END) AS qty
        FROM `tabStock Entry` se JOIN `tabStock Entry Detail` detail
             ON detail.parent = se.name
        WHERE se.work_order = %s AND se.purpose = 'Material Transfer for Manufacture'
          AND se.docstatus = 1 AND se.name != %s
        GROUP BY se.job_card, detail.item_code
    """, (wo, exclude or ""), as_dict=True)
    all_wo, by_card = defaultdict(float), defaultdict(float)
    for row in rows:
        all_wo[row.item_code] += num(row.qty)
        if row.job_card:
            by_card[(row.job_card, row.item_code)] += num(row.qty)
    return all_wo, by_card


def evaluate(doc):
    if not eligible(doc):
        return {"eligible": False, "has_over_transfer": False, "excess": [],
                "rows": [], "snapshot": ""}

    wo = frappe.get_doc("Work Order", doc.work_order)
    card = frappe.get_doc("Job Card", doc.job_card) if doc.job_card else None
    if card and card.work_order != wo.name:
        frappe.throw(_("Stock Entry Job Card is linked to another Work Order."))

    wo_required = defaultdict(float)
    card_required = defaultdict(float)
    for item in wo.required_items:
        wo_required[item.item_code] += num(item.required_qty)
        if card and card.is_own_material(item) and flt(wo.qty):
            card_required[item.item_code] += num(
                flt(item.required_qty) / flt(wo.qty) * flt(card.for_quantity)
            )

    previous, previous_card = posted_transfers(wo.name, doc.name)
    proposed = defaultdict(float)
    for item in doc.items:
        if not (item.item_code and item.s_warehouse and item.t_warehouse):
            continue
        if item.s_warehouse == item.t_warehouse:
            continue
        proposed[item.item_code] += num(flt(item.qty) * flt(item.conversion_factor or 1))

    rows = []
    # Only rows transferred by THIS entry require a new over-transfer decision.
    for code, amount in sorted(proposed.items()):
        if amount <= 0:
            continue
        total = num(previous[code] + amount)
        planned = num(wo_required[code])
        card_total = num(previous_card[(doc.job_card, code)] + amount) if card else None
        card_limit = num(card_required[code]) if card else None
        over = bool(total > planned + 0.000001
                    or (card and card_total > card_limit + 0.000001))
        rows.append({"item_code": code, "planned_wo": planned,
                     "previous_wo": num(previous[code]), "proposed": num(amount),
                     "cumulative_wo": total, "planned_card": card_limit,
                     "cumulative_card": card_total, "over_transfer": over})

    snapshot_data = {
        "name": doc.name or "", "work_order": wo.name,
        "job_card": doc.job_card or "", "is_return": int(doc.is_return or 0),
        "fg_completed_qty": num(doc.fg_completed_qty),
        "rows": [{"item_code": d.item_code, "qty": num(d.qty),
                  "conversion_factor": num(d.conversion_factor),
                  "source": d.s_warehouse or "", "target": d.t_warehouse or "",
                  "original_item": d.original_item or ""} for d in doc.items],
        "evaluated": rows,
    }
    fingerprint = hashlib.sha256(
        json.dumps(snapshot_data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"eligible": True, "rows": rows,
            "excess": [row for row in rows if row["over_transfer"]],
            "has_over_transfer": any(row["over_transfer"] for row in rows),
            "snapshot": fingerprint}


def approval_is_current(doc, context):
    if not context["has_over_transfer"] or not doc.name:
        return False
    record = frappe.db.get_value("Stock Entry", doc.name, FIELDS, as_dict=True)
    return bool(record and record.custom_11fc_ot_approved
                and record.custom_11fc_ot_approved_by and record.custom_11fc_ot_reason
                and record.custom_11fc_ot_snapshot == context["snapshot"])


def validate_approval_fields(doc, method=None):
    if not eligible(doc) or not doc.name or doc.is_new():
        return
    saved = frappe.db.get_value("Stock Entry", doc.name, FIELDS, as_dict=True)
    if saved:
        for key in FIELDS:
            if str(doc.get(key) or "") != str(saved.get(key) or ""):
                frappe.throw(_("Over-transfer approval is read-only. Reload the Stock Entry."))


def before_submit(doc, method=None):
    if not eligible(doc):
        return
    # Serialize same-Work-Order submissions, then re-evaluate approval.
    frappe.db.sql("SELECT name FROM `tabWork Order` WHERE name=%s FOR UPDATE",
                  (doc.work_order,))
    context = evaluate(doc)
    if context["has_over_transfer"] and not approval_is_current(doc, context):
        descriptions = ", ".join(
            f"{row['item_code']}: planned {row['planned_wo']}, "
            f"cumulative transfer {row['cumulative_wo']}"
            for row in context["excess"]
        )
        frappe.throw(
            _("Over-transfer approval required for: {0}. An authorized approver "
              "must approve this draft Stock Entry before submission.").format(descriptions),
            title=_("11FC Over-Transfer Approval Required"))
