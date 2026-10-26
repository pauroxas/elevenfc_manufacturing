app_name = "elevenfc_manufacturing"
app_title = "11FC Manufacturing"
app_publisher = "11FC"
app_description = "11FC Job Card under-transfer and zero-transfer support"
app_email = ""
app_license = "MIT"

extend_doctype_class = {
    "Job Card": ["elevenfc_manufacturing.overrides.job_card.JobCardUnderTransferMixin"],
}

doctype_js = {
    "Job Card": "public/js/job_card_under_transfer.js",
}

# Stock Entry receives NO 11FC override, validation hook or approval.
# ERPNext's native over-transfer restrictions and other stock controls apply.
after_install = "elevenfc_manufacturing.setup.install.setup_under_transfer_only"
after_migrate = "elevenfc_manufacturing.setup.install.setup_under_transfer_only"
