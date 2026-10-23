import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

APPROVER_ROLE = "11FC Material Variance Approver"


def setup_material_variance():
    """Idempotent for first install and subsequent Frappe Cloud site migrations."""
    if not frappe.db.exists("Role", APPROVER_ROLE):
        frappe.get_doc({
            "doctype": "Role", "role_name": APPROVER_ROLE, "desk_access": 1
        }).insert(ignore_permissions=True)

    create_custom_fields({
        "Job Card": [
            {
                "fieldname": "custom_11fc_variance_section",
                "label": "11FC Material Variance Approval",
                "fieldtype": "Section Break",
                "insert_after": "remarks",
                "collapsible": 1,
            },
            {
                "fieldname": "custom_11fc_variance_approved",
                "label": "Material Variance Approved",
                "fieldtype": "Check",
                "read_only": 1,
                "insert_after": "custom_11fc_variance_section",
                "default": "0",
            },
            {
                "fieldname": "custom_11fc_variance_approved_by",
                "label": "Approved By",
                "fieldtype": "Link",
                "options": "User",
                "read_only": 1,
                "insert_after": "custom_11fc_variance_approved",
            },
            {
                "fieldname": "custom_11fc_variance_approved_on",
                "label": "Approved On",
                "fieldtype": "Datetime",
                "read_only": 1,
                "insert_after": "custom_11fc_variance_approved_by",
            },
            {
                "fieldname": "custom_11fc_variance_reason",
                "label": "Material Variance Reason",
                "fieldtype": "Small Text",
                "read_only": 1,
                "insert_after": "custom_11fc_variance_approved_on",
            },
            {
                "fieldname": "custom_11fc_variance_snapshot",
                "label": "Material Variance Approval Snapshot",
                "fieldtype": "Long Text",
                "hidden": 1,
                "read_only": 1,
                "insert_after": "custom_11fc_variance_reason",
            },
        ]
    }, update=True)
    frappe.clear_cache(doctype="Job Card")
