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
- Post-ship (Tier 1 — Stability): Celery app context leak fix — `_get_app()` singleton added to 8 task files (automation, billing, email, maintenance, network, patch, report, ticket); replaces per-invocation `create_app()` that caused DB pool exhaustion under load; CI enhanced with postgres+redis services, coverage upload, Docker build gate on main, TypeScript type-check; `.gitattributes` added with `eol=lf` normalization for all text files
- Post-ship (Tier 2 — Tests): 80 new tests added — `test_tickets.py`, `test_alerts.py`, `test_devices.py`, `test_cache.py`; total 102/102 passing; `conftest.py` force-sets `ORG_REGISTRATION_TOKEN`; CI runs full suite with postgres+redis service containers
- Post-ship (Tier 3 — Production Hardening): Sentry SDK (`sentry-sdk[flask]>=2.0.0`) integrated in `api/app.py` — no-op when `SENTRY_DSN` unset, `traces_sample_rate=0.05`, `send_default_pii=False`; login rate limit tightened from 10/min to 5/min (`POST /api/auth/login`); `SENTRY_DSN` stub added to `.env.example`
- Post-ship (Tier 4 — Cross-Platform Agent): `agent/collector.py` refactored to dispatch on `sys.platform` — macOS uses `sysctl`/`system_profiler`/`softwareupdate`/`brew`, Linux uses `/proc/cpuinfo`/`dmidecode`/`apt`/`dnf`/`yum`/`pacman`/`dpkg`; all Windows-specific code guarded by `_PLATFORM == "win32"`; `agent/build.py` added — PyInstaller single-file binary builder, auto-detects platform, outputs `dist/rmm_agent[.exe]` + copies `config.ini` template
- Post-ship (Tier 5 — Screenshot Pipeline): `agent/screenshot.py` — cross-platform screen capture (PIL.ImageGrab on Windows/macOS, scrot/gnome-screenshot on Linux), max 1920px, JPEG quality 72, returns None silently on headless; `agent/heartbeat.py` gains `send_screenshot(jpeg_bytes)` — POST raw bytes to `POST /api/agents/<id>/screenshot`; `agent/rmm_agent.py` captures every 300s (configurable via `[agent] screenshot_interval`); API: `POST /api/agents/<id>/screenshot` (agent auth, 5MB cap, saves to `api/screenshots/<device_id>.jpg`), `GET /api/devices/<id>/screenshot` (JWT, streams via `send_file`); `Pillow>=10.0.0` added to `agent/requirements.txt`
- Post-ship (Auto-resolve alerts): `evaluate_all_rules` now resolves open alerts when metric drops back below threshold; heartbeat resolves open offline alerts when device reconnects; fixes indefinite alert pile-up; alert storm fix — split `active_alert_map` into `open_alert_map` (no time filter) + `resolved_alert_map` (cooldown after recovery) to prevent re-fire of alerts older than cooldown_minutes
- Post-ship (Terminal improvements): Terminal output polling — React `TerminalPage.tsx` polls `GET /terminal/sessions/<id>/output?after=<last_id>` every 2s; pending-command indicator — `GET /terminal/sessions/<id>/output` returns `pending_commands` count; `14_Terminal.py` shows amber blinking indicator when commands queued but agent offline; terminal token rotation — `terminal_worker.update_token()` called from `rmm_agent` on rotation; session seq reset on auto-close prevents stale buffer on next connect
- Post-ship (Performance): gzip compression via `flask-compress` (all JSON >500B); Waitress 16 threads; `api/utils/jwt_cache.py` — TTLCache(512, 60s) monkey-patch skips HMAC verify for repeated tokens (60-86ms vs 135-177ms); raw JSON cache (`cache_get_raw`/`cache_set_raw`) for `health_map` — returns pre-serialized `Response` bypassing double serialization; PgBouncer support — route `DATABASE_URL` through port 6432, `pool_pre_ping` disabled; cache pre-warm at API startup; `dashboard/utils/cached_calls.py` — `st.cache_data` wrappers for all major read endpoints; `01_Dashboard.py` and `14_Terminal.py` use `@st.fragment` auto-refresh instead of `time.sleep`+rerun; `ThreadPoolExecutor` parallel API calls in `04_Devices.py` and `10_Admin.py`; PostgreSQL `work_mem` raised to 16MB for `rmm_app`
- Post-ship (IoT/MQTT/SNMP): `agent/iot_agent.py` — IoT sensor agent for Raspberry Pi/Linux SBC; reads from `/sys/class/hwmon`, DHT11/DHT22, BME680, PIR, door switch; all sensor libs optional; `api/routes/sensors.py` blueprint at `/api/sensors/`; `SensorReading` model + Alembic migration `l3m4n5o6p7q8`; `api/tasks/mqtt_tasks.py` — Celery MQTT subscription task (no-op when `MQTT_HOST` unset); `api/tasks/snmp_tasks.py` — per-device SNMP polling; `dashboard/pages/18_IoT_Sensors.py` — sensor charts page; `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TOPIC_PREFIX`, `SNMP_TIMEOUT` env vars added
- Post-ship (React Frontend): Full TypeScript/React 19/Vite 8 frontend in `frontend/` — 19 pages matching all Streamlit pages; TanStack Query for server state; React Router 7; Tailwind CSS; axios; CORS configured via `CORS_ORIGINS` + `DASHBOARD_URL` env var; `frontend/src/pages/` contains all page components; `frontend/src/api/` has axios client; production build via `npm run build` → `frontend/dist/`; TypeScript type-check in CI
- Post-ship (AI Assistant modernization): Removed robot/wave emojis; toggle uses Material icons (`:material/auto_awesome:` open, `:material/close:` close); Send/Clear use `:material/send:`/`:material/delete_outline:`; CSS chat bubble styling; message timestamps; history cap 14→16; max_tokens 600→900; CAUTION prefix emoji removed; platform icon fallback 💻→"—" in Devices + Network Discovery
- Post-ship (AI Assistant hardening): Hallucination liability reduction — system prompt rules added: no invented numbers, uncertainty disclosure, "verify before proceeding" on action responses; Terminal + Scripts pages use restricted/navigation-only mode (no commands suggested, code blocks stripped post-generation); danger pattern detection (rm -rf, DROP TABLE, kill -9, etc.) prepends CAUTION banner + returns `contains_warning` flag; dashboard renders warning banner on flagged messages; audit log entry per AI chat message (user, page, warning flag, IP); live context injected for Billing/Tickets/Reports pages; persistent disclaimer shown when widget opens

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
- React frontend (dev): http://localhost:3000
- PostgreSQL: localhost:5432 (db: rmmdb, user: rmm_app)
- Redis/Memurai: localhost:6379
- PgBouncer (optional): localhost:6432

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

