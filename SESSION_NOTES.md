# Session Notes — 2026-09-23

Working notes for this session. Not part of the maintained doc set (`CLAUDE.md`, `README.md`,
`TECHNICAL_GUIDE.md`, `HANDOVER_GUIDE.md`, `SKILL.md`) — those were all updated properly; this
file is a quick "what happened and why" for anyone picking up where this session left off.

## What was built

**API & Token Usage Monitoring** — a superadmin-only backend auditing/reporting feature. Built
because API/token usage had grown unexpectedly high with no visibility into which service,
feature, or user was responsible.

- Tracks: every AI Assistant call (tokens + estimated $ cost), every outbound integration call
  (Stripe, ConnectWise/Autotask PSA, Android MDM, Slack/Teams/generic webhooks, SMTP, IMAP
  polling, network scans), and all internal Flask API request volume.
- Strictly gated to `role == "superadmin"` — regular `admin` gets 403/sees nothing, on every
  surface (API routes, dashboard page + nav link, React page + nav link, Reports template).
- Spike detection: hourly comparison against a trailing-7-day baseline, shown as a live banner
  **and** (opt-in, off by default) real email/Slack/Teams/webhook notifications via a new
  Celery beat task, reusing the existing alert-notification primitives directly rather than
  extending the device-centric `Alert`/`AlertRule` schema.
- New files: `api/models/usage.py`, `api/routes/usage.py`, `api/utils/usage_tracker.py`,
  `api/tasks/usage_tasks.py`, `dashboard/pages/22_Usage_Monitoring.py`,
  `frontend/src/pages/UsageMonitoringPage.tsx` + `frontend/src/api/usage.ts`,
  `api/tests/test_usage.py` (13 tests).
- Migration: `q8r9s0t1u2v3` (already applied to the local dev Postgres DB during this session).

## What was found and committed alongside it

There was a complete, working, but **uncommitted** AI Assistant refactor already sitting in the
working tree from an earlier session (moved prompt/tool logic into `api/services/`, added
conversation persistence, mutating-tool confirm/deny staging, a new rate-limit utility, 14 tests
in `test_assistant.py`). It was unrelated to Usage Monitoring but touched a few of the same
files, so it was split out hunk-by-hunk and committed separately first — see "Commits" below.

## Commits (all pushed to `origin/main`)

```
0f857ba refactor(assistant): move AI assistant to services layer with conversation persistence
4fe6865 feat(usage): add superadmin-only API and AI token usage monitoring
623e650 docs: regenerate HANDOVER_GUIDE.pdf and TECHNICAL_GUIDE.pdf
```

`4fe6865` also updated all 6 documentation files (`CLAUDE.md`, `README.md`, `TECHNICAL_GUIDE.md`
new Ch. 20, `HANDOVER_GUIDE.md` new Part XIII/Ch. 56, `SKILL.md` new Phase H, `.claude/state.md`)
and `api/swagger_spec.py` (47→52 paths, 16→17 tags). `623e650` also generalized `build_pdf.py`
(previously hardcoded to only build `HANDOVER_GUIDE.pdf`) so one script builds both PDFs.

## Verification done this session

- Full API test suite: 146/146 passing (`cd api && venv/Scripts/python.exe -m pytest tests -q`)
- Frontend TypeScript type-check: clean (`cd frontend && npx tsc --noEmit`)
- Flask app boots and registers all 6 new `/api/admin/usage/*` routes
- Migration applied cleanly to the local dev Postgres DB; API + Streamlit dashboard restarted
  and confirmed serving the new code (health checks 200)
- Both regenerated PDFs verified by decompressing their content streams directly (they're
  `/ASCII85Decode /FlateDecode`-encoded) and confirming the new chapter text is actually present,
  not just trusting a clean exit code

## Known open items (not done this session, flagged for follow-up)

- **Celery worker + beat are not running** in this dev environment. The two new hourly beat
  tasks (`persist_hourly_usage_rollup`, `detect_usage_anomaly`) and the internal-API hourly
  rollup won't actually fire until those processes are started:
  ```
  cd api && celery -A tasks.celery_app worker --pool=solo -l info
  cd api && celery -A tasks.celery_app beat -l info
  ```
- Spike-alert notifications are **disabled by default** (`UsageAlertConfig.is_enabled = False`)
  — a superadmin must opt in via the Usage Monitoring page's "Spike Alert Configuration" panel
  and provide at least one email/webhook, or nothing will ever fire even with Celery beat running.
- The React frontend (`frontend/`) was not started/smoke-tested in a browser this session —
  only `tsc --noEmit` was run. The Streamlit dashboard's `22_Usage_Monitoring.py` *was* smoke
  checked (page loads, health check 200) but not clicked through with real AI Assistant traffic
  to visually confirm token/cost numbers render correctly end-to-end.
- Pre-existing, unrelated to this session's work (inherited, not newly introduced): the leaked
  `ORG_REGISTRATION_TOKEN` and `agent/config.ini` contents are still recoverable from git
  history on `origin/main` (flagged in an earlier diagnostic pass, deliberately not scrubbed —
  destructive history rewrite needs an explicit decision); the React frontend is still behind
  Streamlit on page parity.

## Quick reference

- Superadmin login: `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` from `.env` (default email
  `superadmin@rmm.local`).
- Usage Monitoring page: Streamlit sidebar → **SUPERADMIN** section → **Usage Monitoring**
  (`http://localhost:8501`), or React `http://localhost:3000/usage-monitoring`.
- To see real numbers on the page: open the AI Assistant chat widget on any page and send a
  few messages — that's the fastest way to populate token/cost rows.
