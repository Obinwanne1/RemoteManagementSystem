# RMM Build State

## Current Phase
**Phase 1 — Agent Core** (IN PROGRESS)

## Completed
- [x] Project scaffold (directories, .gitignore, CLAUDE.md, .env.example)

## In Progress
- [ ] API: app.py, config.py, extensions.py
- [ ] API models: user.py, device.py
- [ ] API routes: auth.py, agents.py
- [ ] Alembic migrations
- [ ] Agent: collector.py, heartbeat.py, rmm_agent.py

## Phase 1 Milestone
Agent on Windows sends CPU/RAM/disk to PostgreSQL every 60s.

## Prerequisites Still Needed
- PostgreSQL 15 installed and running (port 5432, db: rmmdb)
- Memurai (Redis for Windows) installed and running (port 6379)
- Python venvs created and deps installed

## Next Phase
Phase 2 — API Foundation (all CRUD endpoints + Celery)
