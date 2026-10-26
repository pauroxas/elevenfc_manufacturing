"""Keep legacy approval history but hide obsolete approval UI.

v0.3.1 creates no over-transfer approval roles/fields and leaves all
Stock Entry validation to ERPNext.
"""
import frappe

LEGACY_FIELDS = {
    "Job Card": (
        "custom_11fc_variance_section",
        "custom_11fc_variance_approved",
        "custom_11fc_variance_approved_by",
        "custom_11fc_variance_approved_on",
        "custom_11fc_variance_reason",
        "custom_11fc_variance_snapshot",
    ),
    "Stock Entry": (
        "custom_11fc_ot_section",
        "custom_11fc_ot_approved",
        "custom_11fc_ot_approved_by",
        "custom_11fc_ot_approved_on",
        "custom_11fc_ot_reason",
        "custom_11fc_ot_snapshot",
    ),
}


def setup_under_transfer_only():
    # Hidden, not deleted: existing approval records remain auditable.
    for doctype, fieldnames in LEGACY_FIELDS.items():
        changed = False
        for fieldname in fieldnames:
            name = frappe.db.get_value(
                "Custom Field", {"dt": doctype, "fieldname": fieldname}, "name"
            )
            if name and not frappe.db.get_value("Custom Field", name, "hidden"):
                frappe.db.set_value(
                    "Custom Field", name, "hidden", 1, update_modified=False
                )
                changed = True
        if changed:
            frappe.clear_cache(doctype=doctype)
