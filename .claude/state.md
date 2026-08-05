# RMM Build State

## Current Phase
**ALL PHASES COMPLETE — Commercial Audit (Phase F) done. Docs updated.**

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

## ORG_REGISTRATION_TOKEN (for agent config.ini)
a8b6ea9bceae8b9cff9e63c2519d3e306453c1325306c64d

## PDF Regeneration (pending)
Need one of: pandoc, weasyprint, or reportlab available on PATH.
Check: `pandoc --version` or `pip show weasyprint`
Command (if pandoc available):
```powershell
pandoc HANDOVER_GUIDE.md -o HANDOVER_GUIDE.pdf --pdf-engine=wkhtmltopdf
pandoc TECHNICAL_GUIDE.md -o TECHNICAL_GUIDE.pdf --pdf-engine=wkhtmltopdf
```
