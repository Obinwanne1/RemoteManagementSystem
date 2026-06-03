# SKILL.md — Recreate RMM System A-Z

> NinjaOne-style Remote Monitoring & Management system.
> Stack: Flask API + Streamlit dashboard + Python agent + PostgreSQL + Redis/Celery.
> All 9 phases + A/B/C optimization pass complete.

---

## Prerequisites

### 1. Install PostgreSQL 15

Download: https://www.enterprisedb.com/downloads/postgres-postgresql-installer

During install:
- Port: `5432`
- Superuser password: set something — you will need it

After install, open pgAdmin or psql and run:

```sql
CREATE USER rmm_app WITH PASSWORD 'changeme';
CREATE DATABASE rmmdb OWNER rmm_app;
GRANT ALL PRIVILEGES ON DATABASE rmmdb TO rmm_app;
```

### 2. Install Memurai (Redis for Windows)

Download: https://www.memurai.com/get-memurai

Install with defaults. Service auto-starts on port `6379`.

Verify: `redis-cli ping` → should return `PONG`

### 3. Python 3.11+

Download: https://www.python.org/downloads/

Check: `python --version`

---

## Project Layout

```
RemoteManagementSystem/
├── .claude/
│   └── state.md
├── .env
├── .env.example
├── .gitignore
├── CLAUDE.md
├── SKILL.md
├── HANDOVER_GUIDE.md
├── TECHNICAL_GUIDE.md
├── api/
│   ├── app.py
│   ├── config.py
│   ├── extensions.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── reports/              ← CSV output dir (created at runtime)
│   ├── models/               ← 11 SQLAlchemy model files
│   ├── routes/               ← 13 route modules
│   ├── tasks/                ← Celery task modules
│   └── utils/
│       ├── builtin_scripts.py
│       └── notifications.py
├── dashboard/
│   ├── app.py
│   ├── requirements.txt
│   ├── .streamlit/config.toml
│   ├── pages/                ← 16 Streamlit pages
│   └── utils/
│       ├── api_client.py
│       ├── auth.py
│       ├── nav.py
│       ├── styles.py
│       └── formatters.py
├── agent/
│   ├── rmm_agent.py
│   ├── collector.py
│   ├── executor.py
│   ├── heartbeat.py
│   ├── script_runner.py
│   ├── config.ini
│   └── requirements.txt
└── scripts_library/
    └── windows/
```

---

## Phase 1 — Bootstrap Project

```bash
mkdir RemoteManagementSystem
cd RemoteManagementSystem
git init
```

Create `.gitignore`:
```
.env
__pycache__/
*.pyc
*/venv/
*.egg-info/
.DS_Store
*.log
*.db
reports/
```

---

## Phase 2 — API Backend

### 2.1 Create venv + install deps

```bash
cd api
python -m venv venv
venv\Scripts\activate
pip install flask flask-sqlalchemy flask-migrate flask-jwt-extended flask-cors flask-limiter celery redis psycopg2-binary bcrypt pyotp marshmallow python-dateutil requests python-dotenv gunicorn
pip freeze > requirements.txt
```

### 2.2 `api/extensions.py`

```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
```

### 2.3 `api/config.py`

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / '.env')

class Config:
    SECRET_KEY = os.environ['SECRET_KEY']
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ['JWT_SECRET_KEY']
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 900))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 604800))
    JWT_TOKEN_LOCATION = ['headers', 'cookies']
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
    RATELIMIT_DEFAULT = "200 per minute"
    ORG_REGISTRATION_TOKEN = os.environ['ORG_REGISTRATION_TOKEN']
