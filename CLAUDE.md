# RMM Project — Claude Code Instructions

## Project
NinjaOne-style Remote Monitoring & Management system.
Stack: Flask API + Streamlit dashboard + Python agent + PostgreSQL + Redis/Celery.

## Build Status
**ALL PHASES COMPLETE** (Phases 1–9 + A/B/C optimization pass + post-ship fixes)
- Phase A: API speed/reliability (indexes, batch queries, pool sizing, error handlers, logging, Celery retry)
- Phase B: Dashboard reliability (session reuse, retry/backoff, token refresh, cache_data, spinners, graceful degradation)
- Phase C: Agent reliability (non-blocking CPU, bounded scans, exponential backoff, local task queue, structured logging)
- Post-ship: Org enrollment token exposed in Admin panel; refresh token persisted in `?rtok=` URL param to survive page reloads
- Post-ship: Force password change on first login — `must_change_password` column on `User`; admin checkbox when creating/editing users; `dashboard/app.py` intercepts login and shows full-screen change-password form before granting dashboard access; API endpoint `POST /api/auth/me/force-change-password`
- Post-ship: Software Patches winget fix — `_get_winget_software()` in `agent/collector.py` now skips non-ASCII progress-bar lines (Unicode block chars █▒░) and properly detects the data table separator; `_clean()` sanitizer added to `dashboard/pages/13_Software_Patches.py` strips U+2500–U+259F block/box-drawing chars before HTML render
- Post-ship: WiFi/Agentless device support — three new Device columns (`is_agentless`, `device_type`, `vendor`; `customer_id` now nullable); Alembic migration `f3e2d1c0b9a8`; OUI vendor lookup (`api/utils/oui.py`); network scan Celery task with concurrent ICMP ping sweep (`api/tasks/network_tasks.py`); `ping_agentless_devices` beat task (300s); new API endpoints (`GET /api/devices/platform_counts`, `POST /api/devices/<id>/ping_check`, `POST /api/network/agentless_devices`, `GET /api/admin/server_ips`); Devices page rewritten with 7 OS filter tabs (All/Windows/macOS/Linux/Android/iOS/Agentless); Network Discovery page rewritten with polling + Save All; Admin page shows server LAN IPs + agent deploy instructions; `agent/setup_agent.py` for one-command WiFi deployment
- Post-ship: Superadmin role — `api/utils/superadmin.py` seeds one permanent `superadmin` account at every API startup; cannot be deleted/modified via API; `api/reset_superadmin.py` CLI for emergency password reset; all 9 route files have superadmin bypass in `_require_role()`; Admin page guards updated; role pill is purple (`#7C3AED`)
- Post-ship: Agentless device identification enhancements — `_probe_platform(ip)` in `api/tasks/network_tasks.py` probes 6 ports (62078/iOS, 5555/Android, 445|3389|139/Windows, 548/macOS, 22/Linux) when OUI lookup fails; `_get_hostname(ip)` reverse-DNS lookup populates device hostname; `_upsert_agentless_host` now accepts `hostname` param; agentless device rows in `04_Devices.py` have Edit button (inline form: hostname, platform, device_type) as workaround for randomized-MAC devices; Streamlit duplicate widget key bug fixed via `tab_key` param on `_render_agent_row`/`_render_agentless_row`; `delete_device(device_id)` added to `api_client.py`
- Post-ship: Android/duplicate scan fixes — `_guess_platform_from_hostname(hostname)` added as 3rd detection fallback (after OUI + port probe); matches 50+ Android keywords including Samsung model numbers (Galaxy, S10–S24, Note, A-series, Fold, Flip); rDNS lookup now runs before port probe so hostname available for all fallbacks; `_upsert_agentless_host` IP fallback searches ALL devices (not just agentless) preventing duplicate agentless records for agent-managed Windows PCs; upsert now upgrades `platform`/`device_type` on existing agentless records when re-scan detects better info; Software Patches page excludes agentless devices from device dropdown

## State File
Check `.claude/state.md` at session start for current phase and context.

## Critical Rules
- Never commit `.env` — use `.env.example`
- All file reads/writes: `encoding='utf-8'`
- All paths: use `pathlib.Path`
- Windows subprocesses: `CREATE_NO_WINDOW` flag always
- Celery on Windows: `--pool=solo`
- One bug fix at a time, verified before moving on

