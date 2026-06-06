#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch TECHNICAL_GUIDE.md with all new changes."""

PATH = r'C:\Users\rigwe\Desktop\RemoteManagementSystem\TECHNICAL_GUIDE.md'

with open(PATH, encoding='utf-8') as f:
    content = f.read()

original_len = len(content)
applied = []

def patch(old, new, label):
    global content
    if old not in content:
        print(f'  MISS: {label}')
        return False
    content = content.replace(old, new, 1)
    applied.append(label)
    return True

# ── 1. Add MFA endpoints to Auth table (Section 3) ───────────────────────────
patch(
    '| POST | `/me/force-change-password` | JWT | Set new password + clear `must_change_password` flag |',
    '| POST | `/me/force-change-password` | JWT | Set new password + clear `must_change_password` flag |\n'
    '| PUT  | `/me/password` | JWT | Change password (current + new). Used by Profile page. |\n'
    '| POST | `/mfa/setup` | JWT | Generate provisional TOTP secret. Returns `{secret, provisioning_uri}`. Not active until /mfa/enable called. |\n'
    '| POST | `/mfa/enable` | JWT | Activate MFA. Body: `{code}`. Requires valid TOTP code. |\n'
    '| POST | `/mfa/login` | None | Second login step. Body: `{mfa_token, code}`. Returns full JWT. Rate-limited 10/min. |\n'
    '| POST | `/mfa/disable` | JWT | Disable MFA. Body: `{password}`. Requires current password. |',
    'MFA endpoints in Auth table'
)

# ── 2. Update login endpoint description ─────────────────────────────────────
patch(
    '| POST | `/login` | None | Email+password \u2192 access+refresh tokens |',
    '| POST | `/login` | None | Email+password \u2192 access+refresh tokens, OR `{"status": "mfa_required", "mfa_token": "..."}` (HTTP 200) if user has `mfa_enabled=True` |',
    'login endpoint description'
)

# ── 3. Update Tickets POST -- now requires role ───────────────────────────────
patch(
    '| POST | `/` | JWT tech/admin | Create ticket |',
    '| POST | `/` | JWT tech/admin | Create ticket (was unguarded \u2014 any JWT; now requires `technician` or `admin` role) |',
    'tickets POST role guard'
)

# ── 4. Update /api/agents/register -- rate limited ────────────────────────────
patch(
    '| POST | `/register` | None (org_token) | Register new agent, get device_id + agent_token |',
    '| POST | `/register` | None (org_token) | Register new agent, get device_id + agent_token. Rate-limited: 10/min. |',
    'agent register rate limit'
)

# ── 5. Add metrics endpoint row cap to devices table ─────────────────────────
patch(
    '| GET | `/<id>/metrics` | JWT | Historical metrics (up to 168h) |',
    '| GET | `/<id>/metrics` | JWT | Historical metrics (up to 168h). Row cap: `.limit(5000)` prevents unbounded response. |',
    'metrics row cap'
)

# ── 6. Update JWT Flow to show MFA two-step ──────────────────────────────────
patch(
    'Login:\n'
    '  POST /api/auth/login  {email, password}\n'
    '  \u2192 {access_token, refresh_token, user: {id, email, role, full_name, must_change_password}}',
    'Login (no MFA):\n'
    '  POST /api/auth/login  {email, password}\n'
    '  \u2192 {access_token, refresh_token, user: {id, email, role, full_name, must_change_password}}\n'
    '\n'
    'Login (MFA enabled):\n'
    '  POST /api/auth/login  {email, password}\n'
    '  \u2192 HTTP 200  {status: "mfa_required", mfa_token: "<short-lived JWT>"}\n'
    '  mfa_token is a 5-min TTL JWT with claim {purpose: "mfa_pending"}.\n'
    '  Cannot be used for any other API call.\n'
    '  Client must immediately call:\n'
    '  POST /api/auth/mfa/login  {mfa_token, code}\n'
    '  \u2192 {access_token, refresh_token, user: {...}}',
    'JWT Flow MFA two-step'
)

