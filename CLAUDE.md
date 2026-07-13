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
- Post-ship: Scan false-positive fixes — Windows detection now requires 2+ ports open (445+139 or 445+3389) instead of any single port, preventing routers/NAS with only SMB from being misidentified; router/gateway hostnames (fritz.box, router, gateway, modem, etc.) are included in `discovered_hosts` for display but never persisted as agentless device records; `_upsert_agentless_host` gained 3rd lookup stage: bare-hostname match (case-insensitive, strips .fritz.box/.local suffix) to deduplicate agent devices with multiple network adapters reporting different MACs per interface
- Post-ship: Clickable Device Health Map — cards in `01_Dashboard.py` are now `st.button()` elements styled as white cards (CSS scoped to `section[data-testid="stMain"]` to avoid affecting sidebar); clicking navigates via `st.switch_page("pages/04_Devices.py")` + `st.session_state["_nav_device"]`; Devices page reads session state on load, pre-fills search with device hostname and shows info banner; Refresh button uses `type="primary"` to remain unaffected by card CSS
- Post-ship: Metrics History 7-day fallback — `04_Devices.py` retries with `hours=168` when 24h window returns empty; shows `st.info` banner with reading count and age estimate; chart title updates to "7-day usage history (agent offline)"; still shows "No metric history available" only when 7-day window is also empty
- Post-ship: Software Patches agentless note — green left-border info strip added below "Online Devices" label in `13_Software_Patches.py` explaining that mobile/agentless devices are excluded because they have no agent to report software inventory
- Post-ship: AI Assistant — context-aware chat widget embedded in all 19 dashboard pages; `api/routes/assistant.py` blueprint registered at `/api/assistant`; `dashboard/utils/ai_assistant.py` renders sidebar widget; uses Anthropic Claude Haiku 4.5 (`anthropic>=0.40.0`); JWT role-aware system prompts (viewer/technician/admin/superadmin/client); rate-limited 30 req/min via Flask-Limiter; page-specific descriptions + live context injection + suggested quick actions; session-state chat history; onboarding auto-open on Overview on first login; graceful degradation if Anthropic API is down; `ANTHROPIC_API_KEY`, `AI_ASSISTANT_MODEL`, `AI_ASSISTANT_ENABLED` env vars; API key server-side only — never exposed to dashboard
- Commercial Audit (Track A — Security): Agent multi-customer routing — `customer_id` field in `AgentRegisterSchema` + registration API + `agent/heartbeat.py` + `agent/config.ini`; DPAPI token encryption — `_protect_token`/`_unprotect_token` in `agent/rmm_agent.py` with graceful plaintext migration; Alembic migration `i0j1k2l3m4n5` adding `ix_devices_customer_status` composite index; OpenAPI 3.0 spec at `api/swagger_spec.py` (47 paths, 16 tags) served via SwaggerUI CDN at `/api/docs` + `/api/openapi.json` (`api/routes/docs.py`); pagination added to `alerts`, `admin/users`, `automation/profiles`, `customers/groups` list endpoints; Redis SET NX distributed lock in `evaluate_all_rules` preventing thundering herd; webhook dispatch in `api/utils/webhook.py` — Slack Block Kit, MS Teams MessageCard, generic JSON POST on alert fire
- Commercial Audit (Track C — Stability): Redis query cache `api/utils/cache.py` (`cache_get`/`cache_set`/`cache_delete`); dashboard summary cached 30s per-tenant; platform_counts cached 60s; terminal `create_session` + script `run_script` enforce `device.customer_id` ownership for client-role JWTs; `api/tasks/backup_tasks.py` — nightly pg_dump → gzip, prunes backups older than `BACKUP_RETAIN_DAYS`, registered in Celery beat (86400s); `api/tasks/billing_tasks.py` — daily task generates draft invoices for customers where `billing_day == today`, idempotent; Customer model gains `billing_day`, `per_device_rate`, `tax_rate` columns (migration `j1k2l3m4n5o6`)
- Commercial Audit (Track B — Features): Script `run_script` emits `AuditLog` entry (script name, device count, device IDs); GDPR Art. 20 export — `GET /api/admin/users/<id>/gdpr-export` returns profile + audit log + ticket comments; GDPR Art. 17 delete — `DELETE /api/admin/users/<id>/gdpr-delete` anonymizes PII, scrubs IPs, nulls comment author emails; configurable SLA policies — `api/models/sla_policy.py` + migration `k2l3m4n5o6p7` (creates table + seeds 4 global defaults); CRUD at `/api/sla-policies/`; `api/routes/tickets.py` `create_ticket` now calls `_sla_resolution_hours()` — customer-specific policy → global policy → hardcoded fallback

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
- `api/utils/cache.py` — `cache_get(key)` / `cache_set(key, value, ttl)` / `cache_delete(key)`. Redis-backed JSON cache. Used by dashboard summary (30s TTL) and platform_counts (60s TTL). Silently no-ops if Redis is unavailable.
- `api/utils/webhook.py` — `dispatch_alert_webhooks(channels, rule_name, device_hostname, message, severity)`. Sends to Slack (Block Kit), Teams (MessageCard), generic JSON POST. Called from `alert_tasks.evaluate_all_rules` when `notification_channels` contains `slack`/`teams`/`webhook` keys. Never raises — logs errors silently.
- `api/utils/oui.py` — static OUI (MAC vendor) lookup, 500+ entries. `lookup_vendor(mac)` → vendor string. Used by network scan task to identify Apple/Samsung/Google/etc. devices.
- `api/routes/docs.py` — serves `/api/docs` (SwaggerUI HTML, CDN, brand green topbar) and `/api/openapi.json` (full 47-path spec). No extra pip deps.
- `api/routes/sla_policies.py` — SLA policy CRUD at `/api/sla-policies/`. Global defaults (customer_id=NULL) seeded by migration; cannot be deleted. Per-customer overrides take precedence in `_sla_resolution_hours()` in `tickets.py`.
- `api/routes/admin.py` — `GET /api/admin/users/<id>/gdpr-export` (GDPR Art. 20 data export) and `DELETE /api/admin/users/<id>/gdpr-delete` (Art. 17 anonymization — irreversible).
- `api/tasks/backup_tasks.py` — `backup_database` Celery task: finds pg_dump, runs it, gzip-compresses to `BACKUP_DIR`, prunes files older than `BACKUP_RETAIN_DAYS` (default 7). Runs daily via Celery beat.
- `api/tasks/billing_tasks.py` — `generate_recurring_invoices` Celery task: runs daily, finds customers where `billing_day == today` and `per_device_rate > 0`, generates draft invoices for prior calendar month. Idempotent — skips if invoice for that period already exists.

## Build Order (Phases)
1. ✓ Agent Core → 2. ✓ API Foundation → 3. ✓ Dashboard UI → 4. ✓ Scripts →
5. ✓ Automation Profiles → 6. ✓ Patch Management → 7. ✓ Alerts → 8. ✓ Tickets →
9. ✓ Reports + Billing + Polish
