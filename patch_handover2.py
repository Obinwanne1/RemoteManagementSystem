#!/usr/bin/env python3
"""Patch HANDOVER_GUIDE.md - save first, then verify."""
import sys

PATH = r'C:\Users\rigwe\Desktop\RemoteManagementSystem\HANDOVER_GUIDE.md'

with open(PATH, encoding='utf-8') as f:
    content = f.read()

original_len = len(content)

# ── 1. Update .env template in Chapter 4 ─────────────────────────────────────
OLD = (
    "    SMTP_HOST=smtp.gmail.com\n"
    "    SMTP_PORT=587\n"
    "    SMTP_USER=\n"
    "    SMTP_PASSWORD=\n"
    "    SMTP_FROM=RMM System <noreply@yourcompany.com>\n"
    "    ```"
)
NEW = (
    "    SUPERADMIN_PASSWORD=YourSuperAdminPassword123\n"
    "    SUPERADMIN_EMAIL=superadmin@rmm.local\n"
    "    CORS_ORIGINS=http://localhost:8501\n"
    "    SMTP_HOST=smtp.gmail.com\n"
    "    SMTP_PORT=587\n"
    "    SMTP_USER=\n"
    "    SMTP_PASSWORD=\n"
    "    SMTP_FROM=RMM System <noreply@yourcompany.com>\n"
    "    ```"
)
assert OLD in content, "env block not found"
content = content.replace(OLD, NEW, 1)

# ── 2. Add SUPERADMIN_PASSWORD to substitutions table ────────────────────────
OLD2 = (
    "    | `replace-with-a-unique-org-token-for-agent-registration` "
    "| A unique token agents use to register (e.g., `rmm-prod-2026-companyname-abc123`) |\n"
    "\n"
    "> **IMPORTANT:** The `ORG_REGISTRATION_TOKEN`"
)
NEW2 = (
    "    | `replace-with-a-unique-org-token-for-agent-registration` "
    "| A unique token agents use to register (e.g., `rmm-prod-2026-companyname-abc123`) |\n"
    "    | `YourSuperAdminPassword123` | A strong password (min 10 characters) for the built-in superadmin account. "
    "**Required** -- the API will refuse to start without this set. |\n"
    "\n"
    "> **IMPORTANT:** The `ORG_REGISTRATION_TOKEN`"
)
assert OLD2 in content, "substitutions table tail not found"
content = content.replace(OLD2, NEW2, 1)

# ── 3. Update health check JSON in Chapter 5 ─────────────────────────────────
OLD3 = (
    '2. You should see a JSON response like: '
    '`{"status": "ok", "database": "connected", "redis": "connected"}`\n'
    '3. If any service shows "disconnected", check that respective service is running.'
)
NEW3 = (
    '2. You should see a JSON response like: '
    '`{"status": "ok", "db": true, "redis": true, "version": "1.0.0"}`. '
    'A `"status": "degraded"` response means PostgreSQL or Redis is unreachable -- '
    'the health endpoint now tests actual connectivity, not just configuration.\n'
    '3. If `db` or `redis` is `false`, check that the respective service is running.'
)
assert OLD3 in content, "health check text not found"
content = content.replace(OLD3, NEW3, 1)

# ── 4. Update Chapter 9 login steps -- add MFA note ──────────────────────────
OLD4 = (
    "7. Correct credentials take you to the RMM Dashboard.\n"
    "8. \"Invalid credentials\" means wrong email or password. Check Caps Lock.\n"
    "\n"
    "> **NOTE:** Your session token is stored in browser memory only -- it is not in the URL. "
    "If you share a page URL, the recipient must log in with their own credentials."
)
NEW4 = (
    "7. If your account has **Multi-Factor Authentication (MFA)** enabled, you will see a "
    "second screen asking for a 6-digit code from your authenticator app. Enter the code "
    "and click **Verify ->**. See Chapter 9a for full MFA details.\n"
    "8. Correct credentials (and MFA code if required) take you to the RMM Dashboard.\n"
    "9. \"Invalid credentials\" means wrong email or password. Check Caps Lock.\n"
    "\n"
    "> **NOTE:** Your session is maintained in browser memory. If you share a page URL, "
    "the recipient must log in with their own credentials."
)
assert OLD4 in content, "login steps not found"
content = content.replace(OLD4, NEW4, 1)

