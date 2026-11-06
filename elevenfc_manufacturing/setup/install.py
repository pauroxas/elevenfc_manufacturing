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
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "Stock Entry": [{
            "fieldname": "custom_11fc_return_against_ste",
            "label": "11FC Original Material Transfer",
            "fieldtype": "Link",
            "options": "Stock Entry",
            "insert_after": "job_card",
            "read_only": 1,
            "no_copy": 1,
            "depends_on": "eval:doc.is_return && doc.purpose === 'Material Transfer for Manufacture'",
        }]
    }, update=True)

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
