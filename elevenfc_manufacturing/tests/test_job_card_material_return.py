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


    def test_auto_discovery_combines_rows_from_multiple_original_transfers(self):
        from elevenfc_manufacturing.api.job_card_material_return import get_job_card_returnable_rows

        with patch(
            "elevenfc_manufacturing.api.job_card_material_return.list_original_transfers",
            return_value=[{"name": "STE-A"}, {"name": "STE-B"}],
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return.get_returnable_rows",
            side_effect=lambda _job_card, source: [
                {"source_detail": "LINE-" + source, "item_code": "RM-A"}
            ],
        ):
            results = get_job_card_returnable_rows("JC-1")

        self.assertEqual(len(results), 2)
        self.assertEqual(
            [(r["original_entry"], r["source_detail"]) for r in results],
            [("STE-A", "LINE-STE-A"), ("STE-B", "LINE-STE-B")],
        )

    def test_auto_creation_keeps_one_draft_per_source(self):
        from elevenfc_manufacturing.api.job_card_material_return import create_draft_returns

        rows = [
            {"original_entry": "STE-A", "source_detail": "LINE-A",
             "item_code": "RM-A", "from_warehouse": "WIP",
             "original_item": None, "job_card_item": "JC-ITEM-1", "maximum_qty": 6},
            {"original_entry": "STE-B", "source_detail": "LINE-B",
             "item_code": "RM-A", "from_warehouse": "WIP",
             "original_item": None, "job_card_item": "JC-ITEM-1", "maximum_qty": 4},
        ]
        quantities = [
            {"original_entry": "STE-A", "source_detail": "LINE-A", "qty": 3},
            {"original_entry": "STE-B", "source_detail": "LINE-B", "qty": 2},
        ]
        calls = []

        def create_draft(_jc, source, parts):
            calls.append((source, parts))
            return {"name": "DRAFT-" + source}

        with patch(
            "elevenfc_manufacturing.api.job_card_material_return._load_job_card",
            return_value=(object(), SimpleNamespace(name="WO-1")),
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return.frappe.has_permission",
            return_value=True,
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return.get_job_card_returnable_rows",
            return_value=rows,
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return._wip_available",
            return_value={("RM-A", "WIP", None): 10},
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return._job_card_available",
            return_value={"JC-ITEM-1": 10},
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return.create_draft_return",
            side_effect=create_draft,
        ):
            response = create_draft_returns("JC-1", quantities)

        self.assertEqual(response["names"], ["DRAFT-STE-A", "DRAFT-STE-B"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1][0]["source_detail"], "LINE-A")
        self.assertEqual(calls[1][1][0]["source_detail"], "LINE-B")

    def test_original_batch_bundle_keeps_each_batch_identity(self):
        from elevenfc_manufacturing.api.job_card_material_return import _row_batch_quantities

        source = frappe._dict(
            item_code="INK-A", batch_no=None, transfer_qty=10,
            serial_and_batch_bundle="SABB-SOURCE",
        )
        entries = [
            frappe._dict(batch_no="INK-BATCH-A", qty=-6),
            frappe._dict(batch_no="INK-BATCH-B", qty=-4),
        ]
        with patch(
            "elevenfc_manufacturing.api.job_card_material_return.frappe.get_all",
            return_value=entries,
        ):
            self.assertEqual(
                _row_batch_quantities(source),
                {"INK-BATCH-A": 6, "INK-BATCH-B": 4},
            )

    def test_legacy_batch_field_is_supported(self):
        from elevenfc_manufacturing.api.job_card_material_return import _row_batch_quantities

        source = frappe._dict(
            batch_no="INK-BATCH-A", transfer_qty=7,
            serial_and_batch_bundle=None,
        )
        self.assertEqual(_row_batch_quantities(source), {"INK-BATCH-A": 7})

    def test_batch_return_must_match_original_batch(self):
        source = frappe._dict(self.source_row.__dict__)
        source.batch_no = "INK-BATCH-A"
        source.serial_and_batch_bundle = None
        self.original.items = [source]
        doc = DummyReturn([row(1, 3)])
        doc.items[0].item_code = "INK-A"
        source.item_code = "INK-A"
        doc.items[0].batch_no = "INK-BATCH-OTHER"
        self.patches[4] = patch(
            "elevenfc_manufacturing.api.job_card_material_return.frappe.get_cached_value",
            side_effect=lambda _type, _name, field: 1 if field == "has_batch_no" else 0,
        )
        with self.assertRaises(frappe.ValidationError):
            self.run_with_mocks(doc)

    def test_batch_return_cannot_exceed_original_batch_balance(self):
        source = frappe._dict(self.source_row.__dict__)
        source.batch_no = "INK-BATCH-A"
        source.serial_and_batch_bundle = None
        source.item_code = "INK-A"
        self.original.items = [source]
        doc = DummyReturn([row(1, 5)])
        doc.items[0].item_code = "INK-A"
        doc.items[0].batch_no = "INK-BATCH-A"
        self.patches[4] = patch(
            "elevenfc_manufacturing.api.job_card_material_return.frappe.get_cached_value",
            side_effect=lambda _type, _name, field: 1 if field == "has_batch_no" else 0,
        )
        with patch(
            "elevenfc_manufacturing.api.job_card_material_return._already_returned_by_batch",
            return_value={("SOURCE-ROW-1", "INK-BATCH-A"): 7},
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return._batch_qty_available",
            return_value=8,
        ):
            with self.assertRaises(frappe.ValidationError):
                self.run_with_mocks(doc)

    def test_batch_return_with_matching_batch_and_stock_is_allowed(self):
        source = frappe._dict(self.source_row.__dict__)
        source.batch_no = "INK-BATCH-A"
        source.serial_and_batch_bundle = None
        source.item_code = "INK-A"
        self.original.items = [source]
        doc = DummyReturn([row(1, 3)])
        doc.items[0].item_code = "INK-A"
        doc.items[0].batch_no = "INK-BATCH-A"
        self.patches[2] = patch(
            "elevenfc_manufacturing.api.job_card_material_return._wip_available",
            return_value={("INK-A", "WIP", None): 8},
        )
        self.patches[4] = patch(
            "elevenfc_manufacturing.api.job_card_material_return.frappe.get_cached_value",
            side_effect=lambda _type, _name, field: 1 if field == "has_batch_no" else 0,
        )
        with patch(
            "elevenfc_manufacturing.api.job_card_material_return._already_returned_by_batch",
            return_value={("SOURCE-ROW-1", "INK-BATCH-A"): 2},
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return._batch_qty_available",
            return_value=8,
        ):
            self.run_with_mocks(doc)

    def test_auto_creation_aggregates_wip_across_multiple_sources(self):
        from elevenfc_manufacturing.api.job_card_material_return import create_draft_returns

        rows = [
            {"original_entry": "STE-A", "source_detail": "LINE-A",
             "item_code": "RM-A", "from_warehouse": "WIP",
             "original_item": None, "job_card_item": "JC-ITEM-1", "maximum_qty": 8},
            {"original_entry": "STE-B", "source_detail": "LINE-B",
             "item_code": "RM-A", "from_warehouse": "WIP",
             "original_item": None, "job_card_item": "JC-ITEM-1", "maximum_qty": 8},
        ]
        with patch(
            "elevenfc_manufacturing.api.job_card_material_return._load_job_card",
            return_value=(object(), SimpleNamespace(name="WO-1")),
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return.frappe.has_permission",
            return_value=True,
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return.get_job_card_returnable_rows",
            return_value=rows,
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return._wip_available",
            return_value={("RM-A", "WIP", None): 8},
        ), patch(
            "elevenfc_manufacturing.api.job_card_material_return._job_card_available",
            return_value={"JC-ITEM-1": 8},
        ):
            with self.assertRaises(frappe.ValidationError):
                create_draft_returns("JC-1", [
                    {"original_entry": "STE-A", "source_detail": "LINE-A", "qty": 5},
                    {"original_entry": "STE-B", "source_detail": "LINE-B", "qty": 5},
                ])