# ── 5. Update superadmin default credentials section ─────────────────────────
OLD5 = (
    "**Default credentials** (change these immediately after installation):\n"
    "- Email: `superadmin@rmm.local`\n"
    "- Password: `SuperAdmin@RMM1`"
)
NEW5 = (
    "**Credentials** are set via environment variables in `.env`:\n"
    "- Email: `SUPERADMIN_EMAIL` (default: `superadmin@rmm.local`)\n"
    "- Password: `SUPERADMIN_PASSWORD` -- **this is now required**. "
    "The API will refuse to start if `SUPERADMIN_PASSWORD` is not set in `.env`. "
    "There is no built-in default password."
)
assert OLD5 in content, "superadmin credentials section not found"
content = content.replace(OLD5, NEW5, 1)

# ── 6. Update superadmin .env editing section ────────────────────────────────
OLD6 = (
    "**Changing the superadmin email or password via environment variables:**\n"
    "\n"
    "Edit the `.env` file on the server and set:\n"
    "```\n"
    "SUPERADMIN_EMAIL=your-preferred-email@company.com\n"
    "SUPERADMIN_PASSWORD=YourNewStrongPassword123\n"
    "```\n"
    "Then restart the Flask API. The account will be updated on next startup."
)
NEW6 = (
    "**Changing the superadmin email or password via environment variables:**\n"
    "\n"
    "Edit the `.env` file on the server and set:\n"
    "```\n"
    "SUPERADMIN_EMAIL=your-preferred-email@company.com\n"
    "SUPERADMIN_PASSWORD=YourNewStrongPassword123\n"
    "```\n"
    "Then restart the Flask API. The account will be updated on next startup.\n"
    "\n"
    "> **IMPORTANT:** `SUPERADMIN_PASSWORD` must be set before starting the API. "
    "If it is missing or blank, the API will raise an error and refuse to start. "
    "Minimum length is 10 characters."
)
assert OLD6 in content, "superadmin env section not found"
content = content.replace(OLD6, NEW6, 1)

# ── 7. Add CSV export note to Devices chapter ────────────────────────────────
OLD7 = (
    "### Step-by-step: Investigating a Device After an Alert\n"
    "\n"
    "You have received an alert that ACME-SRV01 has high CPU."
)
NEW7 = (
    "### Exporting Devices to CSV\n"
    "\n"
    "A **Download CSV** button at the top of the Devices page exports all currently-filtered "
    "devices to a CSV file. The export includes: hostname, IP address, platform, online status, "
    "CPU%, RAM%, Disk%, and last seen timestamp. Filters (OS tab, search box) apply before export "
    "-- so you can export just Windows devices, or just devices matching a search term.\n"
    "\n"
    "### Step-by-step: Investigating a Device After an Alert\n"
    "\n"
    "You have received an alert that ACME-SRV01 has high CPU."
)
assert OLD7 in content, "device investigating section not found"
content = content.replace(OLD7, NEW7, 1)

# ── 8. Add two-step delete confirmation note ─────────────────────────────────
OLD8 = (
    "> **NOTE:** Agentless devices do not report CPU, RAM, or disk metrics. "
    "They are presence-monitored only -- the system confirms they are reachable on the network, nothing more."
)
NEW8 = (
    "> **NOTE:** Agentless devices do not report CPU, RAM, or disk metrics. "
    "They are presence-monitored only -- the system confirms they are reachable on the network, nothing more.\n"
    "\n"
    "### Delete Confirmation\n"
    "\n"
    "Deleting a device is a two-step process to prevent accidental removal. The first click on "
    "**Delete** changes the button to **Sure? Confirm / Cancel**. You must click **Confirm** "
    "within the same page load to proceed. Navigating away or clicking **Cancel** abandons the "
    "deletion. This applies to both agent-managed and agentless devices."
)
assert OLD8 in content, "agentless NOTE not found: " + repr(content[content.find("Agentless")-10:content.find("Agentless")+200])
content = content.replace(OLD8, NEW8, 1)

