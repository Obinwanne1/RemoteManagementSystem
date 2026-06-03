# RMM Build State

## Current Phase
**Phases 5–9 COMPLETE**

## Completed
- [x] Full project scaffold (76 files, initial git commit 5ca8e27)
- [x] All 11 SQLAlchemy models
- [x] All 13 API route modules (full CRUD)
- [x] Flask app factory + extensions
- [x] Agent: collector, heartbeat, executor, script_runner, rmm_agent
- [x] Celery task infrastructure + alert beat tasks
- [x] Streamlit dashboard: 16 pages + utils + brand CSS
- [x] Built-in script library
- [x] Seed script (admin user + default customer + built-in scripts)
- [x] Python venvs created + deps installed (api/venv, dashboard/venv, agent/venv)
- [x] Secrets generated in .env

### Phase A — API (Speed + Reliability)
- [x] A-1: Composite DB indexes on 6 tables (new Alembic migration)
- [x] A-2: Batch 8 COUNT queries → 4 aggregations in dashboard summary
- [x] A-3: Limit health_map `.all()` → `.limit(500)`
- [x] A-4: Fix N+1 devices/metrics list (batch fetch latest metric per device)
- [x] A-5: Fix N+1 in agents.get_tasks (pre-fetch scripts by id)
- [x] A-6: Offload automation device-loop to Celery (`automation_tasks.py`); scripts route pre-fetch devices
- [x] A-7: DB connection pool sizing (pool_size=10, max_overflow=20)
- [x] A-8: Global Flask error handlers (400/404/409/503/500)
- [x] A-9: Request logging middleware (before/after_request with ms timing)
- [x] A-10: Celery retry config + task error handling (acks_late, retry on OperationalError)

### Phase B — Dashboard (Clarity + Reliability)
- [x] B-1: Reuse `requests.Session` via `st.session_state["_rmm_client"]`
- [x] B-2: Retry on transient failures (3 attempts, backoff 0.5/1.0/2.0s, ConnectionError/Timeout only)
- [x] B-3: Token auto-refresh on 401 (POST /api/auth/refresh, retry once)
- [x] B-4: Remove access token from URL query params (session_state only)
- [x] B-5: `st.cache_data` wrappers (TTL 30–120s by endpoint type)
- [x] B-6: `st.spinner` on all data loads across all 16 pages
- [x] B-7: Graceful degradation — replaced hard `st.stop()` with `st.warning`
- [x] B-8: Contextual error messages on all pages

### Phase C — Agent (Reliability + Clarity)
- [x] C-1: Non-blocking CPU sample (`interval=None` + startup prime)
- [x] C-2: Bounded registry enumeration (20s hard deadline)
- [x] C-3: Bounded process scan (3s deadline + 200-process cap)
- [x] C-4: Exponential backoff on heartbeat failures (15s→300s cap)
- [x] C-5: 401 re-registration flow (`send_heartbeat` returns `(data, status)`)
- [x] C-6: Local task result queue (`pending_results.json`, cap 100, flush each cycle)
- [x] C-7: Structured logging with `DeviceFilter` + classified exception types

## BLOCKED — Prerequisites
User must install before running:

1. **PostgreSQL 15** (Windows installer from postgresql.org)
   - Create DB: `CREATE DATABASE rmmdb;`
   - Create user: `CREATE USER rmm_app WITH PASSWORD 'changeme';`
   - Grant: `GRANT ALL ON DATABASE rmmdb TO rmm_app;`

2. **Memurai** (Redis for Windows) from memurai.com — runs on port 6379

After install, run in order:
```
# From api/ with venv active:
flask db init
flask db migrate -m "initial"
flask db upgrade
python seed.py

# Then start services:
python app.py                                          # API on :5000
celery -A tasks.celery_app worker --pool=solo -l info  # Worker
celery -A tasks.celery_app beat -l info               # Scheduler

# From dashboard/ with venv active:
streamlit run app.py                                   # Dashboard on :8501

# From agent/ (separate terminal, admin):
python rmm_agent.py                                   # Agent
```

## Login Credentials (after seed)
- URL: http://localhost:8501
- Email: admin@rmm.local
- Password: Admin1234!

## ORG_REGISTRATION_TOKEN (for agent config.ini)
a8b6ea9bceae8b9cff9e63c2519d3e306453c1325306c64d

## Next Phase
Phase 2 — API Foundation (all CRUD verified, Celery running)
→ Already scaffolded. Mostly about verifying with real DB + adding tests.
