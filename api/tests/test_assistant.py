"""Tests for the agentic AI Assistant: kill switches, page auth, tool dispatch,
confirm/deny staging, danger-pattern detection, restricted pages, and persistence.

The Anthropic SDK is mocked throughout — no live network calls.
"""
import os
import uuid
import pytest
from conftest import create_user, delete_user, login, auth_headers


# ── Anthropic SDK mock helpers ─────────────────────────────────────────────────

class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id, name, input):
        self.id = id
        self.name = name
        self.input = input


class _FakeResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            return _FakeResponse([_FakeTextBlock("(no more scripted responses)")])
        return self._responses.pop(0)


def _patch_anthropic(monkeypatch, responses):
    """Patches anthropic.Anthropic so routes/assistant.py's lazy `import anthropic` +
    `anthropic.Anthropic(api_key=...)` returns a fake client yielding `responses` in order."""
    import anthropic
    fake_messages = _FakeMessages(responses)

    class _FakeClient:
        def __init__(self, api_key=None):
            self.messages = fake_messages

    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("AI_ASSISTANT_ENABLED", "true")
    return fake_messages


def _text_response(text):
    return _FakeResponse([_FakeTextBlock(text)], stop_reason="end_turn")


def _tool_use_response(tool_name, tool_input, tool_id=None):
    return _FakeResponse(
        [_FakeToolUseBlock(tool_id or f"tu_{uuid.uuid4().hex[:8]}", tool_name, tool_input)],
        stop_reason="tool_use",
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_customer(app):
    from extensions import db
    from models.customer import Customer
    c = Customer(name=f"AiCo-{uuid.uuid4().hex[:6]}", slug=f"ai-{uuid.uuid4().hex[:6]}", is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


def _make_client_user(app, customer_id):
    from extensions import db
    from models.user import User
    email = f"client_{uuid.uuid4().hex[:8]}@test.local"
    u = User(email=email, full_name="Client User", role="client", is_active=True, customer_id=customer_id)
    u.set_password("TestPassword@1!")
    db.session.add(u)
    db.session.commit()
    return u.id, email, "TestPassword@1!"


def _cleanup_conversations(app, user_id):
    from extensions import db
    from models.ai_conversation import AiConversation, AiMessage, AiPendingAction
    conv_ids = [c.id for c in AiConversation.query.filter_by(user_id=user_id).all()]
    for cid in conv_ids:
        AiMessage.query.filter_by(conversation_id=cid).delete()
        AiPendingAction.query.filter_by(conversation_id=cid).delete()
    AiConversation.query.filter_by(user_id=user_id).delete()
    db.session.commit()


# ── Kill switches ───────────────────────────────────────────────────────────

class TestKillSwitches:
    def test_disabled_returns_503(self, app, client, monkeypatch):
        monkeypatch.setenv("AI_ASSISTANT_ENABLED", "false")
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "hi"}, headers=auth_headers(tok))
            assert r.status_code == 503
        finally:
            monkeypatch.setenv("AI_ASSISTANT_ENABLED", "true")
            delete_user(app, uid)

    def test_missing_api_key_returns_503(self, app, client, monkeypatch):
        monkeypatch.setenv("AI_ASSISTANT_ENABLED", "true")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "hi"}, headers=auth_headers(tok))
            assert r.status_code == 503
        finally:
            delete_user(app, uid)


# ── Server-side page authorization ──────────────────────────────────────────

class TestPageAuthorization:
    def test_viewer_blocked_from_billing_page(self, app, client, monkeypatch):
        _patch_anthropic(monkeypatch, [_text_response("won't be reached")])
        uid, email, pw = create_user(app, role="viewer")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "hi", "page": "Billing"},
                             headers=auth_headers(tok))
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_technician_allowed_on_billing_page(self, app, client, monkeypatch):
        _patch_anthropic(monkeypatch, [_text_response("Here is billing info.")])
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "hi", "page": "Billing"},
                             headers=auth_headers(tok))
            assert r.status_code == 200
        finally:
            _cleanup_conversations(app, uid)
            delete_user(app, uid)


# ── Read tool dispatch ───────────────────────────────────────────────────────