# ── 9. Add CSV export to Tickets chapter ─────────────────────────────────────
OLD9 = (
    "### Step-by-step: Updating a Ticket Status\n"
    "\n"
    "1. Find and expand the ticket."
)
NEW9 = (
    "### Exporting Tickets to CSV\n"
    "\n"
    "A **Download CSV** button at the top of the Tickets page exports all currently-filtered "
    "tickets to a CSV file with: ID, title, customer, priority, status, and created date. "
    "Apply filters first to narrow the export.\n"
    "\n"
    "### Step-by-step: Updating a Ticket Status\n"
    "\n"
    "1. Find and expand the ticket."
)
assert OLD9 in content, "ticket status update section not found"
content = content.replace(OLD9, NEW9, 1)

# ── 10. Add CSV export to Alerts chapter ─────────────────────────────────────
OLD10 = (
    "### Step-by-step: Acknowledging an Alert\n"
    "\n"
    "Acknowledging means"
)
NEW10 = (
    "### Exporting Alerts to CSV\n"
    "\n"
    "A **Download CSV** button at the top of the Active Alerts tab exports all currently-filtered "
    "alerts to a CSV file with: device, rule name, severity, status, and triggered date.\n"
    "\n"
    "### Step-by-step: Acknowledging an Alert\n"
    "\n"
    "Acknowledging means"
)
assert OLD10 in content, "alert acknowledge section not found"
content = content.replace(OLD10, NEW10, 1)

# ── 11. Add CSV export to Admin Audit Log section ────────────────────────────
OLD11 = (
    "**Filtering:** Use the Action type dropdown and date range pickers to narrow results.\n"
    "\n"
    "### Step-by-step: Investigating a Suspicious Action"
)
NEW11 = (
    "**Filtering:** Use the Action type dropdown and date range pickers to narrow results.\n"
    "\n"
    "**Export to CSV:** A **Download CSV** button exports the currently-filtered audit entries "
    "(timestamp, user, action, resource type, resource ID, IP address).\n"
    "\n"
    "### Step-by-step: Investigating a Suspicious Action"
)
assert OLD11 in content, "audit log filter section not found"
content = content.replace(OLD11, NEW11, 1)

# ── 12. Insert new Chapter 9a (MFA) before Chapter 10 ────────────────────────
OLD12 = "## Chapter 10: Your Role and What You Can Access"
NEW12 = """\
## Chapter 9a: Multi-Factor Authentication (MFA)

### What it is

Multi-Factor Authentication (MFA) adds a second verification step to the login process. After entering your email and password, you are asked for a 6-digit time-based code from an authenticator app on your phone (such as Google Authenticator, Authy, or Microsoft Authenticator). Even if someone knows your password, they cannot log in without the code.

### Who uses it

Any user can enable MFA on their own account. Administrators are strongly encouraged to enable it.

### Logging In with MFA Enabled

1. Enter your email and password on the login page and click **Sign In ->**.
2. A new screen appears: **"Two-Factor Authentication Required"**.
3. Open your authenticator app and find the RMM entry.
4. Enter the current 6-digit code shown in the app.
5. Click **Verify ->**.
6. You are taken to the RMM dashboard.

If you click **Back**, you return to the login screen. The 6-digit code refreshes every 30 seconds -- use the current code shown in the app.

> **NOTE:** If you lose access to your authenticator app, contact your system administrator. They can disable MFA on your account via the Admin Users panel.

### Setting Up MFA on Your Account

1. Log in to the RMM dashboard.
2. Click **My Profile** in the sidebar (under ACCOUNT at the bottom).
3. On the right side of the page, find the **Multi-Factor Authentication** section.
4. The badge shows **DISABLED** in red if MFA is not yet set up.
5. Click **Enable MFA**.
6. A QR code appears along with a text key.
7. Open your authenticator app on your phone:
   - Google Authenticator: tap the + icon, then Scan a QR code
   - Authy: tap Add Account, then Scan QR code
   - Microsoft Authenticator: tap +, then Other account, then Scan
8. Scan the QR code shown on screen.
9. The app will show a 6-digit code for "RMM System".
10. Enter that 6-digit code in the **Verify Code** field and click **Activate MFA**.
11. The badge changes to **ENABLED** in green. MFA is now active on your account.

> **TIP:** Also write down or copy the text key shown under the QR code and store it securely. This is your backup key if you ever need to add the account to a new phone.

### Disabling MFA on Your Account

1. Go to **My Profile** in the sidebar.
2. In the MFA section, the badge shows **ENABLED**.
3. Enter your current password in the confirmation field.
4. Click **Disable MFA**.
5. The badge changes to **DISABLED**. MFA is removed from your account.

> **WARNING:** Disabling MFA reduces your account security. Only do this if you are replacing your authenticator app or device -- set MFA up again immediately after.

### Administrator: Disabling MFA for a Locked-Out User

If a user loses their authenticator app and cannot log in:

1. Go to **Admin** -> **Users** tab.
2. Find the user.
3. Click **Edit**.
4. Uncheck **MFA Enabled** and save.
5. The user can now log in with just their password and then re-enroll MFA from My Profile.

---

## Chapter 9b: My Profile Page

### What it is

The My Profile page is a personal settings page accessible to every logged-in user from the sidebar. It allows you to view your account details, change your password, and manage MFA -- all without requiring admin assistance.

### Accessing My Profile

1. Look for **My Profile** in the sidebar under the **ACCOUNT** section at the bottom.
2. Click it -- the page loads with your account information.

### Left Column -- Account Details

- **Full Name** -- your display name
- **Email address** -- your login email
- **Role badge** -- your current role (VIEWER, TECHNICIAN, ADMIN, or SUPERADMIN)

**Changing your password:**

1. In the **Change Password** section on the left, enter your **Current Password**.
2. Enter your **New Password** (minimum 8 characters).
3. Confirm the new password.
4. Click **Update Password**.
5. A success message confirms the change. Your new password takes effect immediately.

### Right Column -- MFA Management

See **Chapter 9a** for full MFA setup and disable instructions. The right column shows the current MFA status badge and the appropriate action (enable or disable).

---

## Chapter 10: Your Role and What You Can Access"""
assert OLD12 in content, "Chapter 10 heading not found"
content = content.replace(OLD12, NEW12, 1)