```

### 2.4 `api/app.py` (with Phase 5 built-in script sync)

```python
from flask import Flask
from config import Config
from extensions import db, migrate, jwt, cors, limiter

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    limiter.init_app(app)

    from routes import auth, agents, customers, devices, alerts
    from routes import tickets, patches, scripts, automation
    from routes import reports, billing, network, dashboard, users

    for bp, prefix in [
        (auth.auth_bp,         '/api/auth'),
        (agents.agents_bp,     '/api/agents'),
        (customers.customers_bp, '/api/customers'),
        (devices.devices_bp,   '/api/devices'),
        (alerts.alerts_bp,     '/api/alerts'),
        (tickets.tickets_bp,   '/api/tickets'),
        (patches.patches_bp,   '/api/patches'),
        (scripts.scripts_bp,   '/api/scripts'),
        (automation.automation_bp, '/api/automation'),
        (reports.reports_bp,   '/api/reports'),
        (billing.billing_bp,   '/api/billing'),
        (network.network_bp,   '/api/network'),
        (dashboard.dashboard_bp, '/api/dashboard'),
        (users.users_bp,       '/api/users'),
    ]:
        app.register_blueprint(bp, url_prefix=prefix)

    @app.route('/api/health')
    def health():
        return {'status': 'ok'}

    # Sync built-in scripts on startup (Phase 5)
    with app.app_context():
        try:
            from utils.builtin_scripts import ensure_builtin_scripts
            ensure_builtin_scripts()
        except Exception:
            app.logger.warning("Could not sync built-in scripts (DB may not be ready yet)")

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### 2.5 Models (11 files in `api/models/`)

See full model code in TECHNICAL_GUIDE.md. Key notes:

- `DeviceMetrics`: field is `collected_at` (not `recorded_at`)
- `Script`: has `is_builtin = db.Column(db.Boolean, default=False)` flag
- `ScriptRun`: `script_id` is NOT NULL FK — all tasks go through Script records
- `AutomationProfile`: JSON columns `disk_config`, `maintenance_config`, `os_patch_config`, `software_patch_config`
- `Report`: `file_path` exposed in `to_dict()` so dashboard can read CSV for download

### 2.6 Run Migrations

```bash
cd api
venv\Scripts\activate
flask db init
flask db migrate -m "initial"
flask db upgrade
```

### 2.7 Seed DB

```bash
python seed.py
# Creates: admin@rmm.local / Admin1234! + Default Customer + built-in scripts
```

---

## Phase 3 — Celery Tasks

### `api/tasks/celery_app.py`

```python
from celery import Celery
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / '.env')

celery_app = Celery(
    'rmm',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=[
        'tasks.alert_tasks',
        'tasks.patch_tasks',
        'tasks.automation_tasks',
        'tasks.report_tasks',
    ]
)

celery_app.conf.beat_schedule = {
    'evaluate-alerts-every-60s': {
        'task': 'tasks.alert_tasks.evaluate_all_rules',
        'schedule': 60.0,
    },
    'mark-offline-devices-every-3m': {
        'task': 'tasks.alert_tasks.mark_offline_devices',
        'schedule': 180.0,
    },
    'sync-patch-status-every-30-min': {
        'task': 'tasks.patch_tasks.sync_patch_status',
        'schedule': 1800.0,
    },
}

celery_app.conf.task_acks_late = True
celery_app.conf.worker_pool = 'solo'  # Windows: no fork()
```

### Task modules

| File | Tasks | Schedule |
|------|-------|---------|
| `tasks/alert_tasks.py` | `evaluate_all_rules`, `mark_offline_devices` | 60s / 180s beat |
| `tasks/patch_tasks.py` | `deploy_patches(device_id, patch_ids)`, `sync_patch_status` | on-demand / 1800s beat |
| `tasks/automation_tasks.py` | `enqueue_profile_run(profile_id)` | triggered per profile schedule |
| `tasks/report_tasks.py` | `generate_report(report_id)` | triggered on report creation |

---

## Phase 4 — Agent

### 4.1 `agent/config.ini`

```ini
[api]
base_url = http://localhost:5000
org_token = YOUR_ORG_REGISTRATION_TOKEN

[agent]
interval_seconds = 60
software_sync_hours = 6
patch_interval = 3600
version = 0.1.0
log_level = INFO
```

### 4.2 `agent/collector.py` (key functions)

