"""Focused unit tests for the mixed-Project Sales Invoice eligibility gate.

Run in a Frappe/ERPNext bench:
  bench --site <test-site> run-tests --app elevenfc_manufacturing
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from elevenfc_manufacturing.overrides.sales_invoice import MultiProjectSalesInvoiceMixin


def order(name, project, customer="Customer A", company="11FC", currency="PHP"):
    return frappe._dict(
        name=name, project=project, customer=customer, company=company,
        currency=currency, docstatus=1,
    )


def item(name, parent, project=None):
    return frappe._dict(name=name, parent=parent, project=project)


def invoice_row(order_name, item_name, project=None, **kwargs):
    return frappe._dict(
        sales_order=order_name, so_detail=item_name, project=project,
        delivery_note=None, dn_detail=None, scio_detail=None,
        **kwargs,
    )


class NativeValidationStub:
    def validate(self):
        self.native_validate_called = True

    def validate_with_previous_doc(self):
        self.native_reference_called = True


class Invoice(MultiProjectSalesInvoiceMixin, NativeValidationStub):
    def __init__(self, rows, *, customer="Customer A", company="11FC",
                 currency="PHP", project="Project A", **kwargs):
        self.items = rows
        self.customer = customer
        self.company = company
        self.currency = currency
        self.project = project
        self.is_return = 0
        self.is_pos = 0
        self.is_debit_note = 0
        self.is_internal_customer = 0
        self.native_validate_called = False
        self.native_reference_called = False
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get(self, key, default=None):
        return getattr(self, key, default)


class TestMixedProjectInvoice(TestCase):
    def setUp(self):
        self.rows = [invoice_row("SO-1", "SOI-1"), invoice_row("SO-2", "SOI-2")]
        self.orders = [order("SO-1", "Project A"), order("SO-2", "Project B")]
        self.source_items = [item("SOI-1", "SO-1"), item("SOI-2", "SO-2")]

    def mock_sources(self, orders=None, items=None):
        orders = self.orders if orders is None else orders
        items = self.source_items if items is None else items

        def read(doctype, **_kwargs):
            return orders if doctype == "Sales Order" else items

        return patch("elevenfc_manufacturing.overrides.sales_invoice.frappe.get_all",
                     side_effect=read)

    def test_mixed_orders_clear_header_and_preserve_line_projects(self):
        invoice = Invoice(self.rows)
        with self.mock_sources():
            invoice.validate()

        self.assertTrue(invoice.native_validate_called)
        self.assertIsNone(invoice.project)
        self.assertEqual([r.project for r in invoice.items], ["Project A", "Project B"])
        self.assertEqual([r.sales_order for r in invoice.items], ["SO-1", "SO-2"])
        self.assertEqual([r.so_detail for r in invoice.items], ["SOI-1", "SOI-2"])

    def test_source_item_project_overrides_order_header(self):
        self.source_items[0].project = "Project A Item"
        invoice = Invoice(self.rows)
        with self.mock_sources():
            invoice.validate()
        self.assertEqual(invoice.items[0].project, "Project A Item")

    def test_single_order_uses_native_path(self):
        invoice = Invoice([self.rows[0]])
        with self.mock_sources():
            invoice.validate()
        self.assertEqual(invoice.project, "Project A")
        self.assertTrue(invoice.native_validate_called)

    def test_same_project_uses_native_path(self):
        invoice = Invoice(self.rows)
        with self.mock_sources(orders=[order("SO-1", "Project A"),
                                       order("SO-2", "Project A")]):
            invoice.validate()
        self.assertEqual(invoice.project, "Project A")

    def test_wrong_customer_does_not_relax_validation(self):
        invoice = Invoice(self.rows)
        with self.mock_sources(orders=[order("SO-1", "Project A"),
                                       order("SO-2", "Project B", customer="Other")]):
            self.assertIsNone(invoice._mixed_so_item_projects())

    def test_wrong_company_does_not_relax_validation(self):
        invoice = Invoice(self.rows)
        with self.mock_sources(orders=[order("SO-1", "Project A"),
                                       order("SO-2", "Project B", company="Other")]):
            self.assertIsNone(invoice._mixed_so_item_projects())

    def test_wrong_currency_does_not_relax_validation(self):
        invoice = Invoice(self.rows)
        with self.mock_sources(orders=[order("SO-1", "Project A"),
                                       order("SO-2", "Project B", currency="USD")]):
            self.assertIsNone(invoice._mixed_so_item_projects())

    def test_invalid_sales_order_item_link_does_not_relax_validation(self):
        invoice = Invoice(self.rows)
        with self.mock_sources(items=[item("SOI-1", "SO-2"),
                                      item("SOI-2", "SO-2")]):
            self.assertIsNone(invoice._mixed_so_item_projects())

    def test_direct_unlinked_item_does_not_relax_validation(self):
        invoice = Invoice(self.rows + [invoice_row(None, None)])
        with self.mock_sources():
            self.assertIsNone(invoice._mixed_so_item_projects())

    def test_delivery_note_flow_uses_native_path(self):
        self.rows[0].delivery_note = "DN-1"
        invoice = Invoice(self.rows)
        with self.mock_sources():
            invoice.validate()
        self.assertEqual(invoice.project, "Project A")

    def test_returns_and_pos_do_not_relax_validation(self):
        for flag in ("is_return", "is_pos", "is_debit_note", "is_internal_customer"):
            with self.subTest(flag=flag):
                invoice = Invoice(self.rows, **{flag: 1})
                with self.mock_sources():
                    self.assertIsNone(invoice._mixed_so_item_projects())
