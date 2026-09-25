"""Automation profile + scheduled run route tests (audits/testing_audit.md
Finding C2 — automation.py had zero test coverage before this file)."""
from unittest.mock import patch
from conftest import create_user, delete_user, login, auth_headers


def _cleanup(app, *, user_ids=(), profile_ids=(), run_ids=(), device_ids=()):
    from extensions import db
    from models.automation import AutomationProfile, ScheduledTaskRun
    from models.device import Device
    for rid in run_ids:
        ScheduledTaskRun.query.filter_by(id=rid).delete()
    for pid in profile_ids:
        AutomationProfile.query.filter_by(id=pid).delete()
    for did in device_ids:
        Device.query.filter_by(id=did).delete()
    db.session.commit()
    for uid in user_ids:
        try:
            delete_user(app, uid)
        except Exception:
            pass


def _make_profile(app, **kwargs):
    from extensions import db
    from models.automation import AutomationProfile
    import uuid
    defaults = dict(name=f"Profile-{uuid.uuid4().hex[:6]}", is_active=True)
    defaults.update(kwargs)
    p = AutomationProfile(**defaults)
    db.session.add(p)
    db.session.commit()
    return p


def _make_device(app):
    from extensions import db
    from models.device import Device
    import uuid
    d = Device(hostname=f"host-{uuid.uuid4().hex[:6]}", platform="windows", is_online=True)
    db.session.add(d)
    db.session.commit()
    return d


class TestListProfiles:
    def test_requires_auth(self, client):
        r = client.get("/api/automation/profiles")
        assert r.status_code == 401

    def test_viewer_can_list(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        profile = _make_profile(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/automation/profiles", headers=auth_headers(token))
            assert r.status_code == 200
            body = r.get_json()
            assert "items" in body and "pages" in body
            assert any(p["id"] == profile.id for p in body["items"])
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id])

    def test_filters_by_customer_id(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        p1 = _make_profile(app, customer_id="cust-a")
        p2 = _make_profile(app, customer_id="cust-b")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/automation/profiles?customer_id=cust-a", headers=auth_headers(token))
            ids = [p["id"] for p in r.get_json()["items"]]
            assert p1.id in ids
            assert p2.id not in ids
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[p1.id, p2.id])


class TestCreateProfile:
    def test_requires_admin_or_technician(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/automation/profiles", headers=auth_headers(token), json={"name": "X"})
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid])

    def test_technician_creates_profile(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        created_id = None
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/automation/profiles", headers=auth_headers(token),
                json={"name": "Weekly Cleanup", "schedule_type": "weekly"},
            )
            assert r.status_code == 201
            body = r.get_json()
            created_id = body["id"]
            assert body["name"] == "Weekly Cleanup"
            assert body["is_active"] is True
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[created_id] if created_id else [])

    def test_rejects_missing_name(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post("/api/automation/profiles", headers=auth_headers(token), json={})
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid])

    def test_rejects_invalid_schedule_type(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.post(
                "/api/automation/profiles", headers=auth_headers(token),
                json={"name": "Bad", "schedule_type": "hourly-ish"},
            )
            assert r.status_code == 400
        finally:
            _cleanup(app, user_ids=[uid])


class TestGetUpdateDeleteProfile:
    def test_get_missing_profile_404s(self, app, client):
        uid, email, pw = create_user(app, role="viewer")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get("/api/automation/profiles/does-not-exist", headers=auth_headers(token))
            assert r.status_code == 404
        finally:
            _cleanup(app, user_ids=[uid])

    def test_update_profile(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        profile = _make_profile(app, name="Old Name")
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.put(
                f"/api/automation/profiles/{profile.id}", headers=auth_headers(token),
                json={"name": "New Name", "is_active": False},
            )
            assert r.status_code == 200
            body = r.get_json()
            assert body["name"] == "New Name"
            assert body["is_active"] is False
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id])

    def test_delete_requires_admin(self, app, client):
        uid, email, pw = create_user(app, role="technician")
        profile = _make_profile(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/automation/profiles/{profile.id}", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id])

    def test_admin_deletes_profile(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        profile = _make_profile(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/automation/profiles/{profile.id}", headers=auth_headers(token))
            assert r.status_code == 200
            from extensions import db
            from models.automation import AutomationProfile
            assert db.session.get(AutomationProfile, profile.id) is None
        finally:
            _cleanup(app, user_ids=[uid])


class TestRunProfileNow:
    def test_enqueues_task(self, app, client):
        uid, email, pw = create_user(app, role="admin")
        profile = _make_profile(app)
        try:
            token = login(client, email, pw).get_json()["access_token"]
            with patch("tasks.automation_tasks.enqueue_profile_run.delay") as mock_delay:
                mock_delay.return_value.id = "fake-celery-task-id"
                r = client.post(f"/api/automation/profiles/{profile.id}/run", headers=auth_headers(token))
            assert r.status_code == 202
            assert r.get_json()["celery_task_id"] == "fake-celery-task-id"
            mock_delay.assert_called_once_with(profile.id)
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id])

    def test_skips_duplicate_recent_run(self, app, client):
        from extensions import db
        from models.automation import ScheduledTaskRun
        from datetime import datetime, timezone
        uid, email, pw = create_user(app, role="admin")
        profile = _make_profile(app)
        dev = _make_device(app)
        run = ScheduledTaskRun(profile_id=profile.id, device_id=dev.id, status="queued", started_at=datetime.now(timezone.utc))
        db.session.add(run)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            with patch("tasks.automation_tasks.enqueue_profile_run.delay") as mock_delay:
                r = client.post(f"/api/automation/profiles/{profile.id}/run", headers=auth_headers(token))
            assert r.status_code == 200
            assert "already queued" in r.get_json()["message"]
            mock_delay.assert_not_called()
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id], run_ids=[run.id], device_ids=[dev.id])


