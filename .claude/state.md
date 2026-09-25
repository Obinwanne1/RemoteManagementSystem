# RMM Build State

## Current Phase
**ALL PHASES COMPLETE — Commercial Audit (Phase F) done. Docs updated. Production-readiness diagnostic done 2026-09-21. Mobile Device Management (Android) added 2026-09-22. AI Assistant Phase 1 refactor + API/Token Usage Monitoring added 2026-09-23. Code duplication, testing, and security audits + full remediation done 2026-09-24/25. Documentation pass across all 6 docs (this file included) done 2026-09-25.**

## 2026-09-24/25 — Code Duplication, Testing Coverage, and Security Audits + Remediation
Three sequential full-codebase audit passes, each written to `audits/*.md` with a "Remediation Status" section, all fully remediated (not just reported):
- **Code Duplication** (`audits/code_duplication_audit.md`): new `api/utils/pagination.py::paginated_response()` wired into 9 list endpoints, replacing 9 hand-copied pagination blocks. Found and fixed a real live bug: `admin.py::list_users` returned key `"users"` while the React Admin page read `data.items` — silently broken pagination, now fixed (dashboard-side `.get("users", [])` → `.get("items", [])` fixes in `02_Tickets.py`/`10_Admin.py`/`_ticket_detail.py` too).
- **Testing Coverage** (`audits/testing_audit.md`): closed 0%-coverage gaps on the entire Celery task layer and the React frontend, plus 17/26 untested API routes and 25/26 untested dashboard pages, to **100% file coverage everywhere** — api 484→**490 tests** (44.4%→72% line coverage, `.coveragerc` added, `--cov-fail-under=70` enforced), dashboard 84 tests (all 26 pages), frontend 39 Vitest tests (all 19 pages, Vitest/RTL newly installed) + 2 Playwright E2E specs, agent 19 tests (unchanged). `test-dashboard`/`test-agent` CI jobs added (previously orphaned). Found and fixed 10 real bugs, most seriously a **cross-session cache leak** in `dashboard/utils/cached_calls.py` — all 13 `@st.cache_data` functions took the access token as an underscore-prefixed param (`_token`), which Streamlit silently excludes from the cache key, so one user's dashboard/device/customer/alert/usage data was served to every other user on the same process for up to 120s. Fixed by dropping the underscore prefix on all 13 functions.
- **Security** (`audits/security_audit.md`): standout finding — stored XSS in `dashboard/pages/04_Devices.py` (hostname/IP/OS fields rendered via `unsafe_allow_html=True` without the codebase's `esc()` convention), fixed. Also fixed: `crypto.py` no longer fails open on encrypt/decrypt errors; Fernet key gained domain separation; `User.mfa_secret` is now encrypted at rest (was plaintext); password reset tokens are now single-use; standard security response headers added (`X-Content-Type-Options`, `X-Frame-Options`, scoped CSP). **55 known dependency vulnerabilities** — 51 fixed via real patch/minor version bumps (`flask`, `flask-cors`, `marshmallow`, `python-dotenv`, `requests`, `Pillow`, `cryptography` (agent), `react-router`/`react-router-dom`, plus npm transitive bumps); `pyasn1` deliberately left pinned `<0.5.0` (confirmed hard incompatibility with `pysnmp==4.4.12`'s classic sync API — needs a `snmp_tasks.py` rewrite, not a version bump). CI's `pip-audit`/`npm audit` steps now enforce (no more `continue-on-error`).
- Full suite after all three passes: **api 490/490, dashboard 84/84, frontend 39/39 Vitest + 2/2 Playwright, agent 19/19**, coverage 72%.
- All 6 maintained docs updated (`CLAUDE.md`, `README.md`, `TECHNICAL_GUIDE.md` new Ch. 21-22, `HANDOVER_GUIDE.md` new Part XIV / Ch. 57-59, `SKILL.md` new Phase I, this file) — see "PDF Regeneration" below, done as part of this same pass.

