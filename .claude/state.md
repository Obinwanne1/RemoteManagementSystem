# RMM Build State

## Current Phase
**Phase 1 — Agent Core** (COMPLETE — waiting on infra)

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
