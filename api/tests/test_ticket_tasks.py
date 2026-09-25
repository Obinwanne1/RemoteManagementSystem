"""Tests for tasks/ticket_tasks.py::check_sla_breaches (audits/testing_audit.md
Finding C3 — 0% coverage before this file). Pairs with the SLA policy logic in
api/routes/sla_policies.py and tickets.py's _sla_resolution_hours()."""
import uuid
from datetime import datetime, timedelta, timezone

import tasks._app_singleton as app_singleton
import tasks.ticket_tasks as ticket_tasks


def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"TktCo-{uuid.uuid4().hex[:6]}", slug=f"tc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_ticket(app, customer_id, *, due_date=None, status="open", sla_breached=False):
    from extensions import db
    from models.ticket import Ticket
    t = Ticket(
        title=f"Ticket-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        status=status, due_date=due_date, sla_breached=sla_breached,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _cleanup(app, *, ticket_ids=(), customer_id=None):
    from extensions import db
    from models.ticket import Ticket
    from models.customer import Customer
    for tid in ticket_ids:
        Ticket.query.filter_by(id=tid).delete()
    if customer_id:
        Customer.query.filter_by(id=customer_id).delete()
    db.session.commit()


def _run_check_sla_breaches(app):
    app_singleton._app = app
    ticket_tasks.check_sla_breaches()


class TestCheckSlaBreaches:
    def test_marks_overdue_open_ticket_as_breached(self, app):
        cust = _make_customer(app)
        past_due = datetime.now(timezone.utc) - timedelta(hours=1)
        t = _make_ticket(app, cust.id, due_date=past_due, status="open")
        try:
            _run_check_sla_breaches(app)
            from extensions import db
            db.session.refresh(t)
            assert t.sla_breached is True
        finally:
            _cleanup(app, ticket_ids=[t.id], customer_id=cust.id)

    def test_marks_overdue_in_progress_ticket_as_breached(self, app):
        cust = _make_customer(app)
        past_due = datetime.now(timezone.utc) - timedelta(minutes=5)
        t = _make_ticket(app, cust.id, due_date=past_due, status="in_progress")
        try:
            _run_check_sla_breaches(app)
            from extensions import db
            db.session.refresh(t)
            assert t.sla_breached is True
        finally:
            _cleanup(app, ticket_ids=[t.id], customer_id=cust.id)

    def test_does_not_breach_ticket_not_yet_due(self, app):
        cust = _make_customer(app)
        future_due = datetime.now(timezone.utc) + timedelta(hours=2)
        t = _make_ticket(app, cust.id, due_date=future_due, status="open")
        try:
            _run_check_sla_breaches(app)
            from extensions import db
            db.session.refresh(t)
            assert t.sla_breached is False
        finally:
            _cleanup(app, ticket_ids=[t.id], customer_id=cust.id)

    def test_ignores_resolved_ticket_even_if_overdue(self, app):
        """A ticket resolved before its due_date passed should never be
        retroactively flagged — the query excludes status not in (open, in_progress)."""
        cust = _make_customer(app)
        past_due = datetime.now(timezone.utc) - timedelta(hours=1)
        t = _make_ticket(app, cust.id, due_date=past_due, status="resolved")
        try:
            _run_check_sla_breaches(app)
            from extensions import db
            db.session.refresh(t)
            assert t.sla_breached is False
        finally:
            _cleanup(app, ticket_ids=[t.id], customer_id=cust.id)

    def test_ignores_ticket_with_no_due_date(self, app):
        cust = _make_customer(app)
        t = _make_ticket(app, cust.id, due_date=None, status="open")
        try:
            _run_check_sla_breaches(app)
            from extensions import db
            db.session.refresh(t)
            assert t.sla_breached is False
        finally:
            _cleanup(app, ticket_ids=[t.id], customer_id=cust.id)

    def test_already_breached_ticket_is_left_alone(self, app):
        """Query filters sla_breached == False, so an already-flagged ticket
        isn't re-touched (idempotent re-runs, cheap no-op query)."""
        cust = _make_customer(app)
        past_due = datetime.now(timezone.utc) - timedelta(hours=1)
        t = _make_ticket(app, cust.id, due_date=past_due, status="open", sla_breached=True)
        try:
            _run_check_sla_breaches(app)
            from extensions import db
            db.session.refresh(t)
            assert t.sla_breached is True
        finally:
            _cleanup(app, ticket_ids=[t.id], customer_id=cust.id)

    def test_returns_none_when_nothing_to_breach(self, app):
        app_singleton._app = app
        result = ticket_tasks.check_sla_breaches()
        assert result is None