# ── 7. Update token URL storage note in JWT Flow ─────────────────────────────
patch(
    '  st.query_params["tok"]             = access_token   \u2190 persists in URL\n'
    '  st.query_params["rtok"]            = refresh_token  \u2190 persists in URL',
    '  st.query_params["tok"]             = access_token   \u2190 written once at login\n'
    '  st.query_params["rtok"]            = refresh_token  \u2190 written once at login\n'
    '  (Tokens are stripped from URL by require_auth() after first restore.\n'
    '   Session state carries them from that point. Mitigates browser history exposure.)',
    'token URL security update'
)

# ── 8. Update the "token never in URL" Known Risks row ───────────────────────
patch(
    '| JWT token theft | Short expiry (900s). HTTPS in production. Token never in URL. |',
    '| JWT token theft | Short expiry (900s). HTTPS in production. Tokens written to URL once at login, then stripped by `require_auth()` after first restore \u2014 no longer re-stamped on every page load. |',
    'token URL risk row'
)

# ── 9. Update evaluate_all_rules description ─────────────────────────────────
patch(
    '#### `evaluate_all_rules()`\n'
    '- Fetches all active alert rules\n'
    '- For each rule, queries latest `DeviceMetrics` per device in scope\n'
    '- Evaluates `metric operator threshold` (e.g., `cpu_pct > 90`)\n'
    '- Respects `cooldown_minutes` \u2014 no duplicate alert within cooldown\n'
    '- Creates `Alert` record on breach\n'
    '- Calls `send_alert_notification()` if `notification_channels.email` is set',
    '#### `evaluate_all_rules()`\n'
    '- Fetches all active alert rules\n'
    '- **N+1 fix:** collects all device IDs per rule batch, then loads all latest metrics\n'
    '  in a single subquery:\n'
    '  ```python\n'
    '  max_id_subq = db.select(func.max(DeviceMetrics.id).label("max_id"))\\\n'
    '      .where(...).group_by(DeviceMetrics.device_id).subquery()\n'
    '  latest_by_device = {m.device_id: m for m in DeviceMetrics.query.join(max_id_subq, ...).all()}\n'
    '  ```\n'
    '  Previously fired one DB query per device per rule (up to 5,000 queries/cycle).\n'
    '  Now: 1 query per rule batch regardless of device count.\n'
    '- Evaluates `metric operator threshold` (e.g., `cpu_pct > 90`)\n'
    '- Respects `cooldown_minutes` \u2014 no duplicate alert within cooldown\n'
    '- Creates `Alert` record on breach\n'
    '- Alert message now includes last-seen timestamp for offline alerts:\n'
    '  `"DESKTOP-ABC has gone offline (last seen: 2024-01-15 14:32 UTC)"`\n'
    '- Calls `send_alert_notification()` if `notification_channels.email` is set',
    'evaluate_all_rules N+1 fix'
)

# ── 10. Update sync_patch_status with maintenance window ─────────────────────
patch(
    '#### `sync_patch_status()`\n'
    '- Iterates all active `PatchPolicy` records\n'
    '- For each policy\u2019s scope (customer or global):\n'
    '  - Auto-approves `PatchRecord` rows where `status=\'pending\'` matching policy flags\n'
    '  - Respects `excluded_software` name patterns',
    '#### `sync_patch_status()`\n'
    '- Iterates all active `PatchPolicy` records\n'
    '- **Maintenance window enforcement:** checks `PatchPolicy.maintenance_window` JSON\n'
    '  (`{"day": "sunday", "time": "02:00", "duration_hours": 4}`) via helper\n'
    '  `_within_maintenance_window(window) -> bool`. If current UTC time is outside\n'
    '  the window, the policy is silently skipped for that cycle.\n'
    '- For each policy\u2019s scope (customer or global):\n'
    '  - Auto-approves `PatchRecord` rows where `status=\'pending\'` matching policy flags\n'
    '  - Respects `excluded_software` name patterns',
    'sync_patch_status maintenance window'
)