```python
import psutil, socket, platform, hashlib, uuid

def collect_hardware_info():
    hostname = socket.gethostname()
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff)
                    for i in range(0, 48, 8)][::-1])
    return {
        'hostname': hostname,
        'platform': platform.system().lower(),
        'os_name': platform.system(),
        'os_version': platform.version(),
        'cpu_brand': platform.processor(),
        'cpu_cores': psutil.cpu_count(),
        'ram_gb': round(psutil.virtual_memory().total / (1024**3), 2),
        'ip_local': socket.gethostbyname(hostname),
        'mac_address': mac,
        'hardware_id': hashlib.sha256(f"{hostname}{mac}".encode()).hexdigest()
    }

def collect_metrics():
    # Non-blocking CPU sample (Phase C-1): prime at startup, then interval=None
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                'mountpoint': part.mountpoint,
                'device': part.device,
                'total_gb': round(usage.total / (1024**3), 2),
                'used_gb':  round(usage.used  / (1024**3), 2),
                'free_gb':  round(usage.free  / (1024**3), 2),
                'percent':  usage.percent,
            })
        except PermissionError:
            pass
    battery = psutil.sensors_battery()
    # Bounded process scan (Phase C-3): 3s deadline, 200-process cap
    procs = sorted(
        psutil.process_iter(['pid', 'name', 'cpu_percent']),
        key=lambda p: p.info['cpu_percent'] or 0, reverse=True
    )[:5]
    return {
        'cpu_pct': cpu,
        'ram_pct': ram.percent,
        'disk_pct': disks[0]['percent'] if disks else 0,
        'battery_pct': battery.percent if battery else None,
        'uptime_seconds': int(psutil.boot_time()),
        'disks': disks,
        'top_processes': [{'pid': p.info['pid'], 'name': p.info['name'],
                           'cpu': p.info['cpu_percent']} for p in procs]
    }

def get_pending_patches():
    """Query Windows Update Agent for pending patches via WUA COM (Phase 6)."""
    import subprocess, json
    ps = r"""
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$result = $searcher.Search("IsInstalled=0 and Type='Software'")
$patches = @()
foreach ($u in $result.Updates) {
    $patches += @{name=$u.Title; kb_id=($u.KBArticleIDs -join ','); patch_type='software'}
}
$patches | ConvertTo-Json -Compress
"""
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
            timeout=60, creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        data = json.loads(out.decode('utf-8', errors='replace').strip() or '[]')
        if isinstance(data, dict):
            data = [data]
        return data[:500]
    except Exception:
        return []
```

### 4.3 `agent/heartbeat.py` (key methods)

```python
import requests, configparser
from pathlib import Path

class APIClient:
    def __init__(self):
        cfg = configparser.ConfigParser()
        cfg.read(Path(__file__).parent / 'config.ini', encoding='utf-8')
        self.base_url = cfg['api']['base_url']
        self.org_token = cfg['api']['org_token']
        self.device_token = None
        self.device_id = None

    def register(self, hw_info):
        resp = requests.post(f'{self.base_url}/api/agents/register',
            json={**hw_info, 'org_token': self.org_token}, timeout=10)
        data = resp.json()
        self.device_token = data['agent_token']
        self.device_id = data['device_id']
        return data

    def send_heartbeat(self, metrics):
        """Returns (data, status_code). Caller checks 401 for re-registration (Phase C-5)."""
        resp = requests.post(
            f'{self.base_url}/api/agents/{self.device_id}/heartbeat',
            json={'metrics': metrics},
            headers={'X-Agent-Token': self.device_token},
            timeout=10
        )
        return resp.json(), resp.status_code

    def get_tasks(self):
        resp = requests.get(
            f'{self.base_url}/api/agents/{self.device_id}/tasks',
            headers={'X-Agent-Token': self.device_token},
            timeout=10
        )
        return resp.json()

    def report_patches(self, patches: list) -> bool:
        """Phase 6: report pending OS patches to API."""
        resp = requests.put(
            f'{self.base_url}/api/agents/{self.device_id}/patches',
            json={'patches': patches},
            headers={'X-Agent-Token': self.device_token},
            timeout=30
        )
        return resp.status_code == 200
```

### 4.4 `agent/rmm_agent.py` (main loop)

