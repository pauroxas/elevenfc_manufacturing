"""Lightweight regression tests for the explicitly approved Job Card change.

Run inside a Frappe/ERPNext bench with:
bench --site <dev-site> run-tests --app elevenfc_manufacturing
"""
import unittest

from elevenfc_manufacturing.overrides.job_card import JobCardUnderTransferMixin


class NativeJobCard:
    def get(self, key, default=None):
        return getattr(self, key, default)

    def validate_transfer_qty(self):
        self.native_transfer_called += 1
        return "native-transfer"

    def validate_semi_finished_goods(self):
        self.native_semi_called += 1
        self.native_semi_flag_seen = self.skip_material_transfer
        return "native-semi"


class Card(JobCardUnderTransferMixin, NativeJobCard):
    def __init__(self, **kwargs):
        self.finished_good = None
        self.is_corrective_job_card = False
        self.is_subcontracted = False
        self.items = [{"item_code": "RM-1", "required_qty": 50, "transferred_qty": 0}]
        self.track_semi_finished_goods = False
        self.skip_material_transfer = 0
        self.native_transfer_called = 0
        self.native_semi_called = 0
        self.native_semi_flag_seen = None
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestUnderTransferOnly(unittest.TestCase):
    def test_regular_card_zero_transfer_not_blocked(self):
        card = Card()
        self.assertIsNone(card.validate_transfer_qty())
        self.assertEqual(card.native_transfer_called, 0)

    def test_regular_card_partial_transfer_not_blocked(self):
        card = Card(items=[{"item_code": "RM-1", "required_qty": 50, "transferred_qty": 30}])
        self.assertIsNone(card.validate_transfer_qty())
        self.assertEqual(card.native_transfer_called, 0)

    def test_other_card_types_use_native_check(self):
        for special in ("finished_good", "is_corrective_job_card", "is_subcontracted"):
            with self.subTest(special=special):
                card = Card(**{special: True})
                self.assertEqual(card.validate_transfer_qty(), "native-transfer")
                self.assertEqual(card.native_transfer_called, 1)

    def test_no_material_rows_uses_native_check(self):
        card = Card(items=[])
        self.assertEqual(card.validate_transfer_qty(), "native-transfer")

    def test_semi_fg_uses_native_checks_with_temporary_transfer_waiver(self):
        card = Card(track_semi_finished_goods=True, skip_material_transfer=0)
        self.assertEqual(card.validate_semi_finished_goods(), "native-semi")
        self.assertEqual(card.native_semi_called, 1)
        self.assertEqual(card.native_semi_flag_seen, 1)
        self.assertEqual(card.skip_material_transfer, 0)

    def test_semi_fg_native_flag_restored_on_exception(self):
        class Broken(Card):
            def validate_semi_finished_goods_native(self):
                raise RuntimeError("native failure")

        # Validate native exception behavior with a dynamically built base.
        class Throws:
            def validate_semi_finished_goods(self):
                self.skip_at_failure = self.skip_material_transfer
                raise RuntimeError("native failure")

        class ExceptionCard(JobCardUnderTransferMixin, Throws, NativeJobCard):
            pass

        card = ExceptionCard()
        card.track_semi_finished_goods = True
        card.is_subcontracted = False
        card.skip_material_transfer = 0
        with self.assertRaisesRegex(RuntimeError, "native failure"):
            card.validate_semi_finished_goods()
        self.assertEqual(card.skip_at_failure, 1)
        self.assertEqual(card.skip_material_transfer, 0)

    def test_non_semi_fg_uses_native_checks(self):
        card = Card(track_semi_finished_goods=False)
        self.assertEqual(card.validate_semi_finished_goods(), "native-semi")
        self.assertEqual(card.native_semi_flag_seen, 0)

    def test_subcontracted_semi_fg_uses_native_checks(self):
        card = Card(track_semi_finished_goods=True, is_subcontracted=True)
        self.assertEqual(card.validate_semi_finished_goods(), "native-semi")
        self.assertEqual(card.native_semi_flag_seen, 0)