# ── 13. Insert Docker chapter before PART II ─────────────────────────────────
OLD13 = "# PART II — GETTING STARTED"
NEW13 = """\
## Chapter 7a: Docker Deployment (Alternative Installation)

### What it is

Docker Compose is an alternative to the manual installation described in Chapters 2-6. It starts all six services (PostgreSQL, Redis, Flask API, Celery worker, Celery beat, and the Streamlit dashboard) with a single command. This is the recommended approach for production deployments and clean lab environments.

### What you need

- **Docker Desktop** installed on the server machine. Download from docker.com/products/docker-desktop. Ensure Docker Engine is running before proceeding.
- The RMM application files in a local directory (e.g. `C:\\RMM\\RemoteManagementSystem\\`).

> **NOTE:** Docker Desktop includes everything needed (Docker Engine and Docker Compose). No separate Redis, PostgreSQL, or Python installation is required -- Docker handles all of that inside containers.

### Step 1: Configure the API Environment File

The `.env` file is still required even with Docker. Create `api\\.env` as described in Chapter 4, but note that the database host in `DATABASE_URL` must be `db` (the Docker service name), not `localhost`:

```
SECRET_KEY=replace-with-a-long-random-string-at-least-32-chars
DATABASE_URL=postgresql://rmm_app:changeme@db:5432/rmmdb
JWT_SECRET_KEY=replace-with-another-long-random-string-at-least-32-chars
ORG_REGISTRATION_TOKEN=replace-with-a-unique-org-token
SUPERADMIN_PASSWORD=YourSuperAdminPassword123
SUPERADMIN_EMAIL=superadmin@rmm.local
CORS_ORIGINS=http://localhost:8501
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

> **IMPORTANT:** `DATABASE_URL` uses `@db:5432` not `@localhost:5432`. Inside Docker's network, the database container is reachable by the service name `db`.

### Step 2: Start All Services

Open a terminal in the project root directory (the folder containing `docker-compose.yml`):

```powershell
Set-Location C:\\RMM\\RemoteManagementSystem
docker-compose up -d
```

Docker will:
1. Pull the PostgreSQL 16 and Redis 7 images (first run only -- takes a few minutes).
2. Build the API and dashboard images from their Dockerfiles.
3. Start all six containers in the correct order.

Wait 15-20 seconds for PostgreSQL to initialize, then verify all containers are running:

```powershell
docker-compose ps
```

All six services should show status `Up`.

### Step 3: Verify

Open **http://localhost:8501** in a browser. The login page should appear.

Check the health endpoint:

```powershell
Invoke-WebRequest -Uri http://localhost:5000/api/health | Select-Object -ExpandProperty Content
```

Expected: `{"db": true, "redis": true, "status": "ok", "version": "1.0.0"}`

### Viewing Logs

```powershell
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# Celery worker
docker-compose logs -f celery_worker
```

### Stopping All Services

```powershell
docker-compose down
```

Data in PostgreSQL is preserved in a Docker volume (`postgres_data`). To also delete all data:

```powershell
docker-compose down -v
```

> **WARNING:** `docker-compose down -v` deletes the database volume permanently. All devices, tickets, users, and reports are lost. Only use this for a complete reset.

### Updating After Code Changes

```powershell
docker-compose build api dashboard
docker-compose up -d
```

### Docker vs Manual Installation -- Which to Use

| Situation | Recommended |
|---|---|
| Production server | Docker (Chapter 7a) |
| Clean lab / test environment | Docker (Chapter 7a) |
| Windows development with local debugging | Manual (Chapters 2-6) |
| Existing PostgreSQL/Redis you want to reuse | Manual (Chapters 2-6) |

---

# PART II -- GETTING STARTED"""
assert OLD13 in content, "PART II heading not found"
content = content.replace(OLD13, NEW13, 1)