## Services & Ports
- Flask API: http://localhost:5000
- Streamlit dashboard: http://localhost:8501
- PostgreSQL: localhost:5432 (db: rmmdb, user: rmm_app)
- Redis/Memurai: localhost:6379

## Kill by port (Windows)
```
netstat -ano | findstr :<PORT>
taskkill /F /PID <PID>
```

## Start Services
```
# API
cd api ; python app.py

# Celery worker
cd api ; celery -A tasks.celery_app worker --pool=solo -l info

# Celery beat
cd api ; celery -A tasks.celery_app beat -l info

# Dashboard
cd dashboard ; streamlit run app.py

# Agent (run as admin for patch management)
cd agent ; python rmm_agent.py
```

## Brand
Primary: #407E3C | White: #FFFFFF | Accent: #5a9e56
Apply to all UI. Dark sidebar, white text, green accents.

## Key Utilities (non-obvious, know before touching)
- `api/utils/builtin_scripts.py` — defines 7 PowerShell built-in scripts + `ensure_builtin_scripts()` (called at API startup). Maintenance tasks (defrag, clean_temp, etc.) are dispatched as ScriptRun records pointing to these. No separate task table.
- `api/utils/notifications.py` — SMTP email alerts. Silently no-ops if `SMTP_HOST` not set in `.env`.
- `api/reports/` — CSV output directory for generated reports. Created at runtime. `Report.file_path` stores the path; dashboard reads bytes directly for download.
- `dashboard/utils/nav.py` — shared sidebar nav component used by all 16 pages via `render_sidebar()`.
- `dashboard/utils/api_client.py` — `RMMClient` class. Uses `st.session_state["_rmm_client"]` session reuse + 3-attempt retry backoff + 401 auto-refresh.
- `dashboard/utils/auth.py` — `require_auth()` re-stamps `?tok=` + `?rtok=` on every page load so F5 restores both access and refresh tokens.
- `api/routes/admin.py` — `GET /api/admin/org-token` (admin JWT only) returns `ORG_REGISTRATION_TOKEN` for display in Admin panel. `POST /api/users` + `PUT /api/users/<id>` accept `must_change_password` bool.
- `api/routes/auth.py` — `POST /api/auth/me/force-change-password` (JWT required) — sets new password and clears `must_change_password` flag.
- `dashboard/app.py` — routing block checks `st.session_state["user"]["must_change_password"]` after login; if True shows `show_force_change_password()` full-screen form before any other page.
- `agent/collector.py` — `_get_winget_software()` skips non-ASCII lines (winget progress bars) and locates the separator line to find the real data table. `_get_registry_software()` bounded at 20s.
- `api/utils/oui.py` — static OUI (MAC vendor) lookup, 500+ entries. `lookup_vendor(mac)` → vendor string. Used by network scan task to identify Apple/Samsung/Google/etc. devices.
- `api/tasks/network_tasks.py` — `run_network_scan(scan_id)` concurrent ICMP sweep + ARP MAC lookup + OUI vendor ID + agentless device upsert. `ping_agentless_devices()` beat task — pings all `is_agentless=True` devices every 5 min.
- `agent/setup_agent.py` — CLI: `python setup_agent.py <server_ip> <org_token>`. Patches config.ini for WiFi deployment; clears device_id/agent_token for clean re-registration.
- `api/utils/superadmin.py` — `ensure_superadmin()` auto-seeds one `superadmin` account at API startup. Credentials from env vars `SUPERADMIN_EMAIL` (default `superadmin@rmm.local`) and `SUPERADMIN_PASSWORD` (default `SuperAdmin@RMM1`). Called from `create_app()`.
- `api/reset_superadmin.py` — Emergency CLI password reset: `python reset_superadmin.py <new_password>` (min 10 chars). Resets superadmin password without needing a JWT token.

## Build Order (Phases)
1. ✓ Agent Core → 2. ✓ API Foundation → 3. ✓ Dashboard UI → 4. ✓ Scripts →
5. ✓ Automation Profiles → 6. ✓ Patch Management → 7. ✓ Alerts → 8. ✓ Tickets →
9. ✓ Reports + Billing + Polish
