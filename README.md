# RMM System

A NinjaOne-style Remote Monitoring & Management platform built in-house. Monitor devices, manage patches, run scripts, respond to alerts, and handle client billing — all from a single dashboard.

**Stack:** Flask API · Streamlit Dashboard · Python Agent · PostgreSQL · Redis/Celery

---

## Features

| Category | What's included |
|----------|----------------|
| **Monitoring** | Real-time CPU/RAM/disk metrics, device health map, 7-day history fallback |
| **Alerts** | Rule-based alerting (threshold + offline), SMTP notifications, cooldown control |
| **Devices** | Agent-managed (Windows/macOS/Linux) + agentless WiFi devices (iOS/Android/IoT) |
| **Tickets** | Full helpdesk ticketing with comments, priority, assignee, status workflow |
| **Patch Management** | OS patches via WUA, software patches via winget, maintenance window enforcement |
| **Scripts** | Run PowerShell/bat/Python/shell scripts remotely, 7 built-in maintenance scripts |
| **Automation** | Scheduled automation profiles (weekly maintenance, patching, cleanup) |
| **Network Discovery** | ICMP sweep + OUI/port/rDNS platform detection, saves agentless device records |
| **Reports** | CSV reports: device health, patch compliance, alert summary, software inventory |
| **Billing** | Invoice creation and status tracking per customer |
| **Auth & Security** | JWT + refresh tokens, TOTP MFA, role-based access control (4 roles), superadmin |
| **Admin** | Audit log, user management, org enrollment token, server IP display |

---

## Architecture

```
Browser → Streamlit Dashboard (:8501)
               │ REST/JWT
               ▼
          Flask API (:5000)
          ├── PostgreSQL (:5432)  — all persistent data
          ├── Redis (:6379)       — Celery broker/backend
          └── Celery Worker + Beat — background tasks

Agent (on each managed machine)
  └── heartbeat every 60s → POST /api/agents/<id>/heartbeat
  └── polls tasks → GET /api/agents/<id>/tasks
```

---

## Quick Start (Docker — recommended)

**Prerequisites:** Docker Desktop

```bash
# 1. Clone
git clone https://github.com/Obinwanne1/RemoteManagementSystem.git
cd RemoteManagementSystem

# 2. Create API env file
cp .env.example api/.env
# Edit api/.env — set SECRET_KEY, JWT_SECRET_KEY, ORG_REGISTRATION_TOKEN, SUPERADMIN_PASSWORD

# 3. Start everything
docker-compose up -d

# 4. Open dashboard
# http://localhost:8501
# Health check: http://localhost:5000/api/health
```

> **Note:** Use `@db:5432` (not `@localhost:5432`) in `DATABASE_URL` when running with Docker.

---