```python
import time, logging, json
from pathlib import Path
from collector import collect_hardware_info, collect_metrics, get_pending_patches
from heartbeat import APIClient
from executor import TaskExecutor

STATE_FILE  = Path(__file__).parent / 'agent_state.json'
RESULT_FILE = Path(__file__).parent / 'pending_results.json'  # Phase C-6

def main():
    client   = APIClient()
    executor = TaskExecutor(client)

    # Load or register
    state = json.loads(STATE_FILE.read_text(encoding='utf-8')) if STATE_FILE.exists() else {}
    if 'device_id' not in state:
        hw = collect_hardware_info()
        # Prime CPU counter (Phase C-1)
        import psutil; psutil.cpu_percent(interval=1)
        data = client.register(hw)
        state.update({'device_id': data['device_id'], 'token': data['agent_token']})
        STATE_FILE.write_text(json.dumps(state), encoding='utf-8')
    else:
        client.device_id    = state['device_id']
        client.device_token = state['token']

    backoff      = 15          # Phase C-4 exponential backoff
    last_patch   = 0.0
    patch_interval = 3600      # configurable in config.ini

    while True:
        try:
            metrics = collect_metrics()
            data, status = client.send_heartbeat(metrics)
            if status == 401:
                # Re-register (Phase C-5)
                hw = collect_hardware_info()
                client.register(hw)
                continue
            backoff = 15       # reset on success

            tasks = client.get_tasks()
            for task in tasks.get('tasks', []):
                executor.run(task)

            # Patch scan cycle (Phase 6)
            if time.time() - last_patch > patch_interval:
                patches = get_pending_patches()
                if patches:
                    client.report_patches(patches)
                last_patch = time.time()

        except Exception as e:
            logging.error(f'Loop error: {e}')
            time.sleep(min(backoff, 300))
            backoff = min(backoff * 2, 300)
            continue

        time.sleep(60)

if __name__ == '__main__':
    main()
```

---

## Phase 5 — Built-in Scripts + Maintenance Dispatch

### Why this design

`ScriptRun.script_id` is NOT NULL — all device tasks must point to a `Script` record. Instead of a new DB table, Phase 5 creates 7 PowerShell scripts as `Script` rows with `is_builtin=True` at API startup. Maintenance actions queue `ScriptRun` records against these built-in scripts. The agent picks them up via the existing `get_tasks` poll.

### `api/utils/builtin_scripts.py` (core of Phase 5)

```python
TASK_TYPE_TO_TAG = {
    "clean_temp":    "__builtin_clean_temp__",
    "defrag":        "__builtin_defrag__",
    "check_disk":    "__builtin_check_disk__",
    "restore_point": "__builtin_restore_point__",
    "clear_browser": "__builtin_clear_browser__",
    "reboot":        "__builtin_reboot__",
    "shutdown":      "__builtin_shutdown__",
}

BUILTIN_SCRIPTS = {
    "clean_temp": {
        "name": "Built-in: Clean Temp Files",
        "content": "Remove-Item -Path $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue",
        "file_type": "ps1",
    },
    "defrag": {
        "name": "Built-in: Defragment",
        "content": "Optimize-Volume -DriveLetter C -Defrag -Verbose",
        "file_type": "ps1",
    },
    # check_disk: chkdsk C: /f — schedules for next reboot if drive locked; exits 0 always
    # restore_point, clear_browser, reboot, shutdown: see builtin_scripts.py for full content
}

def ensure_builtin_scripts():
    """Upsert Script records for all built-in task types. Called at app startup."""
    from models.script import Script
    from extensions import db
    for task_type, tag in TASK_TYPE_TO_TAG.items():
        spec = BUILTIN_SCRIPTS[task_type]
        existing = Script.query.filter_by(name=spec["name"]).first()
        if not existing:
            s = Script(name=spec["name"], content=spec["content"],
                       file_type=spec["file_type"], is_builtin=True,
                       description=tag)
            db.session.add(s)
    db.session.commit()

def get_builtin_script_id(task_type: str):
    """Return Script.id for a task_type, or None."""
    from models.script import Script
    tag = TASK_TYPE_TO_TAG.get(task_type)
    if not tag:
        return None
    s = Script.query.filter_by(description=tag, is_builtin=True).first()
    return s.id if s else None
```

### Device task queue endpoint

`POST /api/devices/<device_id>/queue_task`
Body: `{"task_type": "clean_temp", "timeout_seconds": 300}`

Valid `task_type` values: `clean_temp`, `defrag`, `check_disk`, `restore_point`, `clear_browser`, `reboot`, `shutdown`

### Automation profile dispatch (`api/tasks/automation_tasks.py`)

```python
def _dispatch_profile_tasks(profile, device_id, db_session):
    """Create ScriptRun records for all enabled tasks in a profile."""
    from utils.builtin_scripts import get_builtin_script_id
    from models.script import ScriptRun

    disk_cfg  = profile.disk_config or {}
    maint_cfg = profile.maintenance_config or {}

    task_map = {
        'defrag':       disk_cfg.get('defrag'),
        'check_disk':   disk_cfg.get('checkdisk'),
        'clean_temp':   maint_cfg.get('delete_temp'),
        'restore_point': maint_cfg.get('restore_point'),
        'clear_browser': maint_cfg.get('clear_history'),
        'reboot':       maint_cfg.get('reboot'),
        'shutdown':     maint_cfg.get('shutdown'),
    }

    for task_type, enabled in task_map.items():
        if not enabled:
            continue
        script_id = get_builtin_script_id(task_type)
        if script_id:
            db_session.add(ScriptRun(
                script_id=script_id,
                device_id=device_id,
                timeout_seconds=1800 if task_type == 'defrag' else 300,
            ))
```

