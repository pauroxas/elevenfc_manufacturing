"""11FC: permit a narrowly scoped Job Card material return before Manufacture.

Normal Stock Entry return restrictions, ledger posting, inventory validation,
and standard manufacturing accounting remain active for other entries.
"""
from elevenfc_manufacturing.api.job_card_material_return import (
    RETURN_FIELD,
    PURPOSE,
    validate_return_doc,
)


class JobCardMaterialReturnStockEntryMixin:
    def validate_work_order_status_for_return(self):
        if (
            self.get(RETURN_FIELD)
            and self.purpose == PURPOSE
            and self.is_return
            and self.job_card
        ):
            # Current 11FC workflow requires returns before Work Order completion.
            # Full source, Work Order and balance checks run in validate_return_doc.
            if self.pro_doc and self.pro_doc.docstatus == 1 and self.pro_doc.status not in (
                "Stopped", "Completed", "Closed"
            ):
                return
        return super().validate_work_order_status_for_return()

    def validate(self):
        result = super().validate()
        if self.get(RETURN_FIELD):
            validate_return_doc(self)
        return result

    def before_submit(self):
        native_before_submit = getattr(super(), "before_submit", None)
        if callable(native_before_submit):
            native_before_submit()
        if self.get(RETURN_FIELD):
            # Validate again on submission under a source-row database lock.
            # This catches concurrent draft returns and manual changes to items.
            validate_return_doc(self, lock_source=True)
