# SKILL.md — Recreate RMM System A-Z

> NinjaOne-style Remote Monitoring & Management system.
> Stack: Flask API + Streamlit dashboard + Python agent + PostgreSQL + Redis/Celery.

---

## Prerequisites

### 1. Install PostgreSQL 15

Download: https://www.enterprisedb.com/downloads/postgres-postgresql-installer

During install:
- Port: `5432`
- Superuser password: set something — you'll need it

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
├── api/
│   ├── app.py
│   ├── config.py
│   ├── extensions.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── models/
│   ├── routes/
│   ├── tasks/
│   └── migrations/
├── dashboard/
│   ├── app.py
│   ├── requirements.txt
│   ├── .streamlit/config.toml
│   ├── pages/         (16 pages)
│   └── utils/
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
```

Create `CLAUDE.md` with project rules (copy from repo).

---

## Phase 2 — API Backend

### 2.1 Create venv + install deps

```bash
cd api
python -m venv venv
venv\Scripts\activate
pip install flask flask-sqlalchemy flask-migrate flask-jwt-extended flask-cors flask-limiter celery redis psycopg2-binary bcrypt pyotp marshmallow reportlab openpyxl python-dateutil requests python-dotenv gunicorn
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
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 300, 'pool_pre_ping': True}
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

### 2.4 `api/app.py`

```python
from flask import Flask
from api.config import Config
from api.extensions import db, migrate, jwt, cors, limiter

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    limiter.init_app(app)

    from api.routes import auth, agents, customers, devices, alerts
    from api.routes import tickets, patches, scripts, automation
    from api.routes import reports, billing, network, dashboard

    for bp in [auth.bp, agents.bp, customers.bp, devices.bp, alerts.bp,
               tickets.bp, patches.bp, scripts.bp, automation.bp,
               reports.bp, billing.bp, network.bp, dashboard.bp]:
        app.register_blueprint(bp, url_prefix='/api')

    @app.route('/api/health')
    def health():
        return {'status': 'ok'}

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### 2.5 Models (11 files in `api/models/`)

#### `api/models/__init__.py`
```python
from .user import User
from .customer import Customer, DeviceGroup
from .device import Device, DeviceMetrics, InstalledSoftware
from .alert import AlertRule, Alert
from .ticket import Ticket, TicketComment
from .patch import PatchPolicy, PatchRecord
from .script import Script, ScriptRun
from .automation import AutomationProfile, ScheduledTaskRun
from .report import Report
from .billing import Invoice
from .audit import AgentToken, AuditLog, NetworkScan
```

#### `api/models/user.py`
```python
from api.extensions import db
import bcrypt

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255))
    role = db.Column(db.String(50), default='technician')  # admin, technician, viewer
    mfa_secret = db.Column(db.String(32))
    mfa_enabled = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt(12)
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'), self.password_hash.encode('utf-8')
        )
```

#### `api/models/customer.py`
```python
from api.extensions import db

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    tier = db.Column(db.String(50), default='standard')
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    devices = db.relationship('Device', backref='customer', lazy='dynamic')

class DeviceGroup(db.Model):
    __tablename__ = 'device_groups'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
```

#### `api/models/device.py`
```python
from api.extensions import db
import json

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    hostname = db.Column(db.String(255))
    platform = db.Column(db.String(50))   # windows, linux, mac
    os_name = db.Column(db.String(255))
    os_version = db.Column(db.String(100))
    cpu_brand = db.Column(db.String(255))
    cpu_cores = db.Column(db.Integer)
    ram_gb = db.Column(db.Float)
    serial_number = db.Column(db.String(255))
    ip_local = db.Column(db.String(50))
    ip_public = db.Column(db.String(50))
    mac_address = db.Column(db.String(50))
    hardware_id = db.Column(db.String(64), unique=True)
    status = db.Column(db.String(50), default='active')
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime)
    agent_version = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class DeviceMetrics(db.Model):
    __tablename__ = 'device_metrics'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    cpu_pct = db.Column(db.Float)
    ram_pct = db.Column(db.Float)
    disk_pct = db.Column(db.Float)
    battery_pct = db.Column(db.Float)
    uptime_seconds = db.Column(db.BigInteger)
    top_processes = db.Column(db.JSON)
    disks = db.Column(db.JSON)
    recorded_at = db.Column(db.DateTime, server_default=db.func.now())