# ── 11. Add MFA methods to Dashboard API Client key methods table ─────────────
patch(
    '| `force_change_password(new_password)` | POST | `/api/auth/me/force-change-password` |',
    '| `force_change_password(new_password)` | POST | `/api/auth/me/force-change-password` |\n'
    '| `change_password(current_password, new_password)` | PUT | `/api/auth/me/password` |\n'
    '| `mfa_setup()` | POST | `/api/auth/mfa/setup` |\n'
    '| `mfa_enable(code)` | POST | `/api/auth/mfa/enable` |\n'
    '| `mfa_disable(password)` | POST | `/api/auth/mfa/disable` |\n'
    '| `mfa_login(mfa_token, code)` (static) | POST | `/api/auth/mfa/login` |',
    'MFA methods in API client table'
)

# ── 12. Add N+1 fix to Performance Database table ────────────────────────────
patch(
    '| Composite indexes | Alembic migration | `device_metrics(device_id, collected_at)`, `alerts(status, severity)`, etc. |',
    '| Composite indexes | Direct SQL (post-migration) | 7 new indexes: `ix_device_metrics_device_collected_at`, `ix_devices_customer_online`, `ix_alerts_device_status`, `ix_alerts_status_triggered_at`, `ix_patch_records_device_status`, `ix_tickets_customer_status`, `ix_script_runs_device_status` |\n'
    '| N+1 alert evaluation fix | `tasks/alert_tasks.py` | `evaluate_all_rules()` now loads all latest metrics per rule in 1 subquery. Was up to 5,000 queries/cycle (50 rules x 100 devices). |\n'
    '| Metrics endpoint row cap | `routes/devices.py` | `GET /api/devices/<id>/metrics` applies `.limit(5000)`. Was unbounded (10,080+ rows for 7-day window). |',
    'Performance DB table updates'
)

# ── 13. Update Known Risks table in Security Model ───────────────────────────
patch(
    '| Script injection | Scripts stored as plain text \u2014 reviewed before running. Runs as agent service account only. |',
    '| Script injection | Scripts stored as plain text \u2014 reviewed before running. Agent now uses `-ExecutionPolicy RemoteSigned` instead of `Bypass` \u2014 locally created scripts run, remote scripts must be signed. |\n'
    '| Error response leakage | 400/422 handlers no longer return `str(e)` to client. Detail logged server-side only; generic message returned to caller. |\n'
    '| CORS wildcard | `CORS_ORIGINS` env var (comma-separated) replaces `origins="*"`. Default: `http://localhost:8501`. Set to dashboard URL(s) in production. |',
    'Security risks table updates'
)

# ── 14. Update Production Checklist -- MFA now implemented ───────────────────
patch(
    '- [ ] Enable MFA for admin accounts (MFA secret generation is wired in the User model)',
    '- [ ] Enable MFA for all admin accounts (full TOTP implementation: setup, enable, login, disable via Profile page)\n'
    '- [ ] Set `CORS_ORIGINS` to dashboard URL (replaces wildcard `origins="*"`)\n'
    '- [ ] Set `SUPERADMIN_PASSWORD` in `.env` (now required -- API will not start without it)',
    'Production checklist MFA'
)

# ── 15. Update Env Variables table ───────────────────────────────────────────
patch(
    '| `SUPERADMIN_EMAIL` | \u2014 | `superadmin@rmm.local` | Email for the auto-seeded superadmin account |\n'
    '| `SUPERADMIN_PASSWORD` | \u2014 | `SuperAdmin@RMM1` | Password for the auto-seeded superadmin account. Change in production. |',
    '| `SUPERADMIN_EMAIL` | \u2014 | `superadmin@rmm.local` | Email for the auto-seeded superadmin account |\n'
    '| `SUPERADMIN_PASSWORD` | \u2713 | \u2014 | **Now required at startup.** Min 10 chars. API raises `RuntimeError` if missing or too short. |\n'
    '| `CORS_ORIGINS` | \u2014 | `http://localhost:8501` | Comma-separated allowed CORS origins. Set to dashboard URL(s) in production. |\n'
    '| `DB_PASSWORD` | \u2014 | `changeme` | PostgreSQL password used in `docker-compose.yml` only. |',
    'env vars table updates'
)