# ── 14. Update Table of Contents ─────────────────────────────────────────────
OLD14 = (
    "**PART I — INSTALLATION AND SETUP**\n"
    "- Chapter 1: System Requirements\n"
    "- Chapter 2: Installing Prerequisites\n"
    "- Chapter 3: Setting Up the RMM Application\n"
    "- Chapter 4: First-Time Configuration\n"
    "- Chapter 5: Starting All Services\n"
    "- Chapter 6: Deploying the Agent on Managed Machines\n"
    "- Chapter 7: First-Time Setup Walkthrough\n"
    "\n"
    "**PART II — GETTING STARTED**\n"
    "- Chapter 8: What is the RMM System?\n"
    "- Chapter 9: Logging In and Navigation\n"
    "- Chapter 10: Your Role and What You Can Access"
)
NEW14 = (
    "**PART I -- INSTALLATION AND SETUP**\n"
    "- Chapter 1: System Requirements\n"
    "- Chapter 2: Installing Prerequisites\n"
    "- Chapter 3: Setting Up the RMM Application\n"
    "- Chapter 4: First-Time Configuration\n"
    "- Chapter 5: Starting All Services\n"
    "- Chapter 6: Deploying the Agent on Managed Machines\n"
    "- Chapter 7: First-Time Setup Walkthrough\n"
    "- Chapter 7a: Docker Deployment (Alternative Installation)\n"
    "\n"
    "**PART II -- GETTING STARTED**\n"
    "- Chapter 8: What is the RMM System?\n"
    "- Chapter 9: Logging In and Navigation\n"
    "- Chapter 9a: Multi-Factor Authentication (MFA)\n"
    "- Chapter 9b: My Profile Page\n"
    "- Chapter 10: Your Role and What You Can Access"
)
assert OLD14 in content, "TOC Part I/II not found"
content = content.replace(OLD14, NEW14, 1)

# ── 15. Update admin checklist ───────────────────────────────────────────────
OLD15 = (
    "**Monthly security checklist:**\n"
    "- [ ] Review Audit Log for unexpected DELETE events\n"
    "- [ ] Review Audit Log for unusual LOGIN IP addresses\n"
    "- [ ] Verify all Users are current employees\n"
    "- [ ] Check System Info -> Services card for health\n"
    "- [ ] Review Outstanding invoices in Billing\n"
    "- [ ] Check Compliance % in OS Patches"
)
NEW15 = (
    "**Monthly security checklist:**\n"
    "- [ ] Review Audit Log for unexpected DELETE events (use CSV export for records)\n"
    "- [ ] Review Audit Log for unusual LOGIN IP addresses\n"
    "- [ ] Verify all Users are current employees\n"
    "- [ ] Confirm all admin accounts have MFA enabled (My Profile -> MFA section)\n"
    "- [ ] Check System Info -> Services card for health\n"
    "- [ ] Review Outstanding invoices in Billing\n"
    "- [ ] Check Compliance % in OS Patches"
)
content = content.replace(OLD15, NEW15, 1)  # not assert -- em-dashes may vary

