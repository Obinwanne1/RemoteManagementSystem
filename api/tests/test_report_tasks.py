"""Tests for tasks/report_tasks.py::generate_report (audits/testing_audit.md
Finding C3 — 0% coverage before this file). Writes a real CSV to
api/reports/ (REPORTS_DIR) — every test that generates a file deletes it
in a finally block so nothing is left on disk."""
import csv
import os
import uuid
from datetime import datetime, timezone

import tasks._app_singleton as app_singleton
import tasks.report_tasks as report_tasks


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"RptCo-{uuid.uuid4().hex[:6]}", slug=f"rc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_device(app, customer_id, hostname=None):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=hostname or f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        platform="windows", os_name="Windows 11", ip_address="10.0.0.1", is_online=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _make_report(app, template_type, customer_id=None):
    from extensions import db
    from models.report import Report
    r = Report(name=f"Report-{uuid.uuid4().hex[:6]}", template_type=template_type, customer_id=customer_id)
    db.session.add(r)
    db.session.commit()
    return r


def _cleanup(app, *, report_ids=(), device_ids=(), customer_id=None):
    from extensions import db
    from models.report import Report
    from models.device import Device, DeviceMetrics
    from models.customer import Customer
    for rid in report_ids:
        rpt = db.session.get(Report, rid)
        if rpt and rpt.file_path and os.path.exists(rpt.file_path):
            os.remove(rpt.file_path)
        Report.query.filter_by(id=rid).delete()
    for did in device_ids:
        DeviceMetrics.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()


def _run_generate(app, report_id):
    app_singleton._app = app
    report_tasks.generate_report(report_id)


class TestGenerateReport:
    def test_unknown_report_id_returns_without_error(self, app):
        app_singleton._app = app
        assert report_tasks.generate_report("not-a-real-id") is None

    def test_device_health_report_writes_csv_with_expected_rows(self, app):
        cust = _make_customer(app)
        dev = _make_device(app, cust.id, hostname="report-test-host")
        report = _make_report(app, "device_health", customer_id=cust.id)
        try:
            _run_generate(app, report.id)
            from extensions import db
            db.session.refresh(report)
            assert report.file_path is not None
            assert report.format == "csv"
            assert os.path.exists(report.file_path)
            with open(report.file_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            assert any(r["hostname"] == "report-test-host" for r in rows)
        finally:
            _cleanup(app, report_ids=[report.id], device_ids=[dev.id], customer_id=cust.id)

    def test_ticket_summary_report_filters_by_customer(self, app):
        from extensions import db
        from models.ticket import Ticket
        cust = _make_customer(app)
        other_cust = _make_customer(app)
        t1 = Ticket(title="In scope", customer_id=cust.id, status="open")
        t2 = Ticket(title="Other customer", customer_id=other_cust.id, status="open")
        db.session.add_all([t1, t2])
        db.session.commit()
        report = _make_report(app, "ticket_summary", customer_id=cust.id)
        try:
            _run_generate(app, report.id)
            db.session.refresh(report)
            with open(report.file_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            titles = {r["title"] for r in rows}
            assert "In scope" in titles
            assert "Other customer" not in titles
        finally:
            Ticket.query.filter_by(id=t1.id).delete()
            Ticket.query.filter_by(id=t2.id).delete()
            db.session.commit()
            _cleanup(app, report_ids=[report.id], customer_id=cust.id)
            _cleanup(app, customer_id=other_cust.id)

    def test_unknown_template_type_produces_placeholder_row(self, app):
        report = _make_report(app, "not_a_real_template")
        try:
            _run_generate(app, report.id)
            from extensions import db
            db.session.refresh(report)
            with open(report.file_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 1
            assert "Unknown template type" in rows[0]["info"]
        finally:
            _cleanup(app, report_ids=[report.id])
