"""Tests for routes/scripts.py — script CRUD, run dispatch, run listing
(audits/testing_audit.md Finding C2)."""
import uuid
from conftest import create_user, delete_user, login, auth_headers


def _make_script(app, **kwargs):
    from extensions import db
    from models.script import Script
    defaults = dict(
        name=f"Script-{uuid.uuid4().hex[:6]}", file_type="ps1",
        content="Write-Host 'hi'", is_builtin=False,
    )
    defaults.update(kwargs)
    s = Script(**defaults)
    db.session.add(s)
    db.session.commit()
    return s


def _make_device(app, customer_id=None):
    from extensions import db
    from models.device import Device
    d = Device(hostname=f"host-{uuid.uuid4().hex[:6]}", customer_id=customer_id,
               platform="windows", is_online=True)
    db.session.add(d)
    db.session.commit()
    return d


def _cleanup(app, *, script_ids=(), device_ids=(), user_id=None):
    from extensions import db
    from models.script import Script, ScriptRun
    from models.device import Device
    for did in device_ids:
        ScriptRun.query.filter_by(device_id=did).delete()
        Device.query.filter_by(id=did).delete()
    for sid in script_ids:
        ScriptRun.query.filter_by(script_id=sid).delete()
        Script.query.filter_by(id=sid).delete()
    db.session.commit()
    if user_id:
        delete_user(app, user_id)


class TestListScripts:
    def test_requires_auth(self, client):
        r = client.get("/api/scripts/")
        assert r.status_code == 401

    def test_returns_scripts_without_content_field(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        script = _make_script(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/scripts/", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert any(s["id"] == script.id for s in body)
            assert all("content" not in s for s in body)
        finally:
            _cleanup(app, script_ids=[script.id], user_id=uid)

    def test_filters_by_file_type(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        ps1 = _make_script(app, file_type="ps1")
        bat = _make_script(app, file_type="bat")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/scripts/?file_type=bat", headers=auth_headers(token))
            body = r.get_json()
            ids = {s["id"] for s in body}
            assert bat.id in ids
            assert ps1.id not in ids
        finally:
            _cleanup(app, script_ids=[ps1.id, bat.id], user_id=uid)


class TestCreateScript:
    def test_requires_admin_or_technician(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/scripts/", headers=auth_headers(token),
                             json={"name": "x", "file_type": "ps1", "content": "echo hi"})
            assert r.status_code == 403
        finally:
            delete_user(app, uid)

    def test_creates_successfully(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        script_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/scripts/", headers=auth_headers(token),
                             json={"name": "My Script", "file_type": "ps1", "content": "Write-Host hi"})
            assert r.status_code == 201
            body = r.get_json()
            script_id = body["id"]
            assert body["file_type"] == "ps1"
        finally:
            _cleanup(app, script_ids=[script_id] if script_id else [], user_id=uid)

    def test_rejects_invalid_file_type(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/scripts/", headers=auth_headers(token),
                             json={"name": "x", "file_type": "exe", "content": "echo hi"})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)

    def test_rejects_oversized_content(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/scripts/", headers=auth_headers(token),
                             json={"name": "x", "file_type": "ps1", "content": "a" * (513 * 1024)})
            assert r.status_code == 400
        finally:
            delete_user(app, uid)


class TestUpdateDeleteScript:
    def test_builtin_cannot_be_edited(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        script = _make_script(app, is_builtin=True)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(f"/api/scripts/{script.id}", headers=auth_headers(token), json={"name": "new"})
            assert r.status_code == 400
        finally:
            _cleanup(app, script_ids=[script.id], user_id=uid)

    def test_builtin_cannot_be_deleted(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        script = _make_script(app, is_builtin=True)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/scripts/{script.id}", headers=auth_headers(token))
            assert r.status_code == 400
        finally:
            _cleanup(app, script_ids=[script.id], user_id=uid)

    def test_non_builtin_can_be_deleted(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        script = _make_script(app, is_builtin=False)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/scripts/{script.id}", headers=auth_headers(token))
            assert r.status_code == 200
        finally:
            _cleanup(app, script_ids=[], user_id=uid)  # already deleted


class TestRunScript:
    def test_requires_device_ids(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        script = _make_script(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/scripts/{script.id}/run", headers=auth_headers(token),
                             json={"device_ids": []})
            assert r.status_code == 400
        finally:
            _cleanup(app, script_ids=[script.id], user_id=uid)

    def test_queues_run_for_valid_device(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        script = _make_script(app)
        device = _make_device(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/scripts/{script.id}/run", headers=auth_headers(token),
                             json={"device_ids": [device.id]})
            assert r.status_code == 202
            body = r.get_json()
            assert body["queued"] == 1
        finally:
            _cleanup(app, script_ids=[script.id], device_ids=[device.id], user_id=uid)

    def test_viewer_role_forbidden(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        script = _make_script(app)
        device = _make_device(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(f"/api/scripts/{script.id}/run", headers=auth_headers(token),
                             json={"device_ids": [device.id]})
            assert r.status_code == 403
        finally:
            _cleanup(app, script_ids=[script.id], device_ids=[device.id], user_id=uid)


class TestListRuns:
    def test_requires_auth(self, client):
        r = client.get("/api/scripts/runs")
        assert r.status_code == 401

    def test_returns_paginated_items(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        script = _make_script(app)
        device = _make_device(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            run_resp = client.post(f"/api/scripts/{script.id}/run", headers=auth_headers(token),
                                    json={"device_ids": [device.id]})
            assert run_resp.status_code == 202
            r = client.get("/api/scripts/runs", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body and "pages" in body
        finally:
            _cleanup(app, script_ids=[script.id], device_ids=[device.id], user_id=uid)