---

## Phase 6 — Patch Management

### Flow

1. Agent calls `get_pending_patches()` every `patch_interval` seconds (default 3600s)
2. Agent calls `PUT /api/agents/<device_id>/patches` with patch list
3. API deduplicates by patch name, creates `PatchRecord` rows with `status="pending"`
4. Celery beat runs `sync_patch_status()` every 30 min — auto-approves based on `PatchPolicy` flags
5. Dashboard shows patches; technician clicks "Deploy Selected"
6. Dashboard calls `POST /api/devices/<device_id>/deploy_patches` with `patch_ids`
7. Celery `deploy_patches.delay(device_id, patch_ids)` builds a PS1 script, creates a `ScriptRun`, marks patches as "deployed"

### `api/tasks/patch_tasks.py` key logic

```python
@celery_app.task
def deploy_patches(device_id: str, patch_ids: list):
    """Build transient PS1 script from approved patches, create ScriptRun."""
    # Finds PatchRecords by ID, builds Install-WindowsUpdate call
    # Creates/updates Script record with tag __deploy_patches_transient__
    # Creates ScriptRun pointing to that script
    # Marks PatchRecords as status='deployed'

@celery_app.task
def sync_patch_status():
    """Auto-approve patches based on PatchPolicy flags."""
    # Iterates PatchPolicies
    # Checks auto_approve_critical, auto_approve_security, etc.
    # Respects excluded_software list
    # Updates matching PatchRecord.status to 'approved'
```

---

## Phase 7 — Alert Email Notifications

### `api/utils/notifications.py`

```python
import smtplib, os
from email.mime.text import MIMEText

def send_alert_notification(rule_name: str, device_hostname: str,
                             message: str, emails: list):
    """Send email alert. No-ops silently if SMTP_HOST not configured."""
    host = os.environ.get('SMTP_HOST')
    if not host or not emails:
        return
    port = int(os.environ.get('SMTP_PORT', 587))
    user = os.environ.get('SMTP_USER', '')
    pwd  = os.environ.get('SMTP_PASS', '')
    from_addr = os.environ.get('SMTP_FROM', user)

    msg = MIMEText(f"Rule: {rule_name}\nDevice: {device_hostname}\n\n{message}")
    msg['Subject'] = f"[RMM Alert] {rule_name} — {device_hostname}"
    msg['From']    = from_addr
    msg['To']      = ', '.join(emails)

    with smtplib.SMTP(host, port) as smtp:
        if port != 25:
            smtp.starttls()
        if user:
            smtp.login(user, pwd)
        smtp.sendmail(from_addr, emails, msg.as_string())
```

Integration in `alert_tasks.py`:
```python
channels = rule.notification_channels or {}
emails   = channels.get('email', [])
if emails:
    from utils.notifications import send_alert_notification
    send_alert_notification(rule.name, device.hostname, alert.message, emails)
```

Required `.env` vars (all optional — skip to disable email):
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
SMTP_FROM=rmm@yourcompany.com
```

---

## Phase 8 — Ticket Assignment

Ticket model has `assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)`.

Dashboard `02_Tickets.py` uses three columns per ticket: Update Status | Assign To | Add Comment.

`PUT /api/tickets/<id>` accepts `{"assignee_id": <user_id>}` — same endpoint as status update.

---

## Phase 9 — Report Generation

### Flow

1. Dashboard `POST /api/reports` creates a `Report` record and returns `report.id`
2. API immediately dispatches `generate_report.delay(report.id)`
3. Celery worker runs `generate_report(report_id)`:
   - Queries DB for the relevant data based on `template_type`
   - Writes CSV to `api/reports/<report_id>_<name>.csv`
   - Updates `report.file_path` in DB
4. Dashboard polls or refreshes — when `file_path` is set, shows download button
5. `st.download_button` reads file bytes directly from disk path

### Templates

| `template_type` | Data collected |
|---|---|
| `device_health` | All devices + latest metrics (batch query) |
| `patch_compliance` | All patch records + device names |
| `alert_summary` | All alerts + rule names + device names |
| `software_inventory` | All installed software + device names |
| `ticket_summary` | All tickets + customer names |

### `Report.to_dict()` must include `file_path`

```python
def to_dict(self):
    return {
        'id': self.id,
        'name': self.name,
        'template_type': self.template_type,
        'format': self.format,
        'file_path': self.file_path,   # ← required for dashboard download
        'has_file': bool(self.file_path),
        'created_at': self.created_at.isoformat() if self.created_at else None,
    }
