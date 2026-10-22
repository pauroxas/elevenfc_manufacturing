app_name = "elevenfc_manufacturing"
app_title = "11FC Manufacturing"
app_publisher = "11FC"
app_description = "Job Card material variance approvals for 11FC"
app_email = ""
app_license = "MIT"

extend_doctype_class = {
    "Job Card": ["elevenfc_manufacturing.overrides.job_card.JobCardMaterialVarianceMixin"]
}

doctype_js = {
    "Job Card": "public/js/job_card_variance.js"
}

after_install = "elevenfc_manufacturing.setup.install.setup_material_variance"
after_migrate = "elevenfc_manufacturing.setup.install.setup_material_variance"