## 2026-09-23 — AI Assistant Phase 1 Refactor + API & Token Usage Monitoring
- **AI Assistant refactor**: prompt/tool logic moved out of `routes/assistant.py` into `services/ai_prompt.py` + `services/ai_tools.py`; durable conversation history (`AiConversation`/`AiMessage`, migration `p7q8r9s0t1u2`); mutating tool calls staged via `AiPendingAction`, require explicit confirm/deny — never auto-executed; `utils/rate_limit.py` for per-tool rate limits on the agentic path. 14 new tests (`test_assistant.py`).
- **Usage Monitoring** (why: usage had gotten unexpectedly high with no visibility into the cause): new `ApiUsageEvent`/`ApiUsageHourly`/`UsageAlertConfig` tables (migration `q8r9s0t1u2v3`); `utils/usage_tracker.py` records every AI Assistant call's token count + estimated cost, every outbound integration call (Stripe, PSA, Android MDM, webhooks, SMTP, IMAP poll, network scan), and every internal Flask API request (via a Redis counter rolled into an hourly table by Celery beat).
- `api/routes/usage.py` (`/api/admin/usage`) is **strictly superadmin-only** — no admin bypass, unlike every other route in this app. `tasks/usage_tasks.py::detect_usage_anomaly` (hourly beat) fires real email/webhook notifications on a usage spike via the existing `send_alert_notification`/`dispatch_alert_webhooks` primitives (deliberately does not create an `Alert`/`AlertRule` row — `Alert.device_id` is `NOT NULL`, not worth migrating).
- Dashboard `22_Usage_Monitoring.py` + React `UsageMonitoringPage.tsx`, both gated to `role == "superadmin"` exactly. New `api_usage` Reports template, hidden from non-superadmin.
- 13 new tests (`test_usage.py`); full suite 146/146 passing. Committed as two separate commits (refactor, then usage monitoring) since they were independent work sharing a few touched files (`api/app.py`, `.env.example`, `dashboard/utils/api_client.py`, `frontend/src/components/Layout.tsx`).
- Docs updated: CLAUDE.md, README.md, TECHNICAL_GUIDE.md, HANDOVER_GUIDE.md, SKILL.md, this file. PDFs not regenerated (pre-existing open TODO, see below).

## 2026-09-22 — Mobile Device Management (Android)
- Real phone management (lock/wipe/lost-mode/compliance) via Google's Android Management API — no custom agent on the phone. `MdmIntegration`/`MobileEnrollment` models + migration `o6p7q8r9s0t1`; `api/routes/mobile_mdm.py` (`/api/mdm`); `api/tasks/mdm_tasks.py` (5-min beat sync); `api/utils/android_mgmt.py`; `api/utils/crypto.py` (promoted out of `psa_integration.py`, now shared).
- Consent-gated enrollment: `role=client` server-forced to BYOD + requires `consent_acknowledged`; every consent event and issued command audit-logged.
- Dashboard: new `19_Mobile_Enrollment.py` (admin/technician), "+ Enroll My Phone" on `21_Client_Tickets.py`, real action buttons on managed rows in `04_Devices.py`.
- iOS deliberately not implemented — needs an Apple Business Manager or Fleet/MicroMDM decision outside this codebase; placeholder columns/dispatch stub reserved so it's additive later.
- 10 new tests (`api/tests/test_mobile_mdm.py`); full suite 116/116 passing.
- All 5 top-level docs updated with practical examples: `CLAUDE.md`, `README.md`, `TECHNICAL_GUIDE.md` (new Ch. 19), `HANDOVER_GUIDE.md` (new Ch. 55), `SKILL.md` (new Phase G).
- The code itself was committed (`892e945`) separately, before this doc pass — this doc-update pass is NOT yet committed as of writing this note. The user's own `git push` of `892e945` also hit a cancelled GitHub device-code auth prompt in their terminal; confirm that resolved before assuming `origin/main` is current.