```

---

## Phase A — API Optimizations

| Item | What was done |
|------|--------------|
| A-1 | Composite DB indexes on 6 high-query tables (Alembic migration) |
| A-2 | Dashboard summary: 8 COUNT queries → 4 aggregations |
| A-3 | Health map `.all()` → `.limit(500)` |
| A-4 | N+1 devices/metrics: batch fetch latest metric per device via subquery |
| A-5 | N+1 agents/tasks: pre-fetch scripts by id dict |
| A-6 | Automation device-loop offloaded to Celery |
| A-7 | DB pool: `pool_size=10`, `max_overflow=20` |
| A-8 | Global Flask error handlers (400/404/409/503/500) |
| A-9 | Request logging middleware (before/after_request with ms timing) |
| A-10 | Celery `acks_late=True`, retry on `OperationalError` |

---

## Phase B — Dashboard Optimizations

| Item | What was done |
|------|--------------|
| B-1 | `requests.Session` reuse via `st.session_state["_rmm_client"]` |
| B-2 | Retry on transient failures: 3 attempts, backoff 0.5/1.0/2.0s |
| B-3 | Token auto-refresh on 401 (POST /api/auth/refresh, retry once) |
| B-4 | Access token persisted in `?tok=` URL param; refresh token in `?rtok=`. Both re-stamped on every authenticated page load by `require_auth()` so F5 restores full session |
| B-5 | `st.cache_data` wrappers (TTL 30–120s by endpoint type) |
| B-6 | `st.spinner` on all data loads across all 16 pages |
| B-7 | Replaced hard `st.stop()` with `st.warning` (graceful degradation) |
| B-8 | Contextual error messages on all pages |

---

## Phase C — Agent Optimizations

| Item | What was done |
|------|--------------|
| C-1 | Non-blocking CPU sample: `interval=None` + startup prime |
| C-2 | Bounded registry enumeration: 20s hard deadline |
| C-3 | Bounded process scan: 3s deadline + 200-process cap |
| C-4 | Exponential backoff on heartbeat failures: 15s → 300s cap |
| C-5 | 401 re-registration flow in main loop |
| C-6 | Local task result queue: `pending_results.json`, cap 100, flush each cycle |
| C-7 | Structured logging with `DeviceFilter` + classified exception types |

---

## Phase 5 — Dashboard Setup

### 5.1 Install deps

```bash
cd dashboard
python -m venv venv
venv\Scripts\activate
pip install streamlit plotly pandas requests python-dotenv
pip freeze > requirements.txt
```

### 5.2 `.streamlit/config.toml`

```toml
[server]
port = 8501
headless = true

[theme]
base = "dark"
primaryColor = "#407E3C"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1a1f2e"
textColor = "#ffffff"
```

### 5.3 `dashboard/utils/nav.py` (shared sidebar, Phase B)

```python
import streamlit as st

def render_sidebar():
    """Render the shared sidebar with 5 nav sections."""
    user = st.session_state.get('user', {})
    # ... user card, role pill, 5 nav sections:
    # MONITORING: Overview, Devices, Alerts
    # MANAGEMENT: Tickets, Customers, Automation
    # PATCHING: OS Patches, Software Patches
    # TOOLS: Scripts, Disk Management, Maintenance, Network Discovery
    # BUSINESS: Reports, Billing, Admin
