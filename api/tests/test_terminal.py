"""Remote Terminal tests (audits/testing_audit.md Finding C2 — terminal.py was
the LOWEST-covered route file in the project, 19%, and the highest-risk: it's
the remote-shell surface). Covers both the JWT dashboard endpoints (session
create/get/close/send-command/output) and the agent-Bearer-token endpoints
(poll for pending commands, mark running, stream output, mark done)."""
import hashlib
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _make_device(app, *, is_agentless=False, customer_id=None):
    from extensions import db
    from models.device import Device
    d = Device(
        hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
        platform="windows", is_online=True, is_agentless=is_agentless,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _make_agent_token(app, device_id, raw_token=None):
    from extensions import db
    from models.audit import AgentToken
    raw_token = raw_token or f"raw-term-token-{uuid.uuid4().hex[:8]}"
    at = AgentToken(device_id=device_id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest())
    db.session.add(at)
    db.session.commit()
    return raw_token


def _cleanup(app, *, device_ids=(), session_ids=(), user_ids=()):
    from extensions import db
    from models.device import Device
    from models.audit import AgentToken
    from models.terminal import TerminalSession, TerminalCommand, TerminalOutput
    for sid in session_ids:
        TerminalOutput.query.filter_by(session_id=sid).delete()
        TerminalCommand.query.filter_by(session_id=sid).delete()
        TerminalSession.query.filter_by(id=sid).delete()
    for did in device_ids:
        AgentToken.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    db.session.commit()
    for uid in user_ids:
        try:
            delete_user(app, uid)
        except Exception:
            pass


class TestCreateSession:
    def test_requires_admin_or_technician_role(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        dev = _make_device(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            assert r.status_code == 403
        finally:
            _cleanup(app, device_ids=[dev.id], user_ids=[uid])

    def test_requires_device_id(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid])

    def test_404_for_nonexistent_device(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": "not-a-real-id"})
            assert r.status_code == 404
        finally:
            _cleanup(app, user_ids=[uid])

    def test_rejects_agentless_device(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app, is_agentless=True)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], user_ids=[uid])

    def test_client_role_cannot_open_session_on_other_customers_device(self, app, client):
        from extensions import db
        from models.user import User
        from models.customer import Customer
        client_uid, client_email, client_pw = create_user(app, role="client")
        own_cust = Customer(name=f"C-{uuid.uuid4().hex[:6]}", slug=f"c-{uuid.uuid4().hex[:6]}", is_active=True)
        other_cust = Customer(name=f"C-{uuid.uuid4().hex[:6]}", slug=f"c-{uuid.uuid4().hex[:6]}", is_active=True)
        db.session.add_all([own_cust, other_cust])
        db.session.commit()
        other_dev = _make_device(app, customer_id=other_cust.id)
        try:
            u = db.session.get(User, client_uid)
            u.customer_id = own_cust.id
            db.session.commit()

            token = login(client, client_email, client_pw).get_json()["access_token"]
            r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": other_dev.id})
            # Route only checks _require_role("admin", "technician") — a "client"
            # role is rejected by that check before device ownership is ever
            # evaluated, so this asserts 403 (role gate), not 404 (scope gate).
            assert r.status_code == 403
        finally:
            _cleanup(app, device_ids=[other_dev.id], user_ids=[client_uid])
            Customer.query.filter_by(id=own_cust.id).delete()
            Customer.query.filter_by(id=other_cust.id).delete()
            db.session.commit()

    def test_creates_session_with_welcome_message(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            assert r.status_code == 201
            body = r.get_json()
            session_id = body["id"]
            assert body["device_id"] == dev.id
            assert body["status"] == "active"

            out = client.get(f"/api/terminal/sessions/{session_id}/output", headers=auth_headers(token))
            assert out.status_code == 200
            outputs = out.get_json()["output"]
            assert len(outputs) == 1
            assert outputs[0]["stream"] == "system"
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])

    def test_opening_a_second_session_closes_the_first(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_ids = []
        try:
            token = login(client, email, pw).get_json()["access_token"]
            first = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            first_id = first.get_json()["id"]
            session_ids.append(first_id)

            second = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_ids.append(second.get_json()["id"])

            check = client.get(f"/api/terminal/sessions/{first_id}", headers=auth_headers(token))
            assert check.get_json()["status"] == "closed"
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=session_ids, user_ids=[uid])


class TestSessionOwnership:
    def test_technician_cannot_see_another_technicians_session(self, app, client):
        owner_uid, owner_email, owner_pw = create_user(app, role="technician")
        other_uid, other_email, other_pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            owner_token = login(client, owner_email, owner_pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(owner_token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]

            other_token = login(client, other_email, other_pw).get_json()["access_token"]
            r = client.get(f"/api/terminal/sessions/{session_id}", headers=auth_headers(other_token))
            assert r.status_code == 404
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[owner_uid, other_uid])

    def test_admin_can_see_any_technicians_session(self, app, client):
        owner_uid, owner_email, owner_pw = create_user(app, role="technician")
        admin_uid, admin_email, admin_pw = create_user(app, role="admin")
        dev = _make_device(app)
        session_id = None
        try:
            owner_token = login(client, owner_email, owner_pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(owner_token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]

            admin_token = login(client, admin_email, admin_pw).get_json()["access_token"]
            r = client.get(f"/api/terminal/sessions/{session_id}", headers=auth_headers(admin_token))
            assert r.status_code == 200
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[owner_uid, admin_uid])


