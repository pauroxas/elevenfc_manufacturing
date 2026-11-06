"""Unit-level guards for source-linked Job Card material returns.

These tests mock ERPNext document reads; DEV bench integration tests must
separately exercise Stock Ledger, GL, serial/batch and Work Order behavior.
"""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from elevenfc_manufacturing.api.job_card_material_return import (
    RETURN_FIELD,
    _already_returned,
    validate_return_doc,
)


def row(idx, qty, detail="SOURCE-ROW-1", item="RM-A",
        from_wh="WIP", to_wh="Stores", jc_item="JC-ITEM-1"):
    return frappe._dict(
        idx=idx,
        ste_detail=detail,
        against_stock_entry="STE-SOURCE",
        item_code=item,
        original_item=None,
        transfer_qty=qty,
        stock_uom="Kg",
        job_card_item=jc_item,
        s_warehouse=from_wh,
        t_warehouse=to_wh,
        is_finished_item=0,
    )


class DummyReturn:
    def __init__(self, rows=None):
        self.items = rows or [row(1, 5)]
        self.purpose = "Material Transfer for Manufacture"
        self.is_return = 1
        self.job_card = "JC-1"
        self.work_order = "WO-1"
        self.company = "11FC"
        self.fg_completed_qty = 0
        self.name = "NEW-RETURN"
        self.source = "STE-SOURCE"

    def get(self, key, default=None):
        if key == RETURN_FIELD:
            return self.source
        return getattr(self, key, default)


class TestJobCardMaterialReturn(TestCase):
    def setUp(self):
        self.source_row = SimpleNamespace(
            name="SOURCE-ROW-1", item_code="RM-A", original_item=None,
            transfer_qty=10, stock_uom="Kg", job_card_item="JC-ITEM-1",
            s_warehouse="Stores", t_warehouse="WIP",
        )
        self.original = SimpleNamespace(
            name="STE-SOURCE", work_order="WO-1", company="11FC",
            job_card="JC-1", items=[self.source_row],
        )
        self.patches = [
            patch(
                "elevenfc_manufacturing.api.job_card_material_return._load_source",
                return_value=(object(), object(), self.original),
            ),
            patch(
                "elevenfc_manufacturing.api.job_card_material_return._already_returned",
                return_value={"SOURCE-ROW-1": 2},
            ),
            patch(
                "elevenfc_manufacturing.api.job_card_material_return._wip_available",
                return_value={("RM-A", "WIP", None): 8},
            ),
            patch(
                "elevenfc_manufacturing.api.job_card_material_return._job_card_available",
                return_value={"JC-ITEM-1": 8},
            ),
            patch(
                "elevenfc_manufacturing.api.job_card_material_return.frappe.get_cached_value",
                return_value=0,
            ),
        ]

    def run_with_mocks(self, doc):
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        validate_return_doc(doc)

    def test_return_within_source_remaining_and_wip(self):
        self.run_with_mocks(DummyReturn())

    def test_return_exceeding_source_remaining_fails(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_with_mocks(DummyReturn([row(1, 9)]))

    def test_return_invalid_warehouse_fails(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_with_mocks(DummyReturn([row(1, 5, from_wh="Stores", to_wh="WIP")]))

    def test_return_invalid_job_card_item_fails(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_with_mocks(DummyReturn([row(1, 5, jc_item="WRONG")]))

    def test_return_aggregates_duplicates_by_source_detail(self):
        with self.assertRaises(frappe.ValidationError):
            self.run_with_mocks(DummyReturn([row(1, 5), row(2, 4)]))

    def test_manual_source_reference_cannot_exceed_wip_balance(self):
        self.patches[2] = patch(
            "elevenfc_manufacturing.api.job_card_material_return._wip_available",
            return_value={("RM-A", "WIP", None): 3},
        )
        with self.assertRaises(frappe.ValidationError):
            self.run_with_mocks(DummyReturn())

    def test_missing_source_field_keeps_native_flow(self):
        doc = DummyReturn()
        doc.source = None
        validate_return_doc(doc)