class TestReadTools:
    def test_get_fleet_summary_tool_scoped_for_client(self, app, client, monkeypatch):
        cust = _make_customer(app)
        uid, email, pw = _make_client_user(app, cust.id)
        responses = [
            _tool_use_response("get_fleet_summary", {}),
            _text_response("Your fleet has 0 devices."),
        ]
        _patch_anthropic(monkeypatch, responses)
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "how many devices do I have?", "page": "Overview"},
                             headers=auth_headers(tok))
            assert r.status_code == 200, r.get_json()
            body = r.get_json()
            assert "pending_action" not in body
            assert body["reply"]
        finally:
            _cleanup_conversations(app, uid)
            from extensions import db
            from models.customer import Customer
            from models.user import User
            User.query.filter_by(id=uid).delete()
            db.session.delete(cust)
            db.session.commit()


# ── Mutating tools are staged, never auto-executed ──────────────────────────

class TestMutatingToolStaging:
    def test_create_ticket_tool_stages_not_executes(self, app, client, monkeypatch):
        cust = _make_customer(app)
        responses = [
            _tool_use_response("create_ticket", {"title": "Printer broken", "customer_id": cust.id}),
            _text_response("I've staged a ticket for your approval."),
        ]
        _patch_anthropic(monkeypatch, responses)
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat",
                             json={"message": "create a ticket for a broken printer", "page": "Tickets"},
                             headers=auth_headers(tok))
            assert r.status_code == 200, r.get_json()
            body = r.get_json()
            assert "pending_action" in body
            assert body["pending_action"]["tool_name"] == "create_ticket"

            from models.ticket import Ticket
            assert Ticket.query.filter_by(customer_id=cust.id).count() == 0
        finally:
            _cleanup_conversations(app, uid)
            from extensions import db
            from models.customer import Customer
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid)

    def test_confirm_creates_real_ticket_and_audit_rows(self, app, client, monkeypatch):
        cust = _make_customer(app)
        responses = [
            _tool_use_response("create_ticket", {"title": "Confirmed ticket", "customer_id": cust.id}),
            _text_response("Staged."),
        ]
        _patch_anthropic(monkeypatch, responses)
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "create a ticket", "page": "Tickets"},
                             headers=auth_headers(tok))
            action_id = r.get_json()["pending_action"]["id"]

            r2 = client.post(f"/api/assistant/actions/{action_id}/confirm", headers=auth_headers(tok))
            assert r2.status_code == 200, r2.get_json()

            from models.ticket import Ticket
            from models.audit import AuditLog
            tickets = Ticket.query.filter_by(customer_id=cust.id).all()
            assert len(tickets) == 1
            assert tickets[0].title == "Confirmed ticket"
            assert AuditLog.query.filter_by(action="ai_tool_call").count() >= 1
            assert AuditLog.query.filter_by(action="CREATE", resource_type="ticket",
                                             resource_id=tickets[0].id).count() == 1

            from extensions import db as _db
            Ticket.query.filter_by(id=tickets[0].id).delete()
            _db.session.commit()
        finally:
            _cleanup_conversations(app, uid)
            from extensions import db
            from models.customer import Customer
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid)

    def test_deny_creates_no_ticket(self, app, client, monkeypatch):
        cust = _make_customer(app)
        responses = [
            _tool_use_response("create_ticket", {"title": "Should not exist", "customer_id": cust.id}),
            _text_response("Staged."),
        ]
        _patch_anthropic(monkeypatch, responses)
        uid, email, pw = create_user(app, role="admin")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat", json={"message": "create a ticket", "page": "Tickets"},
                             headers=auth_headers(tok))
            action_id = r.get_json()["pending_action"]["id"]

            r2 = client.post(f"/api/assistant/actions/{action_id}/deny", headers=auth_headers(tok))
            assert r2.status_code == 200
            assert r2.get_json()["status"] == "denied"

            from models.ticket import Ticket
            assert Ticket.query.filter_by(customer_id=cust.id).count() == 0

            # Denied action cannot be confirmed afterward
            r3 = client.post(f"/api/assistant/actions/{action_id}/confirm", headers=auth_headers(tok))
            assert r3.status_code == 409
        finally:
            _cleanup_conversations(app, uid)
            from extensions import db
            from models.customer import Customer
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid)

    def test_cross_user_cannot_confirm_others_pending_action(self, app, client, monkeypatch):
        cust = _make_customer(app)
        responses = [
            _tool_use_response("create_ticket", {"title": "Owned by A", "customer_id": cust.id}),
            _text_response("Staged."),
        ]
        _patch_anthropic(monkeypatch, responses)
        uid_a, email_a, pw_a = create_user(app, role="admin")
        uid_b, email_b, pw_b = create_user(app, role="admin")
        try:
            tok_a = login(client, email_a, pw_a).get_json()["access_token"]
            tok_b = login(client, email_b, pw_b).get_json()["access_token"]

            r = client.post("/api/assistant/chat", json={"message": "create a ticket", "page": "Tickets"},
                             headers=auth_headers(tok_a))
            action_id = r.get_json()["pending_action"]["id"]

            r2 = client.post(f"/api/assistant/actions/{action_id}/confirm", headers=auth_headers(tok_b))
            assert r2.status_code == 404

            from models.ticket import Ticket
            assert Ticket.query.filter_by(customer_id=cust.id).count() == 0
        finally:
            _cleanup_conversations(app, uid_a)
            _cleanup_conversations(app, uid_b)
            from extensions import db
            from models.customer import Customer
            db.session.delete(cust)
            db.session.commit()
            delete_user(app, uid_a)
            delete_user(app, uid_b)