class TestListAndDeleteRuns:
    def test_list_runs_filtered_by_profile(self, app, client):
        from extensions import db
        from models.automation import ScheduledTaskRun
        uid, email, pw = create_user(app, role="viewer")
        profile = _make_profile(app)
        dev = _make_device(app)
        run = ScheduledTaskRun(profile_id=profile.id, device_id=dev.id, status="success")
        db.session.add(run)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.get(f"/api/automation/runs?profile_id={profile.id}", headers=auth_headers(token))
            assert r.status_code == 200
            ids = [x["id"] for x in r.get_json()["items"]]
            assert run.id in ids
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id], run_ids=[run.id], device_ids=[dev.id])

    def test_delete_run_requires_technician_or_admin(self, app, client):
        from extensions import db
        from models.automation import ScheduledTaskRun
        uid, email, pw = create_user(app, role="viewer")
        profile = _make_profile(app)
        dev = _make_device(app)
        run = ScheduledTaskRun(profile_id=profile.id, device_id=dev.id, status="success")
        db.session.add(run)
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/automation/runs/{run.id}", headers=auth_headers(token))
            assert r.status_code == 403
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id], run_ids=[run.id], device_ids=[dev.id])

    def test_clear_queued_runs_bulk_deletes(self, app, client):
        from extensions import db
        from models.automation import ScheduledTaskRun
        uid, email, pw = create_user(app, role="admin")
        profile = _make_profile(app)
        dev = _make_device(app)
        r1 = ScheduledTaskRun(profile_id=profile.id, device_id=dev.id, status="queued")
        r2 = ScheduledTaskRun(profile_id=profile.id, device_id=dev.id, status="queued")
        r3 = ScheduledTaskRun(profile_id=profile.id, device_id=dev.id, status="success")
        db.session.add_all([r1, r2, r3])
        db.session.commit()
        try:
            token = login(client, email, pw).get_json()["access_token"]
            r = client.delete(f"/api/automation/runs/clear-queued?profile_id={profile.id}", headers=auth_headers(token))
            assert r.status_code == 200
            assert "2" in r.get_json()["message"]
            remaining = ScheduledTaskRun.query.filter_by(profile_id=profile.id).all()
            assert len(remaining) == 1
            assert remaining[0].status == "success"
        finally:
            _cleanup(app, user_ids=[uid], profile_ids=[profile.id], run_ids=[r3.id], device_ids=[dev.id])