class TestSendCommand:
    def test_requires_active_session(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]
            client.delete(f"/api/terminal/sessions/{session_id}", headers=auth_headers(token))

            r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "ls"},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])

    def test_rejects_empty_command(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]

            r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "   "},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])

    def test_rejects_command_over_2000_chars(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]

            r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "x" * 2001},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])

    def test_queues_command_and_echoes_to_output(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]

            r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "whoami"},
            )
            assert r.status_code == 201
            assert r.get_json()["status"] == "pending"

            out = client.get(f"/api/terminal/sessions/{session_id}/output", headers=auth_headers(token))
            body = out.get_json()
            assert body["pending_commands"] == 1
            echoed = [o for o in body["output"] if "whoami" in o["content"]]
            assert len(echoed) == 1
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])


class TestAgentPolling:
    def test_agent_endpoints_require_valid_token(self, app, client):
        dev = _make_device(app)
        try:
            r = client.get(f"/api/terminal/agent/{dev.id}/sessions")
            assert r.status_code == 401
        finally:
            _cleanup(app, device_ids=[dev.id])

    def test_agent_sees_pending_command_for_its_session(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]
            cmd_r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "ipconfig"},
            )
            cmd_id = cmd_r.get_json()["id"]

            raw_token = _make_agent_token(app, dev.id)
            r = client.get(
                f"/api/terminal/agent/{dev.id}/sessions",
                headers={"Authorization": f"Bearer {raw_token}"},
            )
            assert r.status_code == 200
            sessions = r.get_json()["sessions"]
            assert any(s["session_id"] == session_id and s["pending_command"]["id"] == cmd_id for s in sessions)
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])

    def test_full_command_lifecycle_running_output_done(self, app, client):
        """Exercises the agent-side flow: pick up -> stream output -> mark done."""
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]
            cmd_r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "echo hi"},
            )
            cmd_id = cmd_r.get_json()["id"]

            raw_token = _make_agent_token(app, dev.id)
            agent_headers = {"Authorization": f"Bearer {raw_token}"}

            running = client.put(f"/api/terminal/agent/{dev.id}/commands/{cmd_id}/running", headers=agent_headers)
            assert running.status_code == 200

            # Picking it up twice should be rejected — not pending anymore.
            running_again = client.put(f"/api/terminal/agent/{dev.id}/commands/{cmd_id}/running", headers=agent_headers)
            assert running_again.status_code == 400

            output = client.post(
                f"/api/terminal/agent/{dev.id}/commands/{cmd_id}/output", headers=agent_headers,
                json={"content": "hi\r\n", "stream": "stdout"},
            )
            assert output.status_code == 200

            done = client.put(
                f"/api/terminal/agent/{dev.id}/commands/{cmd_id}/done", headers=agent_headers,
                json={"exit_code": 0},
            )
            assert done.status_code == 200

            out = client.get(f"/api/terminal/sessions/{session_id}/output", headers=auth_headers(token))
            contents = [o["content"] for o in out.get_json()["output"]]
            assert any("hi" in c for c in contents)
            assert out.get_json()["pending_commands"] == 0
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])

    def test_nonzero_exit_code_appends_footer(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        dev = _make_device(app)
        session_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            create_r = client.post("/api/terminal/sessions", headers=auth_headers(token), json={"device_id": dev.id})
            session_id = create_r.get_json()["id"]
            cmd_r = client.post(
                f"/api/terminal/sessions/{session_id}/commands", headers=auth_headers(token),
                json={"command": "exit 1"},
            )
            cmd_id = cmd_r.get_json()["id"]

            raw_token = _make_agent_token(app, dev.id)
            agent_headers = {"Authorization": f"Bearer {raw_token}"}
            client.put(f"/api/terminal/agent/{dev.id}/commands/{cmd_id}/running", headers=agent_headers)
            done = client.put(
                f"/api/terminal/agent/{dev.id}/commands/{cmd_id}/done", headers=agent_headers,
                json={"exit_code": 1},
            )
            assert done.status_code == 200

            from models.terminal import TerminalCommand
            from extensions import db
            db.session.expire_all()
            cmd = db.session.get(TerminalCommand, cmd_id)
            assert cmd.status == "error"

            out = client.get(f"/api/terminal/sessions/{session_id}/output", headers=auth_headers(token))
            contents = [o["content"] for o in out.get_json()["output"]]
            assert any("Exit code: 1" in c for c in contents)
        finally:
            _cleanup(app, device_ids=[dev.id], session_ids=[session_id] if session_id else [], user_ids=[uid])
