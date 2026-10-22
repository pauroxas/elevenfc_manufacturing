app_name = "elevenfc_manufacturing"
app_title = "11FC Manufacturing"
app_publisher = "11FC"
app_description = "Job Card material variance handling for 11FC"
app_email = ""
app_license = "MIT"

# Frappe v16+ method extension. Leave ERPNext's base JobCard controller intact.
extend_doctype_class = {
    "Job Card": [
        "elevenfc_manufacturing.overrides.job_card.JobCardMaterialVarianceMixin"
    ],
}