## 2026-09-21 — Production-Readiness Diagnostic
- Fixed: `FLASK_DEBUG` defaulted to on (`api/app.py`) — flipped default to off; `docker-compose.yml` now sets it explicitly and requires `DB_PASSWORD` instead of silently defaulting to `changeme`; Postgres/Redis compose ports bound to `127.0.0.1` only.
- Fixed: real secrets were committed to git — `agent/config.ini` (live device_id + encrypted agent_token), and the real `ORG_REGISTRATION_TOKEN` hardcoded in `agent/install.bat` and this file. Scrubbed from current files; **still in git history on `origin/main`**.
- DONE: rotated `ORG_REGISTRATION_TOKEN` in local `.env` (old value only usable for NEW agent enrollments, so already-registered devices are unaffected). DONE: Redis auth added — docker-compose Redis now requires `REDIS_PASSWORD` (new env var, docker-only, not needed for local dev).
- STILL OPEN (requires your decision, not done): scrub the leaked token/device credentials from git history (`git filter-repo`/BFG + force-push) — the old token and `agent/config.ini` contents are still recoverable from past commits on `origin/main`.
- Cleaned up: removed `chunk.txt`, `debug.txt`, `dump.rdb`, `redis.zip` + vendored `redis/` binaries (47MB), `patch_handover*.py`/`patch_technical*.py`, duplicate `generate_pdf.py`, `api/celerybeat-schedule-shm` from git tracking (kept locally, now gitignored).
- Documented in CLAUDE.md: `billing.py` (Stripe), `psa.py` (ConnectWise/Autotask), `update.py` (agent auto-update), `org_settings.py`, `email_tasks.py` (support-inbox-to-ticket), `anomaly_tasks.py` — all existed in code but were missing from the changelog.
- Corrected page counts: Streamlit has 22 pages (not 19). React frontend has 18 pages and is **not** at parity with Streamlit (missing App Center, Invoice Detail, IoT Sensors, Client Tickets) — flagged as a known gap, not built out in this pass.
- Not done in this pass (flagged only): Redis has no `requirepass` set; TECHNICAL_GUIDE.pdf/HANDOVER_GUIDE.pdf regeneration (pre-existing TODO below); closing the React parity gap.

## Completed

### Core Build (Phases 1–9)
- [x] Full project scaffold (76 files, initial git commit 5ca8e27)
- [x] All SQLAlchemy models (12 models incl. SLAPolicy)
- [x] All API route modules (18 blueprints, full CRUD)
- [x] Flask app factory + extensions
- [x] Agent: collector, heartbeat, executor, script_runner, rmm_agent
- [x] Celery task infrastructure + alert beat tasks
- [x] Streamlit dashboard: 19 pages + utils + brand CSS
- [x] Built-in script library (7 scripts)
- [x] Seed script (admin user + default customer + built-in scripts)
- [x] Python venvs created + deps installed (api/venv, dashboard/venv, agent/venv)
- [x] Secrets generated in .env

### Phase A — API (Speed + Reliability)
- [x] A-1 through A-10: indexes, batch queries, pool sizing, error handlers, logging, Celery retry

### Phase B — Dashboard (Clarity + Reliability)
- [x] B-1 through B-8: session reuse, retry/backoff, token refresh, cache_data, spinners, graceful degradation

### Phase C — Agent (Reliability + Clarity)
- [x] C-1 through C-7: non-blocking CPU, bounded scans, exponential backoff, local task queue, structured logging

### Post-Ship Fixes
- [x] Org enrollment token exposed in Admin panel
- [x] Refresh token persisted in `?rtok=` URL param
- [x] Force password change on first login (`must_change_password` column + dashboard intercept)
- [x] Software Patches winget fix (skip non-ASCII progress bar lines)
- [x] WiFi/Agentless device support (3 new Device columns, OUI vendor lookup, network scan task)
- [x] Superadmin role (permanent seeded account, purple role pill, all routes bypassed)
- [x] Agentless device identification enhancements (port probe, rDNS, Android keyword fallback)
- [x] Android/duplicate scan fixes (hostname fallback, IP upsert across all devices)
- [x] Scan false-positive fixes (Windows requires 2+ ports, router hostnames excluded from DB)
- [x] Clickable Device Health Map (`st.button` cards → navigate to Devices page)
- [x] Metrics History 7-day fallback (retries with hours=168 when 24h empty)
- [x] Software Patches agentless note (info strip explaining exclusion)
- [x] Metrics History 30-day fallback extension

