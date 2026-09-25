"""Tests for tasks/billing_tasks.py::generate_recurring_invoices
(audits/testing_audit.md Finding C3) — including the idempotency behavior
CLAUDE.md documents (skips if an invoice for that period already exists)."""
import uuid
from datetime import datetime, timezone

import tasks._app_singleton as app_singleton
import tasks.billing_tasks as billing_tasks


def _make_customer(**kwargs):
    from extensions import db
    from models.customer import Customer
    defaults = dict(
        name=f"BillCo-{uuid.uuid4().hex[:6]}", slug=f"bc-{uuid.uuid4().hex[:6]}",
        is_active=True, billing_day=datetime.now(timezone.utc).day,
        per_device_rate=20.0, tax_rate=0.0,
    )
    defaults.update(kwargs)
    c = Customer(**defaults)
    db.session.add(c)
    db.session.commit()
    return c.id


def _make_device(customer_id):
    from extensions import db
    from models.device import Device
    d = Device(hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id, is_online=True)
    db.session.add(d)
    db.session.commit()
    return d.id


def _cleanup(*, customer_id=None, device_ids=(), invoice_ids=()):
    from extensions import db
    from models.device import Device
    from models.customer import Customer
    from models.billing import Invoice
    for did in device_ids:
        Device.query.filter_by(id=did).delete()
    for iid in invoice_ids:
        Invoice.query.filter_by(id=iid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()


class TestGenerateRecurringInvoices:
    def test_generates_invoice_for_customer_due_today(self, app):
        app_singleton._app = app
        with app.app_context():
            cust_id = _make_customer()
            dev_id = _make_device(cust_id)

        result = billing_tasks.generate_recurring_invoices()

        with app.app_context():
            invoice_id = None
            try:
                assert result["generated"] == 1
                from models.billing import Invoice
                inv = Invoice.query.filter_by(customer_id=cust_id).first()
                assert inv is not None
                assert inv.status == "draft"
                assert inv.device_count == 1
                assert inv.subtotal == 20.0
                assert inv.total == 20.0
                invoice_id = inv.id
            finally:
                _cleanup(customer_id=cust_id, device_ids=[dev_id],
                         invoice_ids=[invoice_id] if invoice_id else [])

    def test_skips_customer_not_due_today(self, app):
        app_singleton._app = app
        with app.app_context():
            # 32 is never a valid day-of-month, so this customer can never match "today"
            cust_id = _make_customer(billing_day=32)

        billing_tasks.generate_recurring_invoices()

        with app.app_context():
            try:
                from models.billing import Invoice
                assert Invoice.query.filter_by(customer_id=cust_id).first() is None
            finally:
                _cleanup(customer_id=cust_id)

    def test_idempotent_skips_if_invoice_already_exists_for_period(self, app):
        """Regression test for the documented idempotency behavior — running
        the task twice in the same period must not create a duplicate invoice."""
        app_singleton._app = app
        with app.app_context():
            cust_id = _make_customer()
            dev_id = _make_device(cust_id)

        first = billing_tasks.generate_recurring_invoices()
        second = billing_tasks.generate_recurring_invoices()

        with app.app_context():
            invoice_id = None
            try:
                assert first["generated"] == 1
                assert second["generated"] == 0
                from models.billing import Invoice
                invoices = Invoice.query.filter_by(customer_id=cust_id).all()
                assert len(invoices) == 1
                invoice_id = invoices[0].id
            finally:
                _cleanup(customer_id=cust_id, device_ids=[dev_id],
                         invoice_ids=[invoice_id] if invoice_id else [])

    def test_zero_rate_customer_excluded(self, app):
        app_singleton._app = app
        with app.app_context():
            cust_id = _make_customer(per_device_rate=0)

        billing_tasks.generate_recurring_invoices()

        with app.app_context():
            try:
                from models.billing import Invoice
                assert Invoice.query.filter_by(customer_id=cust_id).first() is None
            finally:
                _cleanup(customer_id=cust_id)