class InstalledSoftware(db.Model):
    __tablename__ = 'installed_software'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    name = db.Column(db.String(255))
    version = db.Column(db.String(100))
    publisher = db.Column(db.String(255))
    install_date = db.Column(db.String(20))
    source = db.Column(db.String(50))  # registry, winget, chocolatey
    synced_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/alert.py`
```python
from api.extensions import db

class AlertRule(db.Model):
    __tablename__ = 'alert_rules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    metric = db.Column(db.String(100))  # cpu_pct, ram_pct, disk_pct, offline
    operator = db.Column(db.String(10))  # >, <, ==
    threshold = db.Column(db.Float)
    severity = db.Column(db.String(20), default='warning')  # info, warning, critical
    cooldown_minutes = db.Column(db.Integer, default=15)
    is_active = db.Column(db.Boolean, default=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)

class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('alert_rules.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    severity = db.Column(db.String(20))
    status = db.Column(db.String(20), default='open')  # open, acknowledged, resolved
    message = db.Column(db.Text)
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    resolved_at = db.Column(db.DateTime, nullable=True)
```

#### `api/models/ticket.py`
```python
from api.extensions import db

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='open')      # open, in_progress, resolved, closed
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())
    comments = db.relationship('TicketComment', backref='ticket', lazy='dynamic')

class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'))
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    body = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/patch.py`
```python
from api.extensions import db

class PatchPolicy(db.Model):
    __tablename__ = 'patch_policies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    auto_approve_critical = db.Column(db.Boolean, default=True)
    auto_approve_important = db.Column(db.Boolean, default=False)
    reboot_behavior = db.Column(db.String(50), default='prompt')  # prompt, auto, never
    maintenance_window_start = db.Column(db.String(10))  # HH:MM
    maintenance_window_end = db.Column(db.String(10))
    is_active = db.Column(db.Boolean, default=True)

class PatchRecord(db.Model):
    __tablename__ = 'patch_records'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    policy_id = db.Column(db.Integer, db.ForeignKey('patch_policies.id'), nullable=True)
    patch_name = db.Column(db.String(500))
    kb_id = db.Column(db.String(50))
    status = db.Column(db.String(50), default='pending')  # pending, installed, failed
    deployed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/script.py`
```python
from api.extensions import db

