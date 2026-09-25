"""Tests for tasks/psa_tasks.py (audits/testing_audit.md Finding C3, 141
statements, 0% coverage before this file). Real ConnectWise/Autotask HTTP
calls are never made — PsaIntegration.get_client() is always mocked."""
import uuid
from unittest.mock import MagicMock, patch

import tasks._app_singleton as app_singleton
import tasks.psa_tasks as psa_tasks


def _make_customer(app, name=None):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=name or f"PsaCo-{uuid.uuid4().hex[:6]}", slug=f"psc-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_integration(app, **kwargs):
    from extensions import db
    from models.psa_integration import PsaIntegration
    defaults = dict(
        name=f"PSA-{uuid.uuid4().hex[:6]}", type="connectwise",
        api_url="https://example.invalid", client_id="pub", client_secret_enc="enc-secret",
        is_active=True, sync_companies=True, sync_tickets=True, sync_configs=False,
    )
    defaults.update(kwargs)
    integ = PsaIntegration(**defaults)
    db.session.add(integ)
    db.session.commit()
    return integ


def _cleanup(app, *, integration_ids=(), customer_ids=()):
    from extensions import db
    from models.psa_integration import PsaIntegration, PsaCompanyMap, PsaTicketMap
    from models.customer import Customer
    for iid in integration_ids:
        PsaCompanyMap.query.filter_by(psa_integration_id=iid).delete()
        PsaTicketMap.query.filter_by(psa_integration_id=iid).delete()
        PsaIntegration.query.filter_by(id=iid).delete()
    for cid in customer_ids:
        Customer.query.filter_by(id=cid).delete()
    db.session.commit()


def _run_sync(app, integration_id, fake_client):
    app_singleton._app = app
    with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
        psa_tasks.sync_psa_integration(integration_id)


class TestSyncAllPsaIntegrations:
    def test_dispatches_one_task_per_active_integration(self, app):
        app_singleton._app = app
        cust = _make_customer(app)
        integ = _make_integration(app)
        try:
            with patch("tasks.psa_tasks.sync_psa_integration.delay") as mock_delay:
                psa_tasks.sync_all_psa_integrations()
                mock_delay.assert_called_once_with(integ.id)
        finally:
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id])

    def test_skips_inactive_integrations(self, app):
        app_singleton._app = app
        integ = _make_integration(app, is_active=False)
        try:
            with patch("tasks.psa_tasks.sync_psa_integration.delay") as mock_delay:
                psa_tasks.sync_all_psa_integrations()
                mock_delay.assert_not_called()
        finally:
            _cleanup(app, integration_ids=[integ.id])


class TestSyncPsaIntegrationCompanies:
    def test_matches_psa_company_to_customer_by_name_case_insensitive(self, app):
        cust = _make_customer(app, name="Acme Corp")
        integ = _make_integration(app, sync_tickets=False, sync_configs=False)
        try:
            fake_client = MagicMock()
            fake_client.get_companies.return_value = [{"id": "cw-1", "name": "acme corp"}]
            _run_sync(app, integ.id, fake_client)

            from models.psa_integration import PsaCompanyMap
            cmap = PsaCompanyMap.query.filter_by(psa_integration_id=integ.id, customer_id=cust.id).first()
            assert cmap is not None
            assert cmap.psa_company_id == "cw-1"
        finally:
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id])

    def test_no_match_when_names_differ(self, app):
        cust = _make_customer(app, name="Acme Corp")
        integ = _make_integration(app, sync_tickets=False, sync_configs=False)
        try:
            fake_client = MagicMock()
            fake_client.get_companies.return_value = [{"id": "cw-1", "name": "Totally Different LLC"}]
            _run_sync(app, integ.id, fake_client)

            from models.psa_integration import PsaCompanyMap
            assert PsaCompanyMap.query.filter_by(psa_integration_id=integ.id).first() is None
        finally:
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id])


