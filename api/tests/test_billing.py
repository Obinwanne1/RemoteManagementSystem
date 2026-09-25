"""Billing/invoice route tests (audits/testing_audit.md Finding C2 — billing.py
had zero test coverage before this file, and was flagged as one of the
highest-risk gaps: Stripe payment links, invoice PDF/email, webhook handling).

Stripe/SMTP aren't configured in the test environment (no STRIPE_SECRET_KEY/
SMTP_HOST) — this is used deliberately to test the "not configured" 503 paths
without needing real credentials, rather than mocking the SDKs."""
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _cleanup(app, *, user_ids=(), invoice_ids=(), customer_ids=()):
    from extensions import db
    from models.billing import Invoice
    from models.customer import Customer
    for iid in invoice_ids:
        Invoice.query.filter_by(id=iid).delete()
    for cid in customer_ids:
        Customer.query.filter_by(id=cid).delete()
    db.session.commit()
    for uid in user_ids:
        try:
            delete_user(app, uid)
        except Exception:
            pass


def _make_customer(app, **kwargs):
    from extensions import db
    from models.customer import Customer
    defaults = dict(name=f"BillCo-{uuid.uuid4().hex[:6]}", slug=f"bc-{uuid.uuid4().hex[:6]}", is_active=True)
    defaults.update(kwargs)
    c = Customer(**defaults)
    db.session.add(c)
    db.session.commit()
    return c


def _make_invoice(app, customer_id, **kwargs):
    from extensions import db
    from datetime import datetime, timezone
    from models.billing import Invoice
    defaults = dict(
        customer_id=customer_id,
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
        device_count=3, per_device_rate=15.0, subtotal=45.0, tax=0.0, total=45.0,
        status="draft",
    )
    defaults.update(kwargs)
    inv = Invoice(**defaults)
    db.session.add(inv)
    db.session.commit()
    return inv


class TestTierFeatures:
    def test_requires_auth(self, client):
        r = client.get("/api/billing/tier-features")
        assert r.status_code == 401

    def test_returns_tier_and_features(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/billing/tier-features", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert "tier" in body
            assert "features" in body
        finally:
            _cleanup(app, user_ids=[uid])


class TestListInvoices:
    def test_requires_role(self, app, client):
        uid, email, pw = create_user(app, role="client")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/billing/invoices", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid])

    def test_lists_invoices_filtered_by_customer(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/billing/invoices?customer_id={cust.id}", headers=auth_headers(token))
            assert r.status_code == 200
            ids = [i["id"] for i in r.get_json()]
            assert inv.id in ids
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])


class TestGenerateInvoice:
    def test_requires_admin(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/billing/invoices/generate", headers=auth_headers(token), json={"customer_id": cust.id})
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid], customer_ids=[cust.id])

    def test_generates_invoice_from_device_count(self, app, client):
        from extensions import db
        from models.device import Device
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        dev1 = Device(hostname=f"h1-{uuid.uuid4().hex[:6]}", customer_id=cust.id, platform="windows")
        dev2 = Device(hostname=f"h2-{uuid.uuid4().hex[:6]}", customer_id=cust.id, platform="windows")
        db.session.add_all([dev1, dev2])
        db.session.commit()
        created_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/billing/invoices/generate", headers=auth_headers(token),
                json={"customer_id": cust.id, "per_device_rate": 10.0},
            )
            assert r.status_code == 201
            body = r.get_json()
            created_id = body["id"]
            assert body["device_count"] == 2
            assert body["subtotal"] == 20.0
            assert body["invoice_number"].startswith("INV-")
        finally:
            Device.query.filter_by(id=dev1.id).delete()
            Device.query.filter_by(id=dev2.id).delete()
            db.session.commit()
            _cleanup(app, user_ids=[uid], invoice_ids=[created_id] if created_id else [], customer_ids=[cust.id])

    def test_requires_customer_id(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/billing/invoices/generate", headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid])


class TestGetInvoice:
    def test_missing_invoice_404s(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/billing/invoices/does-not-exist", headers=auth_headers(token))
            assert r.status_code == 404
        finally:
            _cleanup(app, user_ids=[uid])

    def test_returns_invoice(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/billing/invoices/{inv.id}", headers=auth_headers(token))
            assert r.status_code == 200
            assert r.get_json()["id"] == inv.id
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])


class TestInvoicePdf:
    def test_generates_real_pdf_bytes(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/billing/invoices/{inv.id}/pdf", headers=auth_headers(token))
            assert r.status_code == 200
            assert r.mimetype == "application/pdf"
            assert r.data[:4] == b"%PDF"  # real PDF magic bytes, not a stub
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])


class TestSendInvoiceEmail:
    def test_503_when_smtp_not_configured(self, app, client, monkeypatch):
        monkeypatch.delenv("SMTP_HOST", raising=False)
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app, email="billing@example.com")
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/billing/invoices/{inv.id}/send-email", headers=auth_headers(token))
            assert r.status_code == 503
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])

    def test_400_when_customer_has_no_email(self, app, client, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app, email=None)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/billing/invoices/{inv.id}/send-email", headers=auth_headers(token))
            assert r.status_code == 400
        finally:
            monkeypatch.delenv("SMTP_HOST", raising=False)
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])


class TestSendAndStatus:
    def test_send_marks_sent(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/billing/invoices/{inv.id}/send", headers=auth_headers(token))
            assert r.status_code == 200
            assert r.get_json()["invoice"]["status"] == "sent"
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])

    def test_update_status_rejects_invalid_value(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.patch(
                f"/api/billing/invoices/{inv.id}/status", headers=auth_headers(token),
                json={"status": "not-a-real-status"},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])

    def test_update_status_to_paid_sets_paid_at(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.patch(
                f"/api/billing/invoices/{inv.id}/status", headers=auth_headers(token),
                json={"status": "paid"},
            )
            assert r.status_code == 200
            assert r.get_json()["invoice"]["paid_at"] is not None
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])

    def test_delete_requires_admin(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/billing/invoices/{inv.id}", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])


class TestPaymentLink:
    def test_503_when_stripe_not_configured(self, app, client, monkeypatch):
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
        uid, email, pw = create_user(app, role="admin")
        cust = _make_customer(app)
        inv = _make_invoice(app, cust.id)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/billing/invoices/{inv.id}/payment_link", headers=auth_headers(token))
            assert r.status_code == 503
        finally:
            _cleanup(app, user_ids=[uid], invoice_ids=[inv.id], customer_ids=[cust.id])


class TestStripeWebhook:
    def test_no_jwt_required(self, client):
        """Webhook endpoint is intentionally unauthenticated (verified by Stripe
        signature instead) — a request with a bad/missing signature must be
        rejected with 400, not 401 (no @jwt_required() on this route at all)."""
        r = client.post("/api/billing/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "bad"})
        assert r.status_code == 400
