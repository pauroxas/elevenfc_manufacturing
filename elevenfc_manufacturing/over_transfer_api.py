"""User-facing authorization endpoints for cumulative over-transfers."""
import frappe
from frappe import _
from frappe.utils import now_datetime

from elevenfc_manufacturing.over_transfer import (
    ROLE, eligible, evaluate, approval_is_current,
)


def load(name):
    if not name or not frappe.db.exists("Stock Entry", name):
        frappe.throw(_("Stock Entry not found."))
    doc = frappe.get_doc("Stock Entry", name)
    doc.check_permission("read")
    return doc


def can_approve(doc):
    return bool(frappe.session.user != "Guest"
                and (frappe.session.user == "Administrator"
                     or ROLE in frappe.get_roles(frappe.session.user))
                and frappe.has_permission("Stock Entry", ptype="write", doc=doc))


def require_approver(doc):
    if not can_approve(doc):
        frappe.throw(_("The 11FC Over-Transfer Approver role and Stock Entry write access "
                       "are required."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def get_over_transfer_status(stock_entry):
    doc = load(stock_entry)
    ctx = evaluate(doc)
    return {
        "eligible": ctx["eligible"],
        "has_over_transfer": ctx["has_over_transfer"],
        "excess": ctx["excess"],
        "approval_valid": approval_is_current(doc, ctx),
        "approved_by": doc.get("custom_11fc_ot_approved_by") or "",
        "can_approve": can_approve(doc),
    }


@frappe.whitelist(methods=["POST"])
def approve_over_transfer(stock_entry, reason):
    doc = load(stock_entry)
    require_approver(doc)
    if doc.docstatus != 0:
        frappe.throw(_("Only a saved draft Stock Entry can be approved."))
    if not eligible(doc):
        frappe.throw(_("This is not a manufacturing material transfer."))
    reason = (reason or "").strip()
    if not (10 <= len(reason) <= 500):
        frappe.throw(_("Please provide a justification between 10 and 500 characters."))
    ctx = evaluate(doc)
    if not ctx["has_over_transfer"]:
        frappe.throw(_("This Stock Entry does not exceed its transfer limits."))
    frappe.db.set_value("Stock Entry", doc.name, {
        "custom_11fc_ot_approved": 1,
        "custom_11fc_ot_approved_by": frappe.session.user,
        "custom_11fc_ot_approved_on": now_datetime(),
        "custom_11fc_ot_reason": reason,
        "custom_11fc_ot_snapshot": ctx["snapshot"],
    })
    doc.add_comment("Comment", _("11FC over-transfer approved by {0}. Reason: {1}").format(
        frappe.session.user, frappe.utils.escape_html(reason)))
    return {"approved": True}


@frappe.whitelist(methods=["POST"])
def revoke_over_transfer(stock_entry):
    doc = load(stock_entry)
    require_approver(doc)
    if doc.docstatus != 0:
        frappe.throw(_("Submitted Stock Entries cannot have approval revoked."))
    frappe.db.set_value("Stock Entry", doc.name, {
        "custom_11fc_ot_approved": 0,
        "custom_11fc_ot_approved_by": None,
        "custom_11fc_ot_approved_on": None,
        "custom_11fc_ot_reason": None,
        "custom_11fc_ot_snapshot": None,
    })
    doc.add_comment("Comment", _("11FC over-transfer approval revoked by {0}").format(
        frappe.session.user))
    return {"revoked": True}