class TestSyncPsaIntegrationTickets:
    def test_pushes_unmapped_open_ticket(self, app):
        from extensions import db
        from models.ticket import Ticket
        from models.psa_integration import PsaCompanyMap

        cust = _make_customer(app)
        integ = _make_integration(app, sync_companies=False, sync_configs=False)
        db.session.add(PsaCompanyMap(psa_integration_id=integ.id, customer_id=cust.id, psa_company_id="cw-9"))
        ticket = Ticket(title="Printer down", customer_id=cust.id, status="open", priority="medium")
        db.session.add(ticket)
        db.session.commit()
        try:
            fake_client = MagicMock()
            fake_client.push_ticket.return_value = "cw-ticket-1"
            fake_client.pull_tickets.return_value = []
            _run_sync(app, integ.id, fake_client)

            from models.psa_integration import PsaTicketMap
            tmap = PsaTicketMap.query.filter_by(psa_integration_id=integ.id, ticket_id=ticket.id).first()
            assert tmap is not None
            assert tmap.psa_ticket_id == "cw-ticket-1"
            fake_client.push_ticket.assert_called_once()
        finally:
            Ticket.query.filter_by(id=ticket.id).delete()
            db.session.commit()
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id])

    def test_pulls_status_update_for_mapped_ticket(self, app):
        from extensions import db
        from datetime import datetime, timezone
        from models.ticket import Ticket
        from models.psa_integration import PsaTicketMap

        cust = _make_customer(app)
        integ = _make_integration(app, sync_companies=False, sync_configs=False)
        ticket = Ticket(title="Printer down", customer_id=cust.id, status="open", priority="medium")
        db.session.add(ticket)
        db.session.flush()
        db.session.add(PsaTicketMap(psa_integration_id=integ.id, ticket_id=ticket.id, psa_ticket_id="cw-ticket-1"))
        db.session.commit()
        try:
            fake_client = MagicMock()
            fake_client.push_ticket.return_value = None
            fake_client.pull_tickets.return_value = [
                {"psa_ticket_id": "cw-ticket-1", "status": "resolved", "priority": "medium"},
            ]
            _run_sync(app, integ.id, fake_client)

            db.session.refresh(ticket)
            assert ticket.status == "resolved"
            assert ticket.resolved_at is not None
        finally:
            PsaTicketMap.query.filter_by(ticket_id=ticket.id).delete()
            Ticket.query.filter_by(id=ticket.id).delete()
            db.session.commit()
            _cleanup(app, integration_ids=[integ.id], customer_ids=[cust.id])


class TestCircuitBreaker:
    def test_increments_consecutive_failures_on_error(self, app):
        integ = _make_integration(app, sync_companies=True, sync_tickets=False, sync_configs=False)
        try:
            fake_client = MagicMock()
            fake_client.get_companies.side_effect = RuntimeError("boom")
            app_singleton._app = app
            with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
                try:
                    psa_tasks.sync_psa_integration(integ.id)
                except Exception:
                    pass  # self.retry() re-raises — expected

            from extensions import db
            db.session.refresh(integ)
            assert integ.consecutive_failures == 1
            assert integ.sync_error is not None
            assert integ.is_active is True  # below the 10-failure disable threshold
        finally:
            _cleanup(app, integration_ids=[integ.id])

    def test_disables_integration_after_max_consecutive_failures(self, app):
        integ = _make_integration(app, sync_companies=True, sync_tickets=False, sync_configs=False,
                                   consecutive_failures=9)
        try:
            fake_client = MagicMock()
            fake_client.get_companies.side_effect = RuntimeError("boom")
            app_singleton._app = app
            with patch("models.psa_integration.PsaIntegration.get_client", return_value=fake_client):
                try:
                    psa_tasks.sync_psa_integration(integ.id)
                except Exception:
                    pass

            from extensions import db
            db.session.refresh(integ)
            assert integ.consecutive_failures == 10
            assert integ.is_active is False
        finally:
            _cleanup(app, integration_ids=[integ.id])

    def test_resets_consecutive_failures_on_success(self, app):
        integ = _make_integration(app, sync_companies=True, sync_tickets=False, sync_configs=False,
                                   consecutive_failures=5)
        try:
            fake_client = MagicMock()
            fake_client.get_companies.return_value = []
            _run_sync(app, integ.id, fake_client)

            from extensions import db
            db.session.refresh(integ)
            assert integ.consecutive_failures == 0
            assert integ.sync_error is None
        finally:
            _cleanup(app, integration_ids=[integ.id])