```

### 5.4 Dashboard pages (16 pages)

| File | Purpose |
|------|---------|
| `01_Dashboard.py` | Overview metrics, device health map, recent alerts, activity feed |
| `02_Tickets.py` | Create/view/update/assign/comment tickets |
| `03_Customers.py` | Customer CRUD, device count per customer |
| `04_Devices.py` | Device list, detail view, metrics charts |
| `05_Alerts.py` | Alert rules config, active alerts, acknowledge/resolve |
| `06_App_Center.py` | Software inventory across devices |
| `07_Network_Discovery.py` | Trigger scans, view discovered hosts |
| `08_Reports.py` | Generate reports, download CSV |
| `09_Billing.py` | Invoice list, create invoice |
| `10_Admin.py` | User management, audit logs, agent enrollment token (Reveal/Hide card) |
| `11_Automation.py` | Automation profile CRUD, run history |
| `12_OS_Patches.py` | OS patch status, approve, deploy patches |
| `13_Software_Patches.py` | Software patch status |
| `14_Disk_Management.py` | Disk usage gauges, summary table, maintenance actions |
| `15_Maintenance.py` | Remote actions (reboot/shutdown/clean/restore/chkdsk/browser) with confirm gate |
| `16_Scripts.py` | Script library, run scripts on devices, view run history |

---

## Environment File

`.env`:
```env
DATABASE_URL=postgresql://rmm_app:changeme@localhost:5432/rmmdb
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
JWT_ACCESS_TOKEN_EXPIRES=900
JWT_REFRESH_TOKEN_EXPIRES=604800
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
ORG_REGISTRATION_TOKEN=<python -c "import secrets; print(secrets.token_hex(24))">
API_BASE_URL=http://localhost:5000
DASHBOARD_URL=http://localhost:8501
# SMTP (optional — omit to disable email alerts)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
SMTP_FROM=rmm@yourcompany.com
```

---

## Start Everything

Open 5 terminals:

**Terminal 1 — Flask API**
```bash
cd api ; venv\Scripts\activate ; python app.py
```

**Terminal 2 — Celery Worker**
```bash
cd api ; venv\Scripts\activate ; celery -A tasks.celery_app worker --pool=solo -l info
```

**Terminal 3 — Celery Beat** (scheduled tasks)
```bash
cd api ; venv\Scripts\activate ; celery -A tasks.celery_app beat -l info
```

**Terminal 4 — Dashboard**
```bash
cd dashboard ; venv\Scripts\activate ; streamlit run app.py
```

**Terminal 5 — Agent** (run as Administrator for patch scanning)
```bash
cd agent ; venv\Scripts\activate ; python rmm_agent.py
```

---

## Verify Health

```bash
curl http://localhost:5000/api/health      # → {"status": "ok"}
curl -s http://localhost:8501              # → 200
redis-cli ping                             # → PONG
psql -U rmm_app -d rmmdb -c "SELECT 1"    # → 1
```

---

## Port Kill (Windows)

```powershell
netstat -ano | findstr :5000
taskkill /F /PID <PID>
```

---

## Default Login

| Field | Value |
|-------|-------|
| URL | http://localhost:8501 |
| Email | admin@rmm.local |
| Password | Admin1234! |

Change password after first login.

---

## Security Checklist

- [ ] `.env` never committed (in `.gitignore`)
- [ ] `SECRET_KEY` and `JWT_SECRET_KEY` are random 32-byte hex strings
- [ ] `ORG_REGISTRATION_TOKEN` rotated after all agents registered (token visible in Admin → System Info → Agent Enrollment Token card)
- [ ] `rmm_app` DB user has no superuser privileges
- [ ] Rate limiting active on `/api/auth/login` (10/min)
- [ ] JWT tokens expire (900s access, 7d refresh)
- [ ] Agent tokens hashed before storing
- [ ] No `FLASK_DEBUG=1` in production
- [ ] `SMTP_PASS` is an app-specific password, not your Gmail password
- [ ] `api/reports/` directory not exposed via HTTP

---

## Key Architecture Decisions

| Decision | Reason |
|----------|--------|
| Flask + SQLAlchemy | Simple, well-known, easy to extend |
| PostgreSQL over SQLite | Production-grade, concurrent writes |
| Celery + Redis | Async tasks for long-running ops (defrag, reports, patch deploy) |
| Streamlit dashboard | Rapid UI with minimal JS |
| JWT auth | Stateless, works for API + dashboard |
| `pool=solo` Celery | Windows has no `fork()` |
| Hardware fingerprint = SHA256(hostname+MAC) | Unique device ID without agent install key |
| bcrypt rounds=12 | Balance security vs login latency |
| Built-in scripts as Script records | Avoids new DB migration; reuses existing ScriptRun task queue |
| `file_path` on Report | Dashboard and API on same machine; bytes read directly — no file serving needed |
| SMTP gated on env var | Email optional; missing config silently skips, no crash |
