"""Role-enforced approval endpoints; the client cannot set approval fields itself."""
import frappe
from frappe import _
from frappe.utils import flt, now_datetime
from elevenfc_manufacturing.setup.install import APPROVER_ROLE
from elevenfc_manufacturing.variance import get_variance_context, approval_is_current

def _load_job_card(job_card):
    if not job_card or not frappe.db.exists("Job Card", job_card):
        frappe.throw(_("Job Card not found."))
    doc = frappe.get_doc("Job Card", job_card)
    doc.check_permission("read")
    return doc

def _check_approver(doc):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login is required."), frappe.PermissionError)
    allowed = (frappe.session.user == "Administrator" or
               APPROVER_ROLE in frappe.get_roles(frappe.session.user) or
               "System Manager" in frappe.get_roles(frappe.session.user))
    if not allowed:
        frappe.throw(_("Only an authorized manufacturing variance approver can perform this action."),
                     frappe.PermissionError)
    doc.check_permission("write")

@frappe.whitelist(methods=["GET"])
def get_material_variance_status(job_card):
    doc = _load_job_card(job_card)
    ctx = get_variance_context(doc)
    return {
        "items": ctx["items"], "has_variance": ctx["has_variance"],
        "approval_valid": approval_is_current(doc, ctx),
        "can_approve": (
            frappe.session.user == "Administrator" or
            "System Manager" in frappe.get_roles(frappe.session.user) or
            APPROVER_ROLE in frappe.get_roles(frappe.session.user)
        ) and frappe.has_permission("Job Card", "write", doc=doc),
        "approved_by": doc.get("custom_11fc_variance_approved_by") or "",
        "approved_on": str(doc.get("custom_11fc_variance_approved_on") or ""),
        "reason": doc.get("custom_11fc_variance_reason") or "",
    }

@frappe.whitelist(methods=["POST"])
def approve_material_variance(job_card, reason):
    doc = _load_job_card(job_card)
    _check_approver(doc)
    if doc.docstatus != 0:
        frappe.throw(_("Only draft Job Cards can receive variance approval."))
    reason = (reason or "").strip()
    if len(reason) < 10 or len(reason) > 500:
        frappe.throw(_("Enter a variance justification between 10 and 500 characters."))
    ctx = get_variance_context(doc)
    if not ctx["valid_work_order"] or not ctx["has_variance"]:
        frappe.throw(_("No Work Order material variance exists to approve."))
    if flt(doc.transferred_qty, 6) < flt(doc.for_quantity, 6):
        frappe.throw(_("The submitted material transfers must cover the Job Card FG quantity."))
    if not frappe.db.exists("Stock Entry", {
        "job_card": job_card, "docstatus": 1,
        "purpose": "Material Transfer for Manufacture",
    }):
        frappe.throw(_("A submitted Material Transfer for Manufacture Stock Entry is required."))
    for item in ctx["items"]:
        if item["planned"] > 0 and item["transferred"] <= 0:
            frappe.throw(_("Cannot approve a Job Card when a required component has no transferred quantity: {0}").format(item["item_code"]))
    frappe.db.set_value("Job Card", job_card, {
        "custom_11fc_variance_approved": 1,
        "custom_11fc_variance_approved_by": frappe.session.user,
        "custom_11fc_variance_approved_on": now_datetime(),
        "custom_11fc_variance_reason": reason,
        "custom_11fc_variance_snapshot": ctx["snapshot"],
    })
    doc.add_comment("Comment", _("11FC material variance approved by {0}. Reason: {1}").format(
        frappe.session.user, frappe.utils.escape_html(reason)
    ))
    return {"approved": True}

@frappe.whitelist(methods=["POST"])
def revoke_material_variance(job_card):
    doc = _load_job_card(job_card)
    _check_approver(doc)
    if doc.docstatus != 0:
        frappe.throw(_("Only draft Job Cards can have approval revoked."))
    frappe.db.set_value("Job Card", job_card, {
        "custom_11fc_variance_approved": 0,
        "custom_11fc_variance_approved_by": None,
        "custom_11fc_variance_approved_on": None,
        "custom_11fc_variance_reason": None,
        "custom_11fc_variance_snapshot": None,
    })
    doc.add_comment("Comment", _("11FC material variance approval revoked by {0}").format(frappe.session.user))
    return {"revoked": True}
