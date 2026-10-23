"""For 11FC, a raw material shortage is not a prerequisite to completing a Job Card.

Do not mutate planned Job Card/BOM/WO quantities. Normal Job Card time logs,
completion quantities and ERPNext's other validations remain enabled.
"""
import frappe
from frappe import _, bold


class JobCardMaterialVarianceMixin:
    def validate_semi_finished_goods(self):
        """Waive only the zero-transfer prerequisite, preserving completion checks.

        ERPNext v16.52 normally also blocks Job Cards for semi-finished-goods
        production when transferred_qty is zero, independently from
        validate_transfer_qty(). Our under-transfer policy permits zero.
        """
        if not self.track_semi_finished_goods or self.is_subcontracted:
            return super().validate_semi_finished_goods()
        if self.docstatus == 1 and not (
            self.total_completed_qty or self.process_loss_qty or self.pending_qty
        ):
            frappe.throw(
                _("Job Card {0} has no completed quantity. Complete the Job Card before submitting.").format(
                    bold(self.name)
                ),
                title=_("Job Not Done Yet"),
            )

    def has_short_transferred_material(self):
        # Under-transfer and zero-transfer are permitted.
        return False

    def validate_transfer_qty(self):
        if self.finished_good or self.is_corrective_job_card or not self.items:
            return super().validate_transfer_qty()
        # Intentionally waive ONLY the transfer-completion prerequisite.
        # Native on_submit still calls inspection, time-log, WO and quantity checks.
        return