class Script(db.Model):
    __tablename__ = 'scripts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    file_type = db.Column(db.String(20))  # ps1, bat, py, sh
    content = db.Column(db.Text, nullable=False)
    os_target = db.Column(db.String(20), default='windows')
    is_builtin = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class ScriptRun(db.Model):
    __tablename__ = 'script_runs'
    id = db.Column(db.Integer, primary_key=True)
    script_id = db.Column(db.Integer, db.ForeignKey('scripts.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    triggered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    exit_code = db.Column(db.Integer)
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/automation.py`
```python
from api.extensions import db

class AutomationProfile(db.Model):
    __tablename__ = 'automation_profiles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    schedule_type = db.Column(db.String(50))  # daily, weekly, monthly
    schedule_time = db.Column(db.String(10))  # HH:MM
    os_patch_config = db.Column(db.JSON)
    software_patch_config = db.Column(db.JSON)
    disk_config = db.Column(db.JSON)
    maintenance_config = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class ScheduledTaskRun(db.Model):
    __tablename__ = 'scheduled_task_runs'
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('automation_profiles.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    status = db.Column(db.String(20), default='pending')
    result_summary = db.Column(db.JSON)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/report.py`
```python
from api.extensions import db

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    template_type = db.Column(db.String(100))  # executive_summary, device_health, patch_compliance
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    format = db.Column(db.String(10), default='pdf')  # pdf, xlsx
    file_path = db.Column(db.String(500))
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/billing.py`
```python
from api.extensions import db

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    device_count = db.Column(db.Integer)
    rate_per_device = db.Column(db.Float, default=15.0)
    total = db.Column(db.Float)
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, overdue
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
```

#### `api/models/audit.py`
```python
from api.extensions import db

class AgentToken(db.Model):
    __tablename__ = 'agent_tokens'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    token_hash = db.Column(db.String(255), unique=True)
    issued_at = db.Column(db.DateTime, server_default=db.func.now())
    is_revoked = db.Column(db.Boolean, default=False)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(255))
    resource_type = db.Column(db.String(100))
    resource_id = db.Column(db.Integer)
    ip_address = db.Column(db.String(50))
    payload = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class NetworkScan(db.Model):
    __tablename__ = 'network_scans'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    scan_range = db.Column(db.String(50))
    discovered_hosts = db.Column(db.JSON)
    status = db.Column(db.String(20), default='pending')
    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    completed_at = db.Column(db.DateTime, nullable=True)
```

### 2.6 Run Migrations

```bash
cd api
venv\Scripts\activate
flask db init
flask db migrate -m "initial"
flask db upgrade
```

### 2.7 Seed DB

`api/seed.py`:
```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.app import create_app
from api.extensions import db
from api.models import User, Customer

def seed():
    app = create_app()
    with app.app_context():
        if not User.query.filter_by(email='admin@rmm.local').first():
            u = User(email='admin@rmm.local', full_name='Admin', role='admin')
            u.set_password('Admin1234!')
            db.session.add(u)
        if not Customer.query.filter_by(slug='default').first():
            c = Customer(name='Default Customer', slug='default')
            db.session.add(c)
        db.session.commit()
        print('Seeded.')

if __name__ == '__main__':
    seed()
```

```bash
python api/seed.py
```

---

## Phase 3 — Celery Tasks

`api/tasks/celery_app.py`:
```python
from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / '.env')

celery_app = Celery(
    'rmm',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    include=['api.tasks.alert_tasks', 'api.tasks.patch_tasks',
             'api.tasks.maintenance_tasks', 'api.tasks.report_tasks']
)

celery_app.conf.beat_schedule = {
    'evaluate-alerts': {
        'task': 'api.tasks.alert_tasks.evaluate_all_rules',
        'schedule': 60.0,
    },
    'mark-offline-devices': {
        'task': 'api.tasks.alert_tasks.mark_offline_devices',
        'schedule': 180.0,
    },
}

celery_app.conf.worker_pool = 'solo'  # Windows requirement
```

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
version = 0.1.0
log_level = INFO
```

### 4.2 `agent/collector.py` (key functions)

```python
import psutil
import socket
import platform
import hashlib
import uuid

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
        'hardware_id': hashlib.sha256(
            f"{hostname}{mac}".encode()
        ).hexdigest()
    }

def collect_metrics():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({'mount': part.mountpoint,
                          'total_gb': round(usage.total / (1024**3), 2),
                          'used_pct': usage.percent})
        except PermissionError:
            pass
    battery = psutil.sensors_battery()
    procs = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']),
                   key=lambda p: p.info['cpu_percent'], reverse=True)[:5]
    return {
        'cpu_pct': cpu,
        'ram_pct': ram.percent,
        'disk_pct': disks[0]['used_pct'] if disks else 0,
        'battery_pct': battery.percent if battery else None,
        'uptime_seconds': int(psutil.boot_time()),
        'disks': disks,
        'top_processes': [{'pid': p.info['pid'], 'name': p.info['name'],
                           'cpu': p.info['cpu_percent']} for p in procs]
    }
```

### 4.3 `agent/heartbeat.py` (API client)

```python
import requests
import configparser
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

    def heartbeat(self, metrics):
        return requests.post(
            f'{self.base_url}/api/agents/heartbeat',
            json={'device_id': self.device_id, 'metrics': metrics},
            headers={'X-Agent-Token': self.device_token},
            timeout=10
        ).json()

    def poll_tasks(self):
        return requests.get(
            f'{self.base_url}/api/agents/tasks',
            params={'device_id': self.device_id},
            headers={'X-Agent-Token': self.device_token},
            timeout=10
        ).json()
```

### 4.4 `agent/rmm_agent.py` (main loop)

```python
import time
import logging
from pathlib import Path
from collector import collect_hardware_info, collect_metrics
from heartbeat import APIClient
from executor import TaskExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'rmm_agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / 'agent_state.json'

def load_state():
    import json
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    return {}

def save_state(state):
    import json
    STATE_FILE.write_text(json.dumps(state), encoding='utf-8')

def main():
    client = APIClient()
    executor = TaskExecutor(client)
    state = load_state()

    if 'device_id' not in state:
        log.info('Registering agent...')
        hw = collect_hardware_info()
        data = client.register(hw)
        state['device_id'] = data['device_id']
        state['token'] = data['agent_token']
        save_state(state)
        log.info(f"Registered as device {state['device_id']}")
    else:
        client.device_id = state['device_id']
        client.device_token = state['token']

    while True:
        try:
            metrics = collect_metrics()
            client.heartbeat(metrics)
            tasks = client.poll_tasks()
            for task in tasks.get('tasks', []):
                executor.run(task)
        except Exception as e:
            log.error(f'Loop error: {e}')
        time.sleep(60)

if __name__ == '__main__':
    main()
```

---

## Phase 5 — Dashboard

### 5.1 Setup

```bash
cd dashboard
python -m venv venv
venv\Scripts\activate
pip install streamlit==1.58.0 plotly==6.1.2 pandas==2.3.3 requests==2.32.3 python-dotenv==1.1.0
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

### 5.3 `dashboard/utils/api_client.py`

```python
import requests
import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()

BASE = os.getenv('API_BASE_URL', 'http://localhost:5000')

def get_headers():
    token = st.session_state.get('access_token')
    return {'Authorization': f'Bearer {token}'} if token else {}

def api_get(path, params=None):
    try:
        r = requests.get(f'{BASE}/api{path}', headers=get_headers(),
                         params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f'API error: {e}')
        return None

def api_post(path, data):
    try:
        r = requests.post(f'{BASE}/api{path}', json=data,
                          headers=get_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f'API error: {e}')
        return None
```

### 5.4 `dashboard/app.py` (login)

```python
import streamlit as st
from utils.api_client import api_post

st.set_page_config(page_title='RMM', layout='wide', page_icon='🖥️')

# Brand CSS
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #1a1f2e; }
.stButton > button { background: #407E3C; color: white; border: none; }
.stButton > button:hover { background: #5a9e56; }
</style>
""", unsafe_allow_html=True)

if 'access_token' not in st.session_state:
    st.title('RMM Login')
    with st.form('login'):
        email = st.text_input('Email')
        password = st.text_input('Password', type='password')
        if st.form_submit_button('Login'):
            resp = api_post('/auth/login', {'email': email, 'password': password})
            if resp and 'access_token' in resp:
                st.session_state.access_token = resp['access_token']
                st.session_state.user = resp['user']
                st.rerun()
            else:
                st.error('Invalid credentials')
else:
    st.switch_page('pages/01_Dashboard.py')
```

### 5.5 Dashboard pages structure (16 pages)

| File | Purpose |
|------|---------|
| `01_Dashboard.py` | Overview metrics, online devices count, open alerts/tickets |
| `02_Tickets.py` | Create, view, update, comment on tickets |
| `03_Customers.py` | Customer CRUD, device count per customer |
| `04_Devices.py` | Device list, detail view, metrics charts |
| `05_Alerts.py` | Alert rules config, active alerts list, acknowledge |
| `06_App_Center.py` | Software inventory across devices |
| `07_Network_Discovery.py` | Trigger scans, view discovered hosts |
| `08_Reports.py` | Generate PDF/XLSX reports |
| `09_Billing.py` | Invoice list, create invoice |
| `10_Admin.py` | User management, audit logs |
| `11_Automation.py` | Automation profile CRUD, run history |
| `12_OS_Patches.py` | OS patch status, deploy patches |
| `13_Software_Patches.py` | Software patch status |
| `14_Disk_Management.py` | Disk usage charts per device |
| `15_Maintenance.py` | Maintenance tasks, schedules |
| `16_Scripts.py` | Script library, run scripts on devices |

Each page follows this pattern:
```python
import streamlit as st
from utils.api_client import api_get, api_post
from utils.auth import require_auth

require_auth()
st.title('Page Title')
data = api_get('/endpoint')
if data:
    # render with st.dataframe, st.metric, plotly charts
```

---

## Phase 6 — Environment File

`.env`:
```env
DATABASE_URL=postgresql://rmm_app:changeme@localhost:5432/rmmdb
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
JWT_ACCESS_TOKEN_EXPIRES=900
JWT_REFRESH_TOKEN_EXPIRES=604800
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
API_HOST=0.0.0.0
API_PORT=5000
DASHBOARD_URL=http://localhost:8501
ORG_REGISTRATION_TOKEN=<generate: python -c "import secrets; print(secrets.token_hex(24))">
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
DASHBOARD_PORT=8501
API_BASE_URL=http://localhost:5000
```

`.env.example` — same but with placeholder values, committed to git.

---

## Phase 7 — Start Everything

Open 4 terminals:

**Terminal 1 — Flask API**
```bash
cd api
venv\Scripts\activate
python app.py
```

**Terminal 2 — Celery Worker**
```bash
cd api
venv\Scripts\activate
celery -A tasks.celery_app worker --pool=solo -l info
```

**Terminal 3 — Celery Beat** (optional, for scheduled tasks)
```bash
cd api
venv\Scripts\activate
celery -A tasks.celery_app beat -l info
```

**Terminal 4 — Dashboard**
```bash
cd dashboard
venv\Scripts\activate
streamlit run app.py
```

**Terminal 5 — Agent** (run as Administrator)
```bash
cd agent
venv\Scripts\activate
python rmm_agent.py
```

---

## Verify Health

```bash
# API alive
curl http://localhost:5000/api/health

# Dashboard alive
curl http://localhost:8501

# Redis alive
redis-cli ping

# DB alive
psql -U rmm_app -d rmmdb -c "SELECT 1"
```

---

## Port Kill (Windows)

```powershell
# Find process on port
netstat -ano | findstr :5000

# Kill it
taskkill /F /PID <PID>
```

---

## Default Login

| Field | Value |
|-------|-------|
| URL | http://localhost:8501 |
| Email | admin@rmm.local |
| Password | Admin1234! |

**Change password after first login.**

---

## Build Order Reference

```
Phase 1  — Agent Core + API scaffold + DB models
Phase 2  — API CRUD verified with real DB + tests
Phase 3  — Dashboard UI refinement
Phase 4  — Scripts library + execution
Phase 5  — Automation profiles
Phase 6  — Patch management (OS + software)
Phase 7  — Alerts system
Phase 8  — Ticket system
Phase 9  — Reports + Billing + Polish
```

---

## Security Checklist

- [ ] `.env` never committed (in `.gitignore`)
- [ ] `SECRET_KEY` and `JWT_SECRET_KEY` are random 32-byte hex strings
- [ ] `ORG_REGISTRATION_TOKEN` rotated after all agents registered
- [ ] `rmm_app` DB user has no superuser privileges
- [ ] Rate limiting active on `/api/auth/login` (10/min)
- [ ] JWT tokens expire (900s access, 7d refresh)
- [ ] Agent tokens hashed before storing
- [ ] No `FLASK_DEBUG=1` in production

---

## Key Architecture Decisions

| Decision | Reason |
|----------|--------|
| Flask + SQLAlchemy | Simple, well-known, easy to extend |
| PostgreSQL over SQLite | Production-grade, concurrent writes |
| Celery + Redis | Async task queue for long-running ops |
| Streamlit dashboard | Rapid UI with minimal JS |
| JWT auth | Stateless, works for API + dashboard |
| `pool=solo` Celery | Windows has no `fork()` |
| Hardware fingerprint = SHA256(hostname+MAC) | Unique device ID without agent install key |
| bcrypt rounds=12 | Balance security vs login latency |
