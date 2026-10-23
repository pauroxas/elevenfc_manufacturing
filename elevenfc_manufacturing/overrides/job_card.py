"""Use approved actual transfer quantities without editing original BOM/WO/Job Card requirements.

Target: ERPNext v16.52.x, Frappe v16.  Core checks continue to run via super().
Approval is per-Job Card and tied to a snapshot of planned and transferred amounts.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt
from elevenfc_manufacturing.variance import get_variance_context, approval_is_current


class JobCardMaterialVarianceMixin:
    # Approval fields are writable only through our role-checked API, not by editing Job Card.
    _approval_fields = (
        "custom_11fc_variance_approved", "custom_11fc_variance_approved_by",
        "custom_11fc_variance_approved_on", "custom_11fc_variance_reason",
        "custom_11fc_variance_snapshot",
    )

    def validate(self):
        if not self.is_new():
            saved = frappe.db.get_value("Job Card", self.name, self._approval_fields, as_dict=True)
            if saved:
                for fieldname in self._approval_fields:
                    if str(self.get(fieldname) or "") != str(saved.get(fieldname) or ""):
                        frappe.throw(_("Material variance approval fields cannot be edited directly."))
        super().validate()

    def validate_transfer_qty(self):
        # Keep the special workflows controlled by ERPNext rather than interfere with them.
        if not (
            (self.track_semi_finished_goods and self.skip_material_transfer)
            or self.finished_good
            or self.is_corrective_job_card
            or not self.items
        ):
            context = get_variance_context(self)
            if context["has_variance"] and not approval_is_current(self, context):
                frappe.throw(
                    _("Material usage differs from the Work Order plan. A user with the "
                      "11FC Material Variance Approver role must approve the variance "
                      "before starting, completing, or submitting this Job Card."),
                    title=_("Material Variance Approval Required"),
                )

        # Preserves native FG transfer coverage, quality, time log and stock restrictions.
        return super().validate_transfer_qty()

    def has_short_transferred_material(self):
        context = get_variance_context(self)
        if context["has_variance"] and approval_is_current(self, context):
            # Do not waive every material check for an entirely missing component.
            for item in context["items"]:
                if item["planned"] > 0 and item["transferred"] <= 0:
                    return True
            return False
        # With no approval, retain ERPNext's original WO-based validation.
        return super().has_short_transferred_material()
