import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLE = "11FC Over-Transfer Approver"

def setup_material_variance():
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)
    defs = [
        ("custom_11fc_ot_approved", "Over-Transfer Approved", "Check", None),
        ("custom_11fc_ot_approved_by", "Approved By", "Link", "User"),
        ("custom_11fc_ot_approved_on", "Approved On", "Datetime", None),
        ("custom_11fc_ot_reason", "Over-Transfer Reason", "Small Text", None),
        ("custom_11fc_ot_snapshot", "Approval Snapshot", "Long Text", None),
    ]
    rows = [{"fieldname": "custom_11fc_ot_section", "label": "11FC Over-Transfer Approval",
             "fieldtype": "Section Break", "insert_after": "remarks", "collapsible": 1}]
    previous = "custom_11fc_ot_section"
    for name, label, typ, options in defs:
        row = {"fieldname": name, "label": label, "fieldtype": typ,
               "read_only": 1, "insert_after": previous}
        if options: row["options"] = options
        if name == "custom_11fc_ot_snapshot": row["hidden"] = 1
        if typ == "Check": row["default"] = "0"
        rows.append(row)
        previous = name
    create_custom_fields({"Stock Entry": rows}, update=True)
    frappe.clear_cache(doctype="Stock Entry")
    frappe.clear_cache(doctype="Job Card")
