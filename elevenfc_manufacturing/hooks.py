app_name = "elevenfc_manufacturing"
app_title = "11FC Manufacturing"
app_publisher = "11FC"
app_description = "Job Card under-transfer and Stock Entry over-transfer controls"
app_email = ""
app_license = "MIT"

extend_doctype_class = {
    "Job Card": ["elevenfc_manufacturing.overrides.job_card.JobCardMaterialVarianceMixin"],
}
doctype_js = {
    "Job Card": "public/js/job_card_variance.js",
    "Stock Entry": "public/js/over_transfer.js",
}
doc_events = {
    "Stock Entry": {
        "validate": "elevenfc_manufacturing.over_transfer.validate_approval_fields",
        "before_submit": "elevenfc_manufacturing.over_transfer.before_submit",
    },
}
after_install = "elevenfc_manufacturing.setup.install.setup_material_variance"
after_migrate = "elevenfc_manufacturing.setup.install.setup_material_variance"
