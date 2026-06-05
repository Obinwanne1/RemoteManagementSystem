# RMM System — Technical Guide

**Audience:** Developers, system architects, and advanced administrators  
**Stack:** Flask 3 · SQLAlchemy 2 · Celery 5 · Streamlit 1.58 · PostgreSQL 15 · Redis/Memurai  
**Version:** 1.0 (all phases complete)

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Data Models](#2-data-models)
3. [API Endpoints](#3-api-endpoints)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Celery Tasks & Schedules](#5-celery-tasks--schedules)
6. [Agent Internals](#6-agent-internals)
7. [Built-in Scripts Reference](#7-built-in-scripts-reference)
8. [Dashboard API Client](#8-dashboard-api-client)
9. [Performance Optimizations](#9-performance-optimizations)
10. [Extension Guide](#10-extension-guide)
11. [Security Model](#11-security-model)
12. [Environment Variables Reference](#12-environment-variables-reference)

---

## 1. System Architecture

### Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser  http://localhost:8501                                   │
│  Streamlit Dashboard (Python)                                     │
│  dashboard/app.py  +  dashboard/pages/*.py  (16 pages)           │
│  dashboard/utils/api_client.py  →  RMMClient (session + retry)   │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP REST  (JWT Bearer in Authorization header)
                         │ 3-attempt retry, 0.5/1.0/2.0s backoff
                         │ 401 → auto-refresh → retry once
┌────────────────────────▼─────────────────────────────────────────┐
│  Flask API  http://localhost:5000                                 │
│  api/app.py  (application factory)                               │
│  api/routes/*.py   (13 blueprints)                               │
│  api/models/*.py   (11 SQLAlchemy models, 21 tables)             │
│  api/utils/builtin_scripts.py   (7 built-in PS1 scripts)         │
│  api/utils/notifications.py     (SMTP email, opt-in)             │
│  api/utils/oui.py               (MAC vendor lookup, 500+ entries)│
│  api/tasks/network_tasks.py     (ICMP scan + agentless ping beat) │
└──────┬──────────────┬───────────────────┬────────────────────────┘
       │              │                   │
  PostgreSQL      Redis (broker)      Agent API endpoints
  :5432           :6379               /api/agents/*
  db: rmmdb       Celery backend      X-Agent-Token auth
       │              │
       │    ┌─────────▼──────────────────────────────┐
       │    │  Celery Worker  (--pool=solo on Windows) │
       │    │  tasks/alert_tasks.py   — beat 60s/180s  │
       │    │  tasks/patch_tasks.py   — beat 1800s      │
       │    │  tasks/automation_tasks.py — on demand    │
       │    │  tasks/report_tasks.py  — on demand       │
       │    │  tasks/network_tasks.py — beat 300s       │
       │    └────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  Python Agent  (on each managed Windows machine)                 │
│  agent/rmm_agent.py  — main loop (60s heartbeat)                │
│  agent/collector.py  — hardware/metrics/software/patches         │
│  agent/heartbeat.py  — APIClient (register/heartbeat/tasks)      │
│  agent/executor.py   — task execution engine                     │
│  agent/script_runner.py — ps1/bat/py/sh execution                │
└─────────────────────────────────────────────────────────────────┘
```

### Request Flow: Dashboard → API → Agent

```
User clicks "Reboot" in Maintenance page
  │
  ▼
dashboard/pages/15_Maintenance.py
  └─ client.reboot_device(device_id)
       └─ POST /api/devices/<id>/reboot
            └─ routes/devices.py: reboot_device()
                 └─ _queue_builtin_task(device_id, "reboot")
                      └─ ScriptRun(script_id=<builtin_reboot_id>, device_id=...)
                           └─ db.session.add + commit
                                │
                               (60s later)
                                │
                                ▼
                    agent polls GET /api/agents/<id>/tasks
                      └─ returns [{type: "run_script", script_content: "..."}]
                           └─ executor.run(task)
                                └─ script_runner.run_ps1("Restart-Computer -Force")
```

---

## 2. Data Models

### Model Relationships

```
Customer ──< Device ──< DeviceMetrics
    │           │──< InstalledSoftware
    │           │──< AlertRule.customer_id (optional)
    │           │──< PatchRecord
    │           │──< ScriptRun
    │           └──< ScheduledTaskRun
    │
    ├──< Ticket ──< TicketComment
    │       └── assignee_id → User
    │
    ├──< PatchPolicy
    ├──< AutomationProfile ──< ScheduledTaskRun
    ├──< Invoice
    ├──< Report
    └──< NetworkScan

AlertRule ──< Alert
Script ──< ScriptRun
User ──< AuditLog
Device ──< AgentToken
```

### Model Reference

#### `User` (`users`)
```python
id                   Integer PK
email                String(255) UNIQUE NOT NULL
password_hash        String(255)          # bcrypt rounds=12
full_name            String(255)
role                 String(50)           # superadmin | admin | technician | viewer
                                          # superadmin: highest privilege, bypasses all _require_role() checks,
                                          # cannot be deleted or modified via API
mfa_secret           String(32)
mfa_enabled          Boolean default False
is_active            Boolean default True
must_change_password Boolean default False server_default="false"
                                          # True → intercept login with force-change screen
created_at           DateTime server_default=now()
```

#### `Customer` (`customers`)
```python
id         Integer PK
name       String(255) NOT NULL
slug       String(100) UNIQUE
email      String(255)
phone      String(50)
tier       String(50) default 'standard'   # standard | premium | enterprise
notes      Text
is_active  Boolean default True
created_at DateTime
```

#### `Device` (`devices`)
```python
id           String/UUID PK
customer_id  FK → customers
group_id     FK → device_groups  (nullable)
hostname     String(255)
platform     String(50)          # windows | linux | mac
os_name      String(255)
os_version   String(100)
cpu_brand    String(255)
cpu_cores    Integer
ram_gb       Float
ip_address   String(50)          # local IP
serial_number String(255)
hardware_id  String(64) UNIQUE   # SHA256(hostname+MAC)
status       String(50) default 'active'
is_online    Boolean default False
last_seen    DateTime
agent_version String(20)
display_name String(255)
created_at   DateTime
is_agentless Boolean default False NOT NULL  # True = network-discovered, no agent
device_type  String(50) default 'laptop' NOT NULL  # laptop | desktop | mobile | server | unknown
vendor       String(255) nullable             # OUI lookup result, e.g. "Apple, Inc."
# NOTE: customer_id is nullable=True — agentless devices start unassigned
```

#### `DeviceMetrics` (`device_metrics`)
```python
id             Integer PK
device_id      FK → devices
cpu_pct        Float
ram_pct        Float
disk_pct       Float             # primary disk
battery_pct    Float (nullable)
uptime_seconds BigInteger
top_processes  JSON              # [{pid, name, cpu}]
disks          JSON              # [{mountpoint, device, total_gb, used_gb, free_gb, percent}]
collected_at   DateTime          # NOTE: field is collected_at not recorded_at
```

#### `AlertRule` (`alert_rules`)
```python
id                    Integer PK
name                  String(255) NOT NULL
metric                String(100)   # cpu_pct | ram_pct | disk_pct | offline
operator              String(10)    # > | < | ==
threshold             Float
severity              String(20)    # info | warning | critical
cooldown_minutes      Integer default 15
is_active             Boolean default True
customer_id           FK → customers (nullable = global rule)
notification_channels JSON          # {"email": ["addr@domain.com"]}
```

#### `Alert` (`alerts`)
```python
id              Integer PK
rule_id         FK → alert_rules
device_id       FK → devices
severity        String(20)
status          String(20) default 'open'   # open | acknowledged | resolved
message         Text
acknowledged_by FK → users (nullable)
created_at      DateTime
resolved_at     DateTime (nullable)
```

#### `Ticket` + `TicketComment`
```python
# Ticket
id           String/UUID PK
title        String(500) NOT NULL
description  Text
customer_id  FK → customers
device_id    FK → devices (nullable)
assignee_id  FK → users (nullable)      # Phase 8 addition
priority     String(20) default 'medium'  # low | medium | high | critical
status       String(20) default 'open'    # open | in_progress | resolved | closed
source       String(50)                   # manual | alert | agent
created_at   DateTime
updated_at   DateTime onupdate=now()

# TicketComment
id          Integer PK
ticket_id   FK → tickets
author_id   FK → users
body        Text NOT NULL
is_internal Boolean default False
created_at  DateTime
```

#### `Script` + `ScriptRun`
```python
# Script
id          String/UUID PK
name        String(255) NOT NULL
description Text          # used as __tag__ for built-in scripts
file_type   String(20)    # ps1 | bat | py | sh
content     Text NOT NULL
os_target   String(20) default 'windows'
is_builtin  Boolean default False
created_by  FK → users (nullable)
created_at  DateTime

# ScriptRun
id              String/UUID PK
script_id       FK → scripts  NOT NULL
device_id       FK → devices
triggered_by    FK → users (nullable)
exit_code       Integer
stdout          Text
stderr          Text
status          String(20) default 'pending'   # pending | running | completed | failed | timeout
timeout_seconds Integer default 300
started_at      DateTime (nullable)
completed_at    DateTime (nullable)
created_at      DateTime
```

#### `PatchPolicy` + `PatchRecord`
```python
# PatchPolicy
id                      Integer PK
name                    String(255) NOT NULL
customer_id             FK → customers (nullable)
auto_approve_critical   Boolean default True
auto_approve_important  Boolean default False
auto_approve_security   Boolean default False
reboot_behavior         String(50) default 'prompt'   # prompt | auto | never
maintenance_window_start String(10)   # HH:MM
maintenance_window_end   String(10)
excluded_software        JSON         # list of software name patterns to skip
is_active               Boolean default True

# PatchRecord
id           Integer PK
device_id    FK → devices
policy_id    FK → patch_policies (nullable)
patch_name   String(500)
kb_id        String(50)
patch_type   String(50)    # critical | security | definition | update | feature | driver
status       String(50) default 'pending'   # pending | approved | deployed | failed
deployed_at  DateTime (nullable)
created_at   DateTime
```

#### `AutomationProfile` + `ScheduledTaskRun`
```python
# AutomationProfile
id                   Integer PK
name                 String(255) NOT NULL
customer_id          FK → customers (nullable)
schedule_type        String(50)   # daily | weekly | monthly | once
schedule_day         String(20)   # monday..sunday or day-of-month
schedule_time        String(10)   # HH:MM
os_patch_config      JSON         # {install_all, critical, security, definition, ...}
software_patch_config JSON        # {update_all, excluded: [...]}
disk_config          JSON         # {defrag: bool, checkdisk: bool}
maintenance_config   JSON         # {delete_temp, restore_point, clear_history, reboot, shutdown}
notification_emails  String(500)
run_on_new_agents    Boolean default False
is_active            Boolean default True
last_run_at          DateTime (nullable)
created_at           DateTime

# ScheduledTaskRun
id             Integer PK
profile_id     FK → automation_profiles
device_id      FK → devices
status         String(20) default 'pending'
result_summary JSON
started_at     DateTime (nullable)
finished_at    DateTime (nullable)
created_at     DateTime
```

#### `Report`
```python
id            Integer PK
name          String(255)
template_type String(100)   # device_health | patch_compliance | alert_summary | software_inventory | ticket_summary
customer_id   FK → customers (nullable)
format        String(10) default 'csv'
file_path     String(500)   # absolute path to generated CSV in api/reports/
generated_by  FK → users (nullable)
created_at    DateTime

# IMPORTANT: to_dict() must include "file_path" for dashboard download to work
```

---

## 3. API Endpoints

All endpoints prefixed with `/api/`. Protected by `@jwt_required()` unless noted.

### Auth (`/api/auth/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | None | Email+password → access+refresh tokens |
| POST | `/refresh` | Refresh token | Rotate access token |
| POST | `/logout` | JWT | Revoke token |
| POST | `/me/force-change-password` | JWT | Set new password + clear `must_change_password` flag |

### Agents (`/api/agents/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/register` | None (org_token) | Register new agent, get device_id + agent_token |
| POST | `/<device_id>/heartbeat` | X-Agent-Token | Submit metrics, get queued tasks back |
| GET | `/<device_id>/tasks` | X-Agent-Token | Poll pending ScriptRun records |
| POST | `/<device_id>/task_result` | X-Agent-Token | Submit ScriptRun result |
| PUT | `/<device_id>/patches` | X-Agent-Token | Submit pending Windows patches list |
| PUT | `/<device_id>/software` | X-Agent-Token | Submit installed software list |

### Devices (`/api/devices/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List devices (paginated, filterable) |
| GET | `/<id>` | JWT | Get device + latest metrics |
| PUT | `/<id>` | JWT admin/tech | Update display_name, group_id |
| DELETE | `/<id>` | JWT admin | Remove device |
| GET | `/<id>/metrics` | JWT | Historical metrics (up to 168h) |
| GET | `/<id>/software` | JWT | Installed software list |
| POST | `/<id>/reboot` | JWT admin/tech | Queue reboot task |
| POST | `/<id>/shutdown` | JWT admin/tech | Queue shutdown task |
| POST | `/<id>/queue_task` | JWT admin/tech | Queue any built-in maintenance task |
| POST | `/<id>/deploy_patches` | JWT admin/tech | Trigger patch deployment via Celery |
| GET | `/platform_counts` | JWT | Returns `{"by_platform": {windows: N, ...}, "agentless": N}` |
| POST | `/<id>/ping_check` | JWT admin/tech | Ping device IP, update is_online/last_seen. Only for is_agentless=True devices. |

**`queue_task` valid `task_type` values:**
`clean_temp`, `defrag`, `check_disk`, `restore_point`, `clear_browser`, `reboot`, `shutdown`

### Alerts (`/api/alerts/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List alerts (filter by status, severity) |
| GET | `/rules` | JWT | List alert rules |
| POST | `/rules` | JWT admin/tech | Create alert rule |
| PUT | `/rules/<id>` | JWT admin/tech | Update alert rule |
| DELETE | `/rules/<id>` | JWT admin | Delete alert rule |
| POST | `/<id>/acknowledge` | JWT | Acknowledge alert |
| POST | `/<id>/resolve` | JWT | Resolve alert |

### Tickets (`/api/tickets/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List tickets (filter by status, priority) |
| POST | `/` | JWT tech/admin | Create ticket |
| GET | `/<id>` | JWT | Get ticket + comments |
| PUT | `/<id>` | JWT tech/admin | Update status, priority, assignee_id |
| DELETE | `/<id>` | JWT admin | Delete ticket |
| POST | `/<id>/comments` | JWT | Add comment |

### Scripts (`/api/scripts/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List scripts (filter built-in/custom) |
| POST | `/` | JWT tech/admin | Create script |
| PUT | `/<id>` | JWT tech/admin | Update script |
| DELETE | `/<id>` | JWT admin | Delete script |
| POST | `/<id>/run` | JWT tech/admin | Create ScriptRun records for target devices |
| GET | `/runs` | JWT | List recent ScriptRun records |
| GET | `/runs/<id>` | JWT | Get ScriptRun detail (stdout, stderr) |

### Patches (`/api/patches/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List patch records (filter by status, device) |
| PUT | `/<id>/approve` | JWT tech/admin | Approve a patch record |
| POST | `/approve_bulk` | JWT tech/admin | Approve multiple patch records |
| GET | `/policies` | JWT | List patch policies |
| POST | `/policies` | JWT admin | Create patch policy |
| PUT | `/policies/<id>` | JWT admin | Update patch policy |

### Automation (`/api/automation/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/profiles` | JWT | List automation profiles |
| POST | `/profiles` | JWT admin/tech | Create profile |
| PUT | `/profiles/<id>` | JWT admin/tech | Update profile |
| DELETE | `/profiles/<id>` | JWT admin | Delete profile |
| POST | `/profiles/<id>/run` | JWT admin/tech | Trigger immediate profile run |
| GET | `/runs` | JWT | List ScheduledTaskRun records |

### Reports (`/api/reports/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List reports |
| POST | `/` | JWT admin/tech | Create report + trigger generation |
| GET | `/<id>` | JWT | Get report metadata (includes file_path) |

### Billing (`/api/billing/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/invoices` | JWT | List invoices |
| POST | `/invoices` | JWT admin | Create invoice |
| PUT | `/invoices/<id>` | JWT admin | Update invoice status |

### Customers (`/api/customers/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | List customers |
| POST | `/` | JWT admin/tech | Create customer |
| GET | `/<id>` | JWT | Get customer detail |
| PUT | `/<id>` | JWT admin/tech | Update customer |
| DELETE | `/<id>` | JWT admin | Deactivate customer |

### Users (`/api/users/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT admin | List users |
| POST | `/` | JWT admin | Create user |
| PUT | `/<id>` | JWT admin | Update user (role, active, password) |

### Admin (`/api/admin/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users` | JWT admin | List all users |
| POST | `/users` | JWT admin | Create user — accepts `must_change_password` bool |
| PUT | `/users/<id>` | JWT admin | Update user — accepts `must_change_password` bool. Returns 403 if target is superadmin. |
| DELETE | `/users/<id>` | JWT admin | Delete user. Returns 403 if target is superadmin. |
| GET | `/org-token` | JWT admin | Return `ORG_REGISTRATION_TOKEN` for display in Admin panel |
| GET | `/server_ips` | None | Returns `{"hostname": "...", "lan_ips": ["192.168.x.x"]}` via socket.getaddrinfo |

### Network (`/api/network/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/scan` | JWT admin/tech | Trigger network discovery scan (dispatches `run_network_scan.delay`) |
| GET | `/scans` | JWT | List scan results |
| POST | `/agentless_devices` | JWT admin/tech | Batch upsert agentless devices. Body: `{"hosts": [...], "customer_id": optional}`. Returns `{"created": N, "updated": M, "skipped": K}`. |

### Dashboard Summary (`/api/dashboard/`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/summary` | JWT | Aggregated counts (devices, alerts, tickets, online) |
| GET | `/health_map` | JWT | Device health list (limit 500) — returned objects include `id`, `hostname`, `status`, `is_online`; used by Dashboard Overview to render clickable cards |
| GET | `/activity` | JWT | Recent audit log entries |

---

## 4. Authentication & Authorization

### JWT Flow

```
Login:
  POST /api/auth/login  {email, password}
  → {access_token, refresh_token, user: {id, email, role, full_name, must_change_password}}

Force password change (if must_change_password=True):
  Dashboard intercepts in app.py before showing any page.
  User fills new password form → POST /api/auth/me/force-change-password {new_password}
  → clears must_change_password flag → st.rerun() → normal dashboard

Dashboard stores:
  st.session_state["access_token"]   = access_token
  st.session_state["refresh_token"]  = refresh_token
  st.session_state["user"]           = user dict
  st.query_params["tok"]             = access_token   ← persists in URL
  st.query_params["rtok"]            = refresh_token  ← persists in URL

API call:
  Authorization: Bearer <access_token>

On 401:
  POST /api/auth/refresh  (Authorization: Bearer <refresh_token>)
  → {access_token}
  Update session_state, retry original request once

On page reload (F5) or navigation:
  Streamlit session state is wiped on browser reload.
  app.py reads st.query_params["tok"] and ["rtok"] before session state check.
  require_auth() in every page also re-reads and re-stamps both params.
  require_auth() re-stamps ?tok= and ?rtok= on every authenticated page
  load — ensures F5 on any page restores both access and refresh tokens,
  allowing silent renewal even after the 900s access token TTL expires.
```

> **NOTE:** Both access (`?tok=`) and refresh (`?rtok=`) tokens are stored in URL params.
> This is a pragmatic trade-off for Streamlit's stateless page reload model — without it,
> any F5 reload logs the user out. Mitigated by short access token TTL (900s default).
> In production with HTTPS, tokens in URL are not visible in transit but appear in server
> access logs — rotate `JWT_ACCESS_TOKEN_EXPIRES` to 300s for higher-security environments.

### Agent Token Flow

```
Agent registers:
  POST /api/agents/register
  Body: {hardware_id, hostname, platform, os_name, cpu_brand, cpu_cores,
         ram_gb, ip_local, mac_address, org_token}
  → {device_id, agent_token}

Stored in: agent/agent_state.json

Subsequent requests:
  Header: X-Agent-Token: <agent_token>

Token stored hashed in agent_tokens table.
On 401: agent re-registers (full registration flow).
```

### Role Permissions Matrix

| Action | viewer | technician | admin | superadmin |
|--------|--------|-----------|-------|-----------|
| View dashboard, devices, alerts | ✓ | ✓ | ✓ | ✓ |
| Create/update tickets | — | ✓ | ✓ | ✓ |
| Acknowledge/resolve alerts | — | ✓ | ✓ | ✓ |
| Run scripts | — | ✓ | ✓ | ✓ |
| Queue maintenance tasks | — | ✓ | ✓ | ✓ |
| Approve/deploy patches | — | ✓ | ✓ | ✓ |
| Manage automation profiles | — | ✓ | ✓ | ✓ |
| Create/update customers | — | ✓ | ✓ | ✓ |
| Generate reports | — | ✓ | ✓ | ✓ |
| Create/manage users | — | — | ✓ | ✓ |
| Delete any resource | — | — | ✓ | ✓ |
| View Admin page | — | — | ✓ | ✓ |
| Manage billing/invoices | — | — | ✓ | ✓ |
| Modify/delete superadmin account | — | — | — | — (CLI only) |

> **NOTE:** All `_require_role()` guards in all 9 route files include a superadmin bypass: `if claims.get("role") == "superadmin": return None`. The superadmin account itself cannot be modified or deleted via any API endpoint — use `api/reset_superadmin.py` for password changes.

---

## 5. Celery Tasks & Schedules

### Beat Schedule

| Task | Schedule | Module |
|------|----------|--------|
| `evaluate_all_rules` | Every 60s | `tasks.alert_tasks` |
| `mark_offline_devices` | Every 180s | `tasks.alert_tasks` |
| `sync_patch_status` | Every 1800s | `tasks.patch_tasks` |
| `ping_agentless_devices` | Every 300s | `tasks.network_tasks` |

### Task Signatures

#### `evaluate_all_rules()`
- Fetches all active alert rules
- For each rule, queries latest `DeviceMetrics` per device in scope
- Evaluates `metric operator threshold` (e.g., `cpu_pct > 90`)
- Respects `cooldown_minutes` — no duplicate alert within cooldown
- Creates `Alert` record on breach
- Calls `send_alert_notification()` if `notification_channels.email` is set

#### `mark_offline_devices()`
- Marks devices as `is_online=False` if `last_seen` > 5 minutes ago
- Creates offline alerts if a matching rule exists

#### `sync_patch_status()`
- Iterates all active `PatchPolicy` records
- For each policy's scope (customer or global):
  - Auto-approves `PatchRecord` rows where `status='pending'` matching policy flags
  - Respects `excluded_software` name patterns

#### `deploy_patches(device_id, patch_ids)`
- Looks up `PatchRecord` rows by ID
- Builds a PowerShell script using PSWindowsUpdate to install those KB IDs
- Creates or updates a `Script` record with tag `__deploy_patches_transient__`
- Creates a `ScriptRun` pointing to that script for the device
- Marks `PatchRecord.status = 'deployed'`

#### `generate_report(report_id)`
- Loads `Report` record by ID
- Dispatches to template-specific data collector:
  - `device_health` — all devices + batch-fetched latest metrics
  - `patch_compliance` — all patch records + device/policy joins
  - `alert_summary` — all alerts + rule names + device hostnames
  - `software_inventory` — all installed software + device hostnames
  - `ticket_summary` — all tickets + customer names
- Writes CSV to `api/reports/<report_id>_<name>.csv`
- Updates `report.file_path` in DB

#### `enqueue_profile_run(profile_id)`
- Loads `AutomationProfile`
- Queries all devices in scope (by `customer_id` or global)
- Calls `_dispatch_profile_tasks(profile, device_id, db_session)` per device
- Updates `profile.last_run_at`

#### `_dispatch_profile_tasks(profile, device_id, db_session)`
- Reads `disk_config` and `maintenance_config` JSON
- For each enabled task type, creates a `ScriptRun` pointing to the corresponding built-in script
- Also creates `ScriptRun` records for any custom scripts attached to the profile

#### `run_network_scan(scan_id)`
- Parses CIDR range from the `NetworkScan` record
- Concurrent ICMP ping sweep via `ThreadPoolExecutor(50)` — all IPs in range pinged in parallel
- For each live IP: ARP table lookup for MAC address, OUI vendor lookup via `lookup_vendor(mac)`
- Reverse DNS via `_get_hostname(ip)` runs **before** port probe so hostname is available for all fallbacks
- Detection pipeline (stops at first match):
  1. `_guess_platform(vendor)` — OUI vendor string keywords
  2. `_probe_platform(ip)` — TCP ports: 62078→iOS, 5555→Android, **2+ of** (445/3389/139)→Windows (2-port threshold prevents routers/NAS with only SMB from being misidentified), 548→macOS, 22→Linux; skipped entirely for router hostnames
  3. `_guess_platform_from_hostname(rdns)` — 50+ keyword match on rDNS hostname (brand names + Samsung model numbers S10–S24, Note, A12–A73, Fold, Flip, Ultra); catches Android phones with ADB disabled
- Router/gateway hostnames (`fritz.box`, `router`, `gateway`, `modem`, etc.) are included in `discovered_hosts` for scan display but **never persisted** as agentless device records
- Calls `_upsert_agentless_host(...)` for all non-router live hosts
- Updates `NetworkScan` record with status, host count, and completion timestamp

`_upsert_agentless_host` lookup order (stops at first match):
1. MAC address — primary stable key
2. IP address across ALL devices (not just agentless) — prevents duplicates for agent-managed PCs
3. Bare hostname match (strips `.fritz.box`/`.local`, case-insensitive) — catches multi-adapter machines where agent and scan see different MACs (e.g. Ethernet vs WiFi adapter)
- On match with non-agentless device: returns `"skipped"` — never modifies agent-managed records
- On match with agentless device: upgrades `platform`/`device_type` if currently "unknown" and new scan detects better info

> **NOTE:** Phones with fully randomized MACs and all ports blocked will still reach the hostname fallback. If the router assigns a model-name hostname (Fritz!Box, ASUS, TP-Link all do), the device will be identified. Devices that remain "unknown" after all three stages can be corrected via the Edit button on the agentless device row.

#### `ping_agentless_devices()`
- Loads all `Device` records where `is_agentless=True`
- Pings each device's `ip_address`
- Updates `is_online=True` and `last_seen=now()` on response
- Devices that have not responded for more than 10 minutes are marked `is_online=False`
- Changes committed in a single batch after all pings complete

### Starting Celery (Windows)

```bash
# Worker (must use --pool=solo on Windows — no fork())
celery -A tasks.celery_app worker --pool=solo -l info

# Beat scheduler (separate process)
celery -A tasks.celery_app beat -l info
```

---

## 6. Agent Internals

### Main Loop

```
startup
  ├─ load agent_state.json (device_id, token)
  ├─ if not registered: POST /api/agents/register → save state
  ├─ prime CPU counter: psutil.cpu_percent(interval=1)
  └─ loop every 60s:
       ├─ collect_metrics()          (non-blocking cpu_percent(interval=None))
       ├─ send_heartbeat(metrics)
       │    ├─ on 401: re-register
       │    └─ on connection error: exponential backoff 15s→300s
       ├─ get_tasks()
       │    └─ executor.run(task) for each queued task
       ├─ if time − last_patch > patch_interval:
       │    ├─ get_pending_patches()  (WUA COM via PowerShell)
       │    └─ report_patches(patches)
       └─ flush pending_results.json (Phase C-6 local queue)
```

### Task Execution

Agent receives tasks in format:
```json
{
  "type": "run_script",
  "run_id": "<uuid>",
  "script_type": "ps1",
  "script_content": "...",
  "timeout": 300
}
```

`executor.py` passes to `script_runner.py`:
- **ps1**: `powershell -NoProfile -NonInteractive -Command <content>` with `CREATE_NO_WINDOW`
- **bat**: `cmd /c <tempfile.bat>`
- **py**: `python <tempfile.py>`
- **sh**: `bash <tempfile.sh>` (Linux/macOS agents)

After execution, agent POSTs result to `/api/agents/<id>/task_result`:
```json
{
  "run_id": "<uuid>",
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "status": "completed"
}
```

### Patch Scanning

Uses PowerShell WUA COM object — requires no external package:
```powershell
$session  = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result   = $searcher.Search("IsInstalled=0 and Type='Software'")
```

Returns up to 500 patches as `[{name, kb_id, patch_type}]`. Reported via `PUT /api/agents/<id>/patches`. API deduplicates by `patch_name` and creates `PatchRecord` rows with `status='pending'`.

### Software Collection

`get_installed_software()` merges two sources, deduplicated by lowercase name:

| Source | Function | Notes |
|--------|----------|-------|
| Windows registry | `_get_registry_software()` | 3 hive paths, 20s hard deadline |
| winget | `_get_winget_software()` | Skips non-ASCII lines (progress bars); finds separator line before parsing |

**Winget parser detail:** `winget list` prints Unicode block-char progress bars (█▒░, `ord > 127`) before the real data table. The parser skips these lines, finds the first all-dash separator line (length > 10), then parses only lines after it. The dashboard adds a `_clean()` filter (strips U+2500–U+259F) as defence-in-depth before HTML rendering.

### Resilience Features

| Feature | Implementation |
|---------|---------------|
| Non-blocking CPU | `cpu_percent(interval=None)` after startup prime |
| Bounded process scan | Cap at 200 processes, 3s timeout |
| Bounded registry scan | 20s hard deadline |
| Winget Unicode parser | Skip `ord > 127` lines; locate separator line before data |
| Heartbeat backoff | 15s → 30s → 60s … → 300s cap on failure |
| 401 re-registration | Main loop checks status code, triggers full re-register |
| Local result queue | `pending_results.json`, cap 100, flushed each cycle |
| Structured logging | `DeviceFilter` injects device_id into all log records |

---

## 7. Built-in Scripts Reference

Built-in scripts are `Script` records with `is_builtin=True`. The `description` field stores the lookup tag. Created/updated at API startup via `ensure_builtin_scripts()`.

| task_type | Tag | Script name | What it does |
|-----------|-----|-------------|-------------|
| `clean_temp` | `__builtin_clean_temp__` | Built-in: Clean Temp Files | Removes `%TEMP%`, `%TMP%`, `C:\Windows\Temp` |
| `defrag` | `__builtin_defrag__` | Built-in: Defragment | `Optimize-Volume -DriveLetter C -Defrag` |
| `check_disk` | `__builtin_check_disk__` | Built-in: Check Disk | `chkdsk C: /f` — schedules for next reboot if drive locked; exits 0 in all cases |
| `restore_point` | `__builtin_restore_point__` | Built-in: Create Restore Point | `Checkpoint-Computer -Description "RMM"` |
| `clear_browser` | `__builtin_clear_browser__` | Built-in: Clear Browser History | Removes Chrome/Edge/Firefox cache dirs |
| `reboot` | `__builtin_reboot__` | Built-in: Reboot | `Restart-Computer -Force` |
| `shutdown` | `__builtin_shutdown__` | Built-in: Shutdown | `Stop-Computer -Force` |

**Adding a new built-in script:**
1. Add entry to `TASK_TYPE_TO_TAG` dict in `api/utils/builtin_scripts.py`
2. Add entry to `BUILTIN_SCRIPTS` dict with `name`, `content`, `file_type`
3. Restart the API — `ensure_builtin_scripts()` will create the DB record
4. Add the new `task_type` to any dispatch logic that should use it

**Transient scripts** (not in the built-in registry):
- `__deploy_patches_transient__` — created dynamically by `deploy_patches` Celery task per deployment run

---

## 8. Dashboard API Client

`dashboard/utils/api_client.py` — `RMMClient` class

### Session Management

```python
# One RMMClient per browser session, stored in st.session_state
def get_client():
    if "_rmm_client" not in st.session_state:
        st.session_state["_rmm_client"] = RMMClient(...)
    return st.session_state["_rmm_client"]
```

### Retry + 401 Refresh

```python
def _request(self, method, path, **kwargs):
    for attempt in range(3):
        try:
            resp = self.session.request(method, url, ...)
            if resp.status_code == 401 and attempt == 0:
                self._refresh_token()
                continue
            return resp.json(), None
        except (ConnectionError, Timeout):
            time.sleep([0.5, 1.0, 2.0][attempt])
    return None, "Service unavailable"
```

### Key Methods

| Method | HTTP | Path |
|--------|------|------|
| `list_devices(page, per_page, **filters)` | GET | `/api/devices/` |
| `get_device(device_id)` | GET | `/api/devices/<id>` |
| `queue_device_task(device_id, task_type, timeout=300)` | POST | `/api/devices/<id>/queue_task` |
| `reboot_device(device_id)` | POST | `/api/devices/<id>/reboot` |
| `shutdown_device(device_id)` | POST | `/api/devices/<id>/shutdown` |
| `deploy_patches(device_id, patch_ids)` | POST | `/api/devices/<id>/deploy_patches` |
| `list_tickets(**filters)` | GET | `/api/tickets/` |
| `create_ticket(data)` | POST | `/api/tickets/` |
| `update_ticket(ticket_id, data)` | PUT | `/api/tickets/<id>` |
| `add_comment(ticket_id, body, is_internal)` | POST | `/api/tickets/<id>/comments` |
| `list_alerts(**filters)` | GET | `/api/alerts/` |
| `list_customers(per_page)` | GET | `/api/customers/` |
| `list_users()` | GET | `/api/users/` |
| `force_change_password(new_password)` | POST | `/api/auth/me/force-change-password` |
| `list_patches(**filters)` | GET | `/api/patches/` |
| `approve_patches(patch_ids)` | POST | `/api/patches/approve_bulk` |
| `list_profiles()` | GET | `/api/automation/profiles` |
| `run_profile(profile_id)` | POST | `/api/automation/profiles/<id>/run` |
| `create_report(data)` | POST | `/api/reports/` |
| `list_reports()` | GET | `/api/reports/` |
| `get_platform_counts()` | GET | `/api/devices/platform_counts` |
| `ping_check_device(device_id)` | POST | `/api/devices/<id>/ping_check` |
| `upsert_agentless_devices(hosts, customer_id=None)` | POST | `/api/network/agentless_devices` |
| `trigger_network_scan(customer_id, scan_range)` | POST | `/api/network/scan` |
| `get_server_ips()` | GET | `/api/admin/server_ips` |
| `update_device(device_id, data)` | PUT | `/api/devices/<id>` |
| `delete_device(device_id)` | DELETE | `/api/devices/<id>` |

### Cache Strategy

```python
@st.cache_data(ttl=30)   # fast-changing: devices, alerts
@st.cache_data(ttl=60)   # medium: tickets, customers
@st.cache_data(ttl=120)  # slow-changing: scripts, users, patch policies
```

---

## 9. Performance Optimizations

### Database

| Optimization | Location | Detail |
|-------------|----------|--------|
| Composite indexes | Alembic migration | `device_metrics(device_id, collected_at)`, `alerts(status, severity)`, etc. |
| Batch latest metrics | `routes/devices.py:_batch_latest_metrics()` | Subquery MAX(id) per device — 1 query instead of N |
| Dashboard aggregation | `routes/dashboard.py` | 4 DB aggregations replace 8 COUNT queries |
| Health map cap | `routes/dashboard.py` | `.limit(500)` prevents full-table load |
| N+1 agent tasks | `routes/agents.py` | Pre-fetch scripts by id dict before loop |
| DB connection pool | `config.py` | `pool_size=10, max_overflow=20, pool_pre_ping=True` |

### Celery

| Optimization | Detail |
|-------------|--------|
| `acks_late=True` | Task not acknowledged until completion — survives worker crash |
| `OperationalError` retry | DB connection drops retry with exponential backoff |
| Automation offloaded | Device-loop in `enqueue_profile_run` runs in Celery, not in request thread |

### Dashboard

| Optimization | Detail |
|-------------|--------|
| `RMMClient` session reuse | One `requests.Session` per browser session — persistent HTTP connection |
| Retry backoff | `ConnectionError`/`Timeout` only — 0.5s/1.0s/2.0s |
| `st.cache_data` | TTL caching on list endpoints — prevents repeated API calls on re-renders |
| `st.spinner` | All data loads wrapped — user sees progress feedback |
| Graceful degradation | `st.warning` instead of `st.stop()` — page stays interactive on partial failure |

### Metrics History — 7-Day Fallback

`dashboard/pages/04_Devices.py` — `_render_agent_row()` metrics history block.

Default window: 24 hours (`GET /api/devices/<id>/metrics?hours=24`). If the API returns an empty list (agent was offline for >24h), the dashboard retries with `hours=168` (7 days). On fallback:
- An `st.info` banner shows: *"No data in last 24 h — showing last N readings (oldest ~Xh ago). Agent may be offline."*
- Chart title changes from `"24-hour usage history"` to `"7-day usage history (agent offline)"`.
- If the 7-day window is also empty, `st.warning("No metric history available.")` is shown.

The `collected_at` timezone handling: `pd.to_datetime()` preserves tz-aware timestamps; the "hours ago" calculation converts to UTC via `.tz_convert("UTC")` before diffing against `pd.Timestamp.now(tz="UTC")`.

### Device Health Map — Clickable Cards

Cards in `dashboard/pages/01_Dashboard.py` use `st.button()` + `st.switch_page()` for reliable Streamlit-native navigation. Plain `<a href>` links and `components.html()` with `window.parent.location.href` are intercepted/sandboxed by Streamlit's SPA router and do not work.

**Navigation flow:**
1. User clicks a health map card → `st.session_state["_nav_device"] = str(device_id)` → `st.switch_page("pages/04_Devices.py")`
2. `04_Devices.py` reads `st.session_state.pop("_nav_device", None)` on load, falls back to `st.query_params.get("device")` for direct URL access
3. If matched, pre-fills search box with the device hostname and shows an info banner

**CSS scoping:** Card button styles are injected inside the `else` branch of the health map render and use `section[data-testid="stMain"] button[kind="secondary"]` to target only main-area secondary buttons — sidebar buttons are excluded. Refresh button uses `type="primary"` to opt out of card styling entirely.

---

## 10. Extension Guide

### Adding a New Dashboard Page

1. Create `dashboard/pages/NN_PageName.py`
2. Follow the standard page template:
```python
import streamlit as st
from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css

st.set_page_config(page_title="Page Name — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

st.markdown('<h1 style="margin:0">Page Name</h1>', unsafe_allow_html=True)

with st.spinner("Loading..."):
    data, err = client.some_method()
if err:
    st.warning(f"Could not load data — {err}")
    st.stop()
```
3. Add a nav link in `dashboard/utils/nav.py` under the appropriate section

### Adding a New API Route

1. Create `api/routes/mymodule.py`:
```python
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from extensions import db

mymodule_bp = Blueprint("mymodule", __name__)

@mymodule_bp.route("/", methods=["GET"])
@jwt_required()
def list_items():
    ...
    return jsonify({"items": [...]}), 200
```
2. Register in `api/app.py`:
```python
from routes import mymodule
app.register_blueprint(mymodule.mymodule_bp, url_prefix='/api/mymodule')
```
3. Add corresponding method to `dashboard/utils/api_client.py`

### Adding a New Built-in Script

1. Edit `api/utils/builtin_scripts.py`:
```python
# Add to TASK_TYPE_TO_TAG:
"my_task": "__builtin_my_task__",

# Add to BUILTIN_SCRIPTS:
"my_task": {
    "name": "Built-in: My Task",
    "content": "# PowerShell script here\nWrite-Output 'Done'",
    "file_type": "ps1",
},
```
2. Restart the API — `ensure_builtin_scripts()` creates the DB record automatically
3. Optionally add the `task_type` to `_dispatch_profile_tasks()` in `tasks/automation_tasks.py`
4. Optionally add a UI button in the relevant dashboard page calling `client.queue_device_task(device_id, "my_task")`

### Adding WiFi/Agentless Devices

**For Windows/Linux/macOS laptops on the same WiFi/LAN:**

1. Find the server's LAN IP: Admin → System Info → Server IP Addresses, or check your router.
2. Copy the `agent/` folder to the target machine (USB, network share, or git clone).
3. On the target machine, install dependencies:
   ```bash
   cd agent
   python -m venv venv
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```
4. Run the setup helper — patches `config.ini` automatically:
   ```bash
   python setup_agent.py 192.168.x.x <org_token>
   ```
   The org token is shown in Admin → System Info → Agent Enrollment Token.
5. Start the agent:
   ```bash
   python rmm_agent.py
   ```
6. The device appears in Devices → Windows/Linux/macOS tab within 60 seconds.

**For phones, tablets, and IoT devices (no agent possible):**

1. Go to Network Discovery in the dashboard.
2. Enter the subnet in CIDR notation (e.g. `192.168.1.0/24`) and optionally assign a customer.
3. Click **Scan Network** — the scan takes 15–30 seconds via concurrent ICMP ping.
4. Discovered devices appear with IP, MAC, vendor (from OUI lookup), and detected platform.
   - iOS devices are identified by Apple OUI prefixes, or by port 62078 being open (port probe fallback).
   - Android devices are identified by Samsung/Google/OnePlus/etc. OUI prefixes, or by port 5555 being open.
   - When OUI lookup returns unknown, `_probe_platform(ip)` tries 6 TCP ports to detect the OS.
   - Reverse DNS (`_get_hostname`) populates a friendly hostname (e.g. `Printer.local`) when available.
5. Click **Save All to Devices** to persist them to the database.
6. Devices appear in Devices → Android/iOS/Agentless tabs.
7. Celery beat pings them every 5 minutes — online/offline status updates within 10 minutes of disconnect.

**Identifying devices that evade automated detection (randomized MAC + closed ports):**

Modern phones randomize their MAC address per network, defeating OUI lookup. They also typically block all probed ports. These devices will remain platform "unknown" after a scan. Use the **Edit** button on the agentless device row in the Devices page to manually set hostname, platform, and device_type. This calls `PUT /api/devices/<id>` via `client.update_device(device_id, data)`.

### Adding a New Report Template

1. Add to `tasks/report_tasks.py`:
```python
def _my_template(report, db_session):
    rows = db_session.query(MyModel).all()
    return [{"col1": r.field1, "col2": r.field2} for r in rows]
```
2. Register in the dispatcher dict inside `generate_report()`:
```python
COLLECTORS = {
    ...
    "my_template": _my_template,
}
```
3. Add option to the template dropdown in `dashboard/pages/08_Reports.py`

---

## 11. Security Model

### Network Boundaries

| Surface | Exposure | Notes |
|---------|----------|-------|
| Streamlit `:8501` | LAN/localhost only | No direct user data — proxies to API |
| Flask API `:5000` | LAN/localhost only | All auth enforced via JWT |
| PostgreSQL `:5432` | localhost only | `rmm_app` user has no superuser |
| Redis `:6379` | localhost only | No password in dev (add one for production) |

### Authentication Layers

1. **Dashboard users** — JWT (HS256, `JWT_SECRET_KEY`), 900s access / 7d refresh
2. **Agents** — `X-Agent-Token` header, token stored as SHA256 hash in `agent_tokens` table
3. **API startup** — `ORG_REGISTRATION_TOKEN` required for agent registration
4. **Superadmin** — seeded at every API startup via `ensure_superadmin()` in `api/utils/superadmin.py`; bypasses all `_require_role()` checks; cannot be deleted or modified via API; password reset via `api/reset_superadmin.py` CLI

### Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| JWT token theft | Short expiry (900s). HTTPS in production. Token never in URL. |
| Script injection | Scripts stored as plain text — reviewed before running. Runs as agent service account only. |
| Privilege escalation | Role enforced at API level via `get_jwt()` claims check on every mutation endpoint |
| Celery task injection | Tasks only dispatched by authenticated API endpoints or beat schedule |
| DB credentials in env | `.env` in `.gitignore`. Never committed. |
| Report file exposure | `api/reports/` not served via HTTP. Download reads bytes directly in dashboard. |
| SMTP credential exposure | `SMTP_PASS` read from env only. Never logged. |
| Superadmin lockout | Auto-seeded at every API startup — account always exists. Emergency password reset: `cd api ; python reset_superadmin.py <new_password>` |

### Production Checklist

- [ ] Set `FLASK_DEBUG=0`
- [ ] Use HTTPS (nginx reverse proxy with Let's Encrypt)
- [ ] Add Redis password: `requirepass <password>` in Memurai config
- [ ] Rotate `ORG_REGISTRATION_TOKEN` after all agents registered
- [ ] Change default admin password from `Admin1234!`
- [ ] Set up automated PostgreSQL backups
- [ ] Move `api/reports/` to a dedicated volume outside the project root
- [ ] Run agent as a dedicated low-privilege Windows service account (not SYSTEM)
- [ ] Enable MFA for admin accounts (MFA secret generation is wired in the User model)

---

## 12. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✓ | — | PostgreSQL connection string |
| `SECRET_KEY` | ✓ | — | Flask secret key (32-byte hex) |
| `JWT_SECRET_KEY` | ✓ | — | JWT signing key (32-byte hex) |
| `ORG_REGISTRATION_TOKEN` | ✓ | — | Agent registration shared secret |
| `JWT_ACCESS_TOKEN_EXPIRES` | — | `900` | Access token TTL in seconds |
| `JWT_REFRESH_TOKEN_EXPIRES` | — | `604800` | Refresh token TTL in seconds |
| `REDIS_URL` | — | `redis://localhost:6379/0` | Redis connection URL |
| `CELERY_BROKER_URL` | — | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | — | `redis://localhost:6379/1` | Celery result backend |
| `API_BASE_URL` | — | `http://localhost:5000` | Used by dashboard to reach API |
| `SMTP_HOST` | — | — | SMTP server (omit to disable email alerts) |
| `SMTP_PORT` | — | `587` | SMTP port |
| `SMTP_USER` | — | — | SMTP login username |
| `SMTP_PASS` | — | — | SMTP login password (use app-specific password) |
| `SMTP_FROM` | — | `SMTP_USER` | From address for alert emails |
| `SUPERADMIN_EMAIL` | — | `superadmin@rmm.local` | Email for the auto-seeded superadmin account |
| `SUPERADMIN_PASSWORD` | — | `SuperAdmin@RMM1` | Password for the auto-seeded superadmin account. Change in production. |
| `FLASK_ENV` | — | `production` | Set to `development` for debug mode |
| `FLASK_DEBUG` | — | `0` | Set to `1` only in development |

Generate secrets:
```bash
python -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY, JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(24))"   # ORG_REGISTRATION_TOKEN
```