# ── 16. Add MFA section to Authentication chapter ────────────────────────────
patch(
    '### Agent Token Flow',
    '### MFA Flow\n'
    '\n'
    '```\n'
    'Setup:\n'
    '  POST /api/auth/mfa/setup\n'
    '  \u2192 {secret, provisioning_uri}  (provisional -- not active yet)\n'
    '\n'
    'Enable (after QR scan):\n'
    '  POST /api/auth/mfa/enable  {code: "123456"}\n'
    '  \u2192 {message: "MFA enabled"}  -- sets mfa_enabled=True on User\n'
    '\n'
    'Login with MFA:\n'
    '  POST /api/auth/login  {email, password}\n'
    '  \u2192 {status: "mfa_required", mfa_token: "<5-min JWT>"}  (HTTP 200)\n'
    '  mfa_token JWT claims: {purpose: "mfa_pending", sub: user_id}\n'
    '  Cannot be used for any endpoint except /mfa/login.\n'
    '\n'
    '  POST /api/auth/mfa/login  {mfa_token, code}\n'
    '  Rate-limited: 10/min\n'
    '  \u2192 {access_token, refresh_token, user: {...}}  (full session)\n'
    '\n'
    'Disable:\n'
    '  POST /api/auth/mfa/disable  {password}\n'
    '  \u2192 {message: "MFA disabled"}  -- requires current password for confirmation\n'
    '```\n'
    '\n'
    '**Dashboard flow:**\n'
    '- `login()` in `dashboard/utils/auth.py` returns `"ok"` / `"mfa_required"` / `"error"` (not bool).\n'
    '- On `mfa_required`: stores `mfa_token` in `st.session_state["mfa_pending_token"]`.\n'
    '- `app.py` route block checks `mfa_pending_token` before `access_token` \u2014 shows `show_mfa_step()` full-screen form.\n'
    '- Back button clears `mfa_pending_token` and returns to login.\n'
    '\n'
    '**QR code generation:** `qrcode[pil]==8.0` in `dashboard/requirements.txt`.\n'
    '\n'
    '---\n'
    '\n'
    '### Agent Token Flow',
    'MFA flow section'
)