### Phase F — Commercial Audit
- [x] F-1: Shell injection fix — terminal_worker.py uses structured args (no shell=True)
- [x] F-2: Cross-tenant data leak fix — customer-scoped filtering on 5 list endpoints
- [x] F-3: Agent registration — org_token tied to specific customer at registration
- [x] F-4: Plaintext agent token on disk — DPAPI encryption on Windows (win32crypt)
- [x] F-5: Swagger/OpenAPI — `/api/docs` SwaggerUI, `/api/openapi.json` raw spec (47 paths)
- [x] F-6: Redis caching — `cache_get`/`cache_set`/`cache_delete` helpers, 30-60s TTL on expensive queries
- [x] F-7: Notification webhooks — Slack Block Kit, Teams MessageCard, generic JSON POST
- [x] F-8: Celery thundering herd fix — Redis `SET NX EX` distributed lock on alert evaluation
- [x] F-9: Database backup — nightly `pg_dump` Celery task, gzip, configurable retention
- [x] F-10: Billing automation — recurring invoice Celery task, per-customer billing profiles
- [x] F-11: SLA policies — `SLAPolicy` model + CRUD blueprint + auto due_date on ticket creation
- [x] F-12: GDPR Art. 20 export — `GET /api/admin/users/<id>/gdpr-export`
- [x] F-13: GDPR Art. 17 erasure — `DELETE /api/admin/users/<id>/gdpr-delete` (irreversible anonymisation)
- [x] AI Assistant — context-aware chat widget on all 19 pages (Claude Haiku 4.5, JWT-scoped, rate-limited)
- [x] Terminal client-role device ownership check
- [x] Script run audit logging (AuditLog emission)
- [x] backup_tasks + billing_tasks registered in Celery beat + include list

### Post-Ship (AI Assistant Modernization)
- [x] Removed 🤖/👋 emojis from `dashboard/utils/ai_assistant.py`
- [x] Toggle buttons use Material icons (auto_awesome / close)
- [x] Send + Clear buttons use Material icons (send / delete_outline)
- [x] CSS chat bubble styling injected into sidebar
- [x] Message timestamps (HH:MM) on every bubble
- [x] Empty-state dashed card, subtler disclaimer
- [x] History cap 14→16, max_chars=800 on input
- [x] max_tokens 600→900 in `api/routes/assistant.py`
- [x] CAUTION prefix emoji stripped
- [x] Platform icon fallback 💻→"—" in `04_Devices.py` + `07_Network_Discovery.py`
- [x] HANDOVER_GUIDE.md, CLAUDE.md updated

### Documentation (updated to reflect Phase F)
- [x] CLAUDE.md — post-ship bullets + Key Utilities updated
- [x] SKILL.md — Phase F appended (F.1–F.10)
- [x] TECHNICAL_GUIDE.md — Section 16 Phase F appended (F.1–F.13)
- [x] HANDOVER_GUIDE.md — Version 6.0, Part XI ToC + Chapters 45–50 appended
- [x] README.md — Features table, API endpoints, env vars, project structure updated
- [x] .env.example — BACKUP_DIR, BACKUP_RETAIN_DAYS added (ANTHROPIC_API_KEY already present)
- [ ] HANDOVER_GUIDE.pdf — needs regeneration from updated .md
- [ ] TECHNICAL_GUIDE.pdf — needs regeneration from updated .md

## Services & Ports
- Flask API: http://localhost:5000
- Streamlit dashboard: http://localhost:8501
- PostgreSQL: localhost:5432 (db: rmmdb, user: rmm_app)
- Redis/Memurai: localhost:6379

## Login Credentials
- URL: http://localhost:8501
- Superadmin email: `SUPERADMIN_EMAIL` from `.env` (default: superadmin@rmm.local)
- Superadmin password: `SUPERADMIN_PASSWORD` from `.env`

## ORG_REGISTRATION_TOKEN
Stored in `.env` only (not in this file — see 2026-09-21 diagnostic note below;
the token that was previously written here was committed to git and must be rotated).

## PDF Regeneration
Superseded by `build_pdf.py` at the repo root (generalized 2026-09-23 to build both PDFs from one script; the pandoc/weasyprint note below is historical). Run after any change to `HANDOVER_GUIDE.md` or `TECHNICAL_GUIDE.md`:
```powershell
python build_pdf.py
```
Verify a regenerated PDF actually picked up new content by decompressing its content stream directly (`/ASCII85Decode /FlateDecode`-encoded) rather than trusting a clean exit code — see the 2026-09-23 entry above for the method.
