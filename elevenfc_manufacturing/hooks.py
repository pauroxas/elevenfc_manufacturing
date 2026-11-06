app_name = "elevenfc_manufacturing"
app_title = "11FC Manufacturing"
app_publisher = "11FC"
app_description = "11FC Job Card under-transfer and zero-transfer support"
app_email = ""
app_license = "MIT"

extend_doctype_class = {
    "Job Card": ["elevenfc_manufacturing.overrides.job_card.JobCardUnderTransferMixin"],
    "Sales Invoice": ["elevenfc_manufacturing.overrides.sales_invoice.MultiProjectSalesInvoiceMixin"],
    "Stock Entry": ["elevenfc_manufacturing.overrides.stock_entry.JobCardMaterialReturnStockEntryMixin"],
}

doctype_js = {
    "Job Card": ["public/js/job_card_under_transfer.js", "public/js/job_card_material_return.js"],
}

# Stock Entry extension only handles source-linked returns; standard over-transfer
# restrictions and all unrelated Stock Entry validation remain intact.
after_install = "elevenfc_manufacturing.setup.install.setup_under_transfer_only"
after_migrate = "elevenfc_manufacturing.setup.install.setup_under_transfer_only"