# ── 16. Add MFA to glossary ───────────────────────────────────────────────────
OLD16 = "| Memurai | Windows-native Redis-compatible server."
NEW16 = (
    "| MFA | Multi-Factor Authentication. A second login step using a time-based 6-digit code "
    "from an authenticator app. Enabled per user from the My Profile page. |\n"
    "| Memurai | Windows-native Redis-compatible server."
)
assert OLD16 in content, "Memurai glossary entry not found"
content = content.replace(OLD16, NEW16, 1)

# ── 17. Add Docker to glossary ────────────────────────────────────────────────
OLD17 = "| Defragmentation | Disk maintenance for HDDs"
NEW17 = (
    "| Docker | Container platform used for one-command production deployment. "
    "See Chapter 7a for setup instructions. |\n"
    "| Defragmentation | Disk maintenance for HDDs"
)
assert OLD17 in content, "Defragmentation glossary entry not found"
content = content.replace(OLD17, NEW17, 1)

# ── 18. Add MFA troubleshooting entry ────────────────────────────────────────
OLD18 = "### Problem: Cannot access Admin page"
NEW18 = (
    "### Problem: MFA code rejected -- \"Invalid or expired code\"\n"
    "\n"
    "**Cause:** The code was typed after it expired (codes refresh every 30 seconds), "
    "or the server clock and phone clock are out of sync.\n"
    "\n"
    "**Steps:**\n"
    "1. Wait for the code in your authenticator app to refresh (the circular timer resets to full).\n"
    "2. Enter the fresh code immediately.\n"
    "3. If still failing, check that your phone's time is set to automatic/network time. "
    "TOTP codes depend on both clocks being synchronized.\n"
    "4. If locked out permanently (lost phone), contact an administrator -- they can disable MFA "
    "on your account via Admin -> Users -> Edit.\n"
    "\n"
    "---\n"
    "\n"
    "### Problem: API refuses to start -- \"SUPERADMIN_PASSWORD not set\"\n"
    "\n"
    "**Cause:** The `SUPERADMIN_PASSWORD` environment variable is missing from `api\\.env` "
    "or is less than 10 characters. This is a hard requirement -- the API will not start without it.\n"
    "\n"
    "**Steps:**\n"
    "1. Open `api\\.env` in a text editor.\n"
    "2. Add or update the line: `SUPERADMIN_PASSWORD=YourStrongPassword123`\n"
    "3. The password must be at least 10 characters.\n"
    "4. Restart the API: `cd api ; python app.py`\n"
    "\n"
    "---\n"
    "\n"
    "### Problem: Cannot access Admin page"
)
assert OLD18 in content, "Admin access required troubleshoot not found"
content = content.replace(OLD18, NEW18, 1)

# ── 19. Add Docker troubleshooting entry ─────────────────────────────────────
OLD19 = "### Starting All Services — Quick Reference"
NEW19 = (
    "### Problem: Docker container 'api' exits immediately on startup\n"
    "\n"
    "**Cause:** Usually a missing or invalid `api\\.env` file, or `SUPERADMIN_PASSWORD` not set.\n"
    "\n"
    "**Steps:**\n"
    "1. Check logs: `docker-compose logs api`\n"
    "2. Look for a `RuntimeError` or `SUPERADMIN_PASSWORD` message in the output.\n"
    "3. Verify `api\\.env` exists and contains all required variables (Chapter 7a).\n"
    "4. Ensure `DATABASE_URL` uses `@db:5432` (Docker service name), not `@localhost:5432`.\n"
    "5. After editing `.env`: `docker-compose up -d api`\n"
    "\n"
    "---\n"
    "\n"
    "### Starting All Services -- Quick Reference"
)
assert OLD19 in content, "Starting All Services section not found"
content = content.replace(OLD19, NEW19, 1)

# ── Save ──────────────────────────────────────────────────────────────────────
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("SAVED. New size:", len(content), "chars (was", original_len, ")")
