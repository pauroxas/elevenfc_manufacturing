"""Allow actual Job Card raw-material transfer to differ from the Work Order BOM.

ERPNext v16.52.0 added a check in has_short_transferred_material() that
compares Job Card transfers to the original Work Order required quantities.
This mixin evaluates the Job Card's current, adjusted item requirements instead.

Other ERPNext protections are retained, including the job-level transfer
coverage check in validate_transfer_qty(), inventory and FG rules.
"""

from frappe.utils import flt


class JobCardMaterialVarianceMixin:
    def has_short_transferred_material(self):
        """Return True when a Job Card item is below its own required quantity.

        Do not compare against the original BOM/Work Order item requirement.
        Only use submitted transfers reflected in Job Card Item.transferred_qty.
        This still blocks shortages relative to Job Card requirements.
        """
        for row in self.items or []:
            if flt(row.transferred_qty, 6) < flt(row.required_qty, 6):
                return True
        return False