# Dashboard (Streamlit)
cd dashboard ; streamlit run app.py

# React frontend (dev)
cd frontend ; npm run dev

# Agent (run as admin for patch management)
cd agent ; python rmm_agent.py

# IoT sensor agent (Raspberry Pi / Linux SBC)
cd agent ; python iot_agent.py

# PyInstaller binary build
cd agent ; python build.py
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
- `api/utils/jwt_cache.py` — `TTLCache(512, 60s)` process-local JWT decode cache. Monkey-patches `flask_jwt_extended._decode_jwt_from_request` to skip HMAC verify for repeated tokens. Installed via `_install_jwt_cache()` in `create_app()`. Reduces JWT overhead 135-177ms ��� 60-86ms.
- `api/utils/cache.py` — gains `cache_get_raw(key)` / `cache_set_raw(key, raw_bytes, ttl)` for pre-serialized JSON storage. `health_map` uses this to return a `Response` directly, bypassing double serialization.
- `agent/screenshot.py` — `capture()` returns JPEG bytes or None. Windows/macOS: PIL.ImageGrab; Linux: scrot → gnome-screenshot → PIL fallback. Max 1920px, quality 72. Returns None silently on headless.
- `agent/iot_agent.py` — IoT sensor agent for Raspberry Pi/Linux SBC. Reads hwmon/DHT/BME680/PIR/door sensors. All sensor libs optional. Reuses `config.ini` and `heartbeat.py`. Configure via `[iot]` section in `config.ini`.
- `agent/build.py` — PyInstaller single-file binary builder. `python build.py` in `agent/`. Output: `agent/dist/rmm_agent[.exe]` + `config.ini` template.
- `dashboard/utils/cached_calls.py` — `st.cache_data` wrappers for major read endpoints. Use instead of calling `client.*` directly on frequently re-rendered pages. Call `st.cache_data.clear()` after mutations.
- `api/routes/sensors.py` — IoT sensor readings CRUD at `/api/sensors/`. Agent token auth for POST, JWT for GET.
- `api/tasks/mqtt_tasks.py` — Celery MQTT subscription. Subscribes to `{MQTT_TOPIC_PREFIX}/#`. No-op when `MQTT_HOST` unset.
- `api/tasks/snmp_tasks.py` — Per-device SNMP polling. Community string in `Device.metadata_.snmp_community`. Timeout from `SNMP_TIMEOUT` env var.

## Build Order (Phases)
1. ✓ Agent Core → 2. ✓ API Foundation → 3. ✓ Dashboard UI → 4. ✓ Scripts →
5. ✓ Automation Profiles → 6. ✓ Patch Management → 7. ✓ Alerts → 8. ✓ Tickets →
9. ✓ Reports + Billing + Polish