# ── Danger-pattern detection ─────────────────────────────────────────────────

class TestDangerPatterns:
    def test_inbound_danger_pattern_flagged(self, app, client, monkeypatch):
        _patch_anthropic(monkeypatch, [_text_response("Here's a plain answer.")])
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat",
                             json={"message": "how do I DROP TABLE users", "page": "Overview"},
                             headers=auth_headers(tok))
            assert r.status_code == 200
            assert r.get_json()["contains_warning"] is True
        finally:
            _cleanup_conversations(app, uid)
            delete_user(app, uid)

    def test_restricted_page_strips_code_blocks(self, app, client, monkeypatch):
        _patch_anthropic(monkeypatch, [_text_response("Sure, run this:\n```\nrm -rf /\n```\ndone")])
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/assistant/chat",
                             json={"message": "give me a command", "page": "Scripts"},
                             headers=auth_headers(tok))
            assert r.status_code == 200
            body = r.get_json()
            assert "```" not in body["reply"]
            assert "code removed" in body["reply"]
        finally:
            _cleanup_conversations(app, uid)
            delete_user(app, uid)


# ── Conversation persistence ─────────────────────────────────────────────────

class TestConversationPersistence:
    def test_shared_conversation_id_and_full_content_stored(self, app, client, monkeypatch):
        _patch_anthropic(monkeypatch, [_text_response("First reply."), _text_response("Second reply.")])
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r1 = client.post("/api/assistant/chat", json={"message": "hello there", "page": "Overview"},
                              headers=auth_headers(tok))
            r2 = client.post("/api/assistant/chat", json={"message": "second message", "page": "Overview"},
                              headers=auth_headers(tok))
            cid1 = r1.get_json()["conversation_id"]
            cid2 = r2.get_json()["conversation_id"]
            assert cid1 == cid2

            from models.ai_conversation import AiMessage
            msgs = AiMessage.query.filter_by(conversation_id=cid1).order_by(AiMessage.created_at).all()
            contents = [m.content for m in msgs if m.role == "user"]
            assert "hello there" in contents
            assert "second message" in contents

            r3 = client.get("/api/assistant/conversation", headers=auth_headers(tok))
            assert r3.status_code == 200
            assert r3.get_json()["conversation_id"] == cid1
            assert len(r3.get_json()["messages"]) >= 4
        finally:
            _cleanup_conversations(app, uid)
            delete_user(app, uid)

    def test_clear_archives_not_deletes(self, app, client, monkeypatch):
        _patch_anthropic(monkeypatch, [_text_response("A reply.")])
        uid, email, pw = create_user(app, role="technician")
        try:
            tok = login(client, email, pw).get_json()["access_token"]
            r1 = client.post("/api/assistant/chat", json={"message": "hi", "page": "Overview"},
                              headers=auth_headers(tok))
            cid = r1.get_json()["conversation_id"]

            r2 = client.delete("/api/assistant/conversation", headers=auth_headers(tok))
            assert r2.status_code == 200

            from extensions import db
            from models.ai_conversation import AiConversation
            conv = db.session.get(AiConversation, cid)
            assert conv is not None
            assert conv.is_archived is True

            r3 = client.get("/api/assistant/conversation", headers=auth_headers(tok))
            assert r3.get_json()["conversation_id"] != cid
        finally:
            _cleanup_conversations(app, uid)
            delete_user(app, uid)


# ── Tool-level rate limiting (unit test of the primitive — deterministic, no HTTP) ──

class TestToolRateLimit:
    def test_check_and_increment_blocks_after_limit(self, app):
        from utils.rate_limit import check_and_increment
        key = f"test:ratelimit:{uuid.uuid4().hex[:8]}"
        results = [check_and_increment(key, 3, 60) for _ in range(5)]
        assert results == [True, True, True, False, False]