# ── 17. Add Docker section after env vars ─────────────────────────────────────
patch(
    'Generate secrets:\n'
    '```bash\n'
    'python -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY, JWT_SECRET_KEY\n'
    'python -c "import secrets; print(secrets.token_hex(24))"   # ORG_REGISTRATION_TOKEN\n'
    '```',
    'Generate secrets:\n'
    '```bash\n'
    'python -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY, JWT_SECRET_KEY\n'
    'python -c "import secrets; print(secrets.token_hex(24))"   # ORG_REGISTRATION_TOKEN\n'
    '```\n'
    '\n'
    '---\n'
    '\n'
    '## 13. Docker Deployment\n'
    '\n'
    '### docker-compose.yml (project root)\n'
    '\n'
    '6 services:\n'
    '\n'
    '| Service | Image | Command |\n'
    '|---------|-------|---------|\n'
    '| `db` | `postgres:16-alpine` | Postgres with health check |\n'
    '| `redis` | `redis:7-alpine` | Redis with health check |\n'
    '| `api` | Built from `api/Dockerfile` | `flask db upgrade && python app.py` |\n'
    '| `celery_worker` | Same as `api` | `celery -A tasks.celery_app worker --pool=solo -l info` |\n'
    '| `celery_beat` | Same as `api` | `celery -A tasks.celery_app beat -l info` |\n'
    '| `dashboard` | Built from `dashboard/Dockerfile` | `streamlit run app.py` |\n'
    '\n'
    '### Dockerfiles\n'
    '\n'
    '- `api/Dockerfile` \u2014 `python:3.11-slim` + `libpq-dev gcc` (for psycopg2 compile)\n'
    '- `dashboard/Dockerfile` \u2014 `python:3.11-slim`\n'
    '\n'
    '### Usage\n'
    '\n'
    '```bash\n'
    '# Start all services\n'
    'docker-compose up -d\n'
    '\n'
    '# View API logs\n'
    'docker-compose logs -f api\n'
    '\n'
    '# Stop (preserves data volume)\n'
    'docker-compose down\n'
    '\n'
    '# Stop + delete all data\n'
    'docker-compose down -v\n'
    '\n'
    '# Rebuild after code changes\n'
    'docker-compose build api dashboard && docker-compose up -d\n'
    '```\n'
    '\n'
    '### Environment note\n'
    '\n'
    'When using Docker Compose, `DATABASE_URL` must use `@db:5432` (service name), not `@localhost:5432`.\n'
    '`REDIS_URL` / `CELERY_BROKER_URL` must use `redis://redis:6379/...`.\n'
    '`SUPERADMIN_PASSWORD` is required \u2014 API container will exit immediately if missing.\n'
    '\n'
    '### Security hardening applied at startup (`api/app.py`)\n'
    '\n'
    '`_validate_env()` runs at import time and raises `RuntimeError` if:\n'
    '- `SECRET_KEY` or `JWT_SECRET_KEY` < 32 characters\n'
    '- `SUPERADMIN_PASSWORD` unset or < 10 characters\n'
    '- `ORG_REGISTRATION_TOKEN` is the placeholder value `"replace-with-a-unique-org-token"`\n'
    '\n'
    'Additional hardening:\n'
    '- `X-Request-ID` header: `before_request` generates UUID if not present; echoed on all responses.\n'
    '- Dev mode warning: API logs WARNING on startup if `FLASK_ENV != "production"`.\n'
    '- CORS restricted via `CORS_ORIGINS` env var (replaces `origins="*"`).\n'
    '- 400/422 error handlers: detail logged server-side only, generic message returned to client.',
    'Docker section'
)

# ── 18. Update TOC ────────────────────────────────────────────────────────────
patch(
    '12. [Environment Variables Reference](#12-environment-variables-reference)',
    '12. [Environment Variables Reference](#12-environment-variables-reference)\n'
    '13. [Docker Deployment](#13-docker-deployment)',
    'TOC Docker entry'
)

# ── 19. Add token URL note to dashboard performance table ─────────────────────
patch(
    '| Graceful degradation | `st.warning` instead of `st.stop()` \u2014 page stays interactive on partial failure |',
    '| Graceful degradation | `st.warning` instead of `st.stop()` \u2014 page stays interactive on partial failure |\n'
    '| Token URL security | `require_auth()` strips `?tok=`/`?rtok=` from URL after first restore. Tokens no longer re-stamped on every page load \u2014 reduces browser history exposure. |',
    'token URL dashboard perf note'
)

# ── 20. Add HTTPS warning to dashboard client section ─────────────────────────
patch(
    '### Cache Strategy',
    '### HTTPS Warning\n'
    '\n'
    '`api_client.py` logs a `WARNING` at import time if `API_BASE_URL` uses `http://` pointing '
    'to a non-localhost host. This warns that tokens and data will be transmitted unencrypted.\n'
    '\n'
    '### Cache Strategy',
    'HTTPS warning note'
)

# Save
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'SAVED. {len(applied)} patches applied. Size: {len(content)} (was {original_len})')
print('Applied:', applied)
missed = [p for p in ['MFA endpoints in Auth table', 'login endpoint description',
    'tickets POST role guard', 'agent register rate limit', 'metrics row cap',
    'JWT Flow MFA two-step', 'token URL security update', 'token URL risk row',
    'evaluate_all_rules N+1 fix', 'sync_patch_status maintenance window',
    'MFA methods in API client table', 'Performance DB table updates',
    'Security risks table updates', 'Production checklist MFA', 'env vars table updates',
    'MFA flow section', 'Docker section', 'TOC Docker entry',
    'token URL dashboard perf note', 'HTTPS warning note'] if p not in applied]
if missed:
    print('MISSED:', missed)
