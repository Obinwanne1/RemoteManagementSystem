# RMM Project — Claude Code Instructions

## Project
NinjaOne-style Remote Monitoring & Management system.
Stack: Flask API + Streamlit dashboard + Python agent + PostgreSQL + Redis/Celery.

## Build Status
**ALL PHASES COMPLETE** (Phases 1–9 + A/B/C optimization pass)
- Phase A: API speed/reliability (indexes, batch queries, pool sizing, error handlers, logging, Celery retry)
- Phase B: Dashboard reliability (session reuse, retry/backoff, token refresh, cache_data, spinners, graceful degradation)
- Phase C: Agent reliability (non-blocking CPU, bounded scans, exponential backoff, local task queue, structured logging)

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

## Build Order (Phases)
1. ✓ Agent Core → 2. ✓ API Foundation → 3. ✓ Dashboard UI → 4. ✓ Scripts →
5. ✓ Automation Profiles → 6. ✓ Patch Management → 7. ✓ Alerts → 8. ✓ Tickets →
9. ✓ Reports + Billing + Polish
