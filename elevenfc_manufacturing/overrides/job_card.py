"""For 11FC, a raw material shortage is not a prerequisite to completing a Job Card.

Do not mutate planned Job Card/BOM/WO quantities. Normal Job Card time logs,
completion quantities and ERPNext's other validations remain enabled.
"""
from frappe.utils import flt


class JobCardMaterialVarianceMixin:
    def has_short_transferred_material(self):
        # Under-transfer and zero-transfer are permitted.
        return False

    def validate_transfer_qty(self):
        if self.finished_good or self.is_corrective_job_card or not self.items:
            return super().validate_transfer_qty()
        # Intentionally waive ONLY the transfer-completion prerequisite.
        # Native on_submit still calls inspection, time-log, WO and quantity checks.
        return
