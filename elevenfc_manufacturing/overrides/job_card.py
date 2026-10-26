"""Client-approved Job Card transfer policy for 11FC.

Only waive the prerequisite to transfer all required raw materials before
working on/submitting a Job Card. Material Transfer for Manufacture Stock
Entries, actual consumption, reservations and stock valuation are untouched.
"""


class JobCardUnderTransferMixin:
    def validate_transfer_qty(self):
        # Preserve ERPNext's normal behavior for specialized Job Cards.
        if (
            self.get("finished_good")
            or self.get("is_corrective_job_card")
            or self.get("is_subcontracted")
            or not self.get("items")
        ):
            return super().validate_transfer_qty()

        # The standard ERPNext method only enforces material-transfer
        # completion. For ordinary cards, both zero and partial transfers
        # are permitted. Other native validations run during on_submit.
        return None

    def validate_semi_finished_goods(self):
        # ERPNext separately checks for zero transferred_qty on semi-FG
        # Job Cards. Temporarily waive this one prerequisite, but keep
        # ALL its other native validations instead of copying them here.
        if not self.get("track_semi_finished_goods") or self.get("is_subcontracted"):
            return super().validate_semi_finished_goods()

        previous = self.skip_material_transfer
        try:
            self.skip_material_transfer = 1
            return super().validate_semi_finished_goods()
        finally:
            self.skip_material_transfer = previous