## Manual Setup (Development)

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis (or [Memurai](https://www.memurai.com/) on Windows)

### 1 — Database

```sql
CREATE USER rmm_app WITH PASSWORD 'your_password';
CREATE DATABASE rmmdb OWNER rmm_app;
GRANT ALL PRIVILEGES ON DATABASE rmmdb TO rmm_app;
```

### 2 — API

```powershell
cd api
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\\.env.example .env   # then edit .env
flask --app app:create_app db upgrade
python app.py
```

### 3 — Celery Worker + Beat (separate terminals)

```powershell
cd api
.\venv\Scripts\Activate.ps1
celery -A tasks.celery_app worker --pool=solo -l info   # Terminal 2
celery -A tasks.celery_app beat -l info                 # Terminal 3
```

### 4 — Dashboard

```powershell
cd dashboard
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### 5 — Agent (on each managed machine)

```powershell
cd agent
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup_agent.py <server_ip> <org_token>   # patches config.ini automatically
python rmm_agent.py
```

The org token is shown in **Admin → System Info → Agent Enrollment Token**.

---

## Environment Variables

Copy `.env.example` to `api/.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✓ | Flask secret — min 32 chars |
| `JWT_SECRET_KEY` | ✓ | JWT signing key — min 32 chars |
| `DATABASE_URL` | ✓ | PostgreSQL connection string |
| `ORG_REGISTRATION_TOKEN` | ✓ | Shared secret for agent registration |
| `SUPERADMIN_PASSWORD` | ✓ | Superadmin password — min 10 chars |
| `REDIS_URL` | — | Default: `redis://localhost:6379/0` |
| `CORS_ORIGINS` | — | Default: `http://localhost:8501` |
| `SUPERADMIN_EMAIL` | — | Default: `superadmin@rmm.local` |
| `SMTP_HOST` | — | Omit to disable email alerts |

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Security:** The API refuses to start if `SECRET_KEY`, `JWT_SECRET_KEY`, or `SUPERADMIN_PASSWORD` are missing or too short. `ORG_REGISTRATION_TOKEN` must not be the placeholder value.

---

## Default Login

After first startup the superadmin account is auto-seeded from your `.env`:

| Field | Value |
|-------|-------|
| Email | `SUPERADMIN_EMAIL` (default: `superadmin@rmm.local`) |
| Password | `SUPERADMIN_PASSWORD` (from `.env`) |

---

## Dashboard Pages

| # | Page | Access |
|---|------|--------|
| 01 | Overview — stat cards, health map, alerts feed | All |
| 02 | Tickets | All |
| 03 | Customers | All |
| 04 | Devices — agent + agentless, metrics history | All |
| 05 | Alerts — rules + active alerts | All |
| 06 | App Center — software inventory | All |
| 07 | Network Discovery — ICMP scan, save agentless devices | Admin/Tech |
| 08 | Reports — generate + download CSV | Admin/Tech |
| 09 | Billing — invoices | Admin |
| 10 | Admin — audit log, users, system info | Admin |
| 11 | Automation — scheduled profiles | Admin/Tech |
| 12 | OS Patches — WUA patch records, approve + deploy | Admin/Tech |
| 13 | Software Patches — winget updates | Admin/Tech |
| 14 | Disk Management | Admin/Tech |
| 15 | Maintenance — reboot, shutdown, cleanup | Admin/Tech |
| 16 | Scripts — run custom scripts remotely | Admin/Tech |
| 17 | My Profile — password change, MFA setup | All |

---

## Roles

| Role | Access |
|------|--------|
| **viewer** | Read-only — dashboard, devices, alerts, tickets |
| **technician** | Operational — scripts, patches, tickets, maintenance |
| **admin** | Full — users, billing, audit log, system config |
| **superadmin** | System-level — bypasses all role checks, cannot be deleted via UI |

---

## MFA

TOTP-based two-factor authentication (Google Authenticator, Authy, 1Password, etc.):

1. Log in → **My Profile** → **Enable MFA** → scan QR code → enter 6-digit code
2. On next login: password screen → TOTP screen → dashboard
3. Disable: **My Profile** → enter current password → **Disable MFA**

---

## API Endpoints (summary)

All routes prefixed `/api/`. JWT required unless noted.

- **Auth:** `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/mfa/*`
- **Agents:** `/agents/register` (org_token), `/agents/<id>/heartbeat` (X-Agent-Token)
- **Devices:** `/devices/`, `/devices/<id>`, `/devices/<id>/metrics`, `/devices/<id>/queue_task`
- **Alerts:** `/alerts/`, `/alerts/rules/`
- **Tickets:** `/tickets/`, `/tickets/<id>/comments`
- **Patches:** `/patches/`, `/patches/policies/`
- **Scripts:** `/scripts/`, `/scripts/<id>/run`
- **Automation:** `/automation/profiles/`
- **Network:** `/network/scan`, `/network/agentless_devices`
- **Reports:** `/reports/`
- **Billing:** `/billing/invoices/`
- **Admin:** `/admin/users`, `/admin/org-token`, `/admin/server_ips`
- **Health:** `/health` — `{"status": "ok", "db": true, "redis": true, "version": "1.0.0"}`

Full reference: see `TECHNICAL_GUIDE.md`.

---

## Project Structure

```
RemoteManagementSystem/
├── api/                    # Flask API
│   ├── app.py              # Application factory
│   ├── config.py           # Environment configs
│   ├── models/             # SQLAlchemy models (11 models)
│   ├── routes/             # Blueprint handlers (14 blueprints)
│   ├── tasks/              # Celery tasks (alert, patch, network, report, automation)
│   ├── utils/              # Helpers (superadmin, oui, notifications, builtin_scripts)
│   ├── migrations/         # Alembic migrations
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/              # Streamlit frontend
│   ├── app.py              # Login + routing entrypoint
│   ├── pages/              # 17 pages
│   ├── utils/              # api_client, auth, nav, styles, formatters
│   ├── Dockerfile
│   └── requirements.txt
├── agent/                  # Python monitoring agent
│   ├── rmm_agent.py        # Main loop
│   ├── collector.py        # Metrics + software + patch collection
│   ├── heartbeat.py        # API client
│   ├── executor.py         # Task execution
│   ├── script_runner.py    # PS1/bat/py/sh runner
│   └── setup_agent.py      # One-command WiFi deployment
├── docker-compose.yml      # 6-service stack
├── .env.example            # Environment template
├── HANDOVER_GUIDE.md       # Full user + ops guide (also as PDF)
└── TECHNICAL_GUIDE.md      # Developer reference
```

---

## Documentation

| Document | Audience |
|----------|----------|
| `HANDOVER_GUIDE.md` / `.pdf` | All staff — installation, usage, MFA, troubleshooting |
| `TECHNICAL_GUIDE.md` | Developers — architecture, API reference, security model, extension guide |

---

## Production Checklist

- [ ] Set `FLASK_DEBUG=0`, `FLASK_ENV=production`
- [ ] Use HTTPS (nginx reverse proxy + Let's Encrypt)
- [ ] Set `CORS_ORIGINS` to your dashboard URL (not `*`)
- [ ] Add Redis password (`requirepass` in Memurai/Redis config)
- [ ] Rotate `ORG_REGISTRATION_TOKEN` after all agents registered
- [ ] Enable MFA for all admin accounts
- [ ] Set up automated PostgreSQL backups
- [ ] Run agent as a low-privilege Windows service account (not SYSTEM)

---

## License

Internal use only. Not licensed for redistribution.
