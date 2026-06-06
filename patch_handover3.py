#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch HANDOVER_GUIDE.md - all fixes."""

PATH = r'C:\Users\rigwe\Desktop\RemoteManagementSystem\HANDOVER_GUIDE.md'

with open(PATH, encoding='utf-8') as f:
    content = f.read()

original_len = len(content)
changes = []

def patch(old, new, label):
    global content
    if old not in content:
        print(f"  MISS: {label}")
        return False
    content = content.replace(old, new, 1)
    changes.append(label)
    return True

# 1. env template -- add new vars before SMTP block
patch(
    "    SMTP_HOST=smtp.gmail.com\n"
    "    SMTP_PORT=587\n"
    "    SMTP_USER=\n"
    "    SMTP_PASSWORD=\n"
    "    SMTP_FROM=RMM System <noreply@yourcompany.com>\n"
    "    ```",
    "    SUPERADMIN_PASSWORD=YourSuperAdminPassword123\n"
    "    SUPERADMIN_EMAIL=superadmin@rmm.local\n"
    "    CORS_ORIGINS=http://localhost:8501\n"
    "    SMTP_HOST=smtp.gmail.com\n"
    "    SMTP_PORT=587\n"
    "    SMTP_USER=\n"
    "    SMTP_PASSWORD=\n"
    "    SMTP_FROM=RMM System <noreply@yourcompany.com>\n"
    "    ```",
    "env template"
)

# 2. Add SUPERADMIN_PASSWORD row to substitutions table
patch(
    "    | `replace-with-a-unique-org-token-for-agent-registration` "
    "| A unique token agents use to register (e.g., `rmm-prod-2026-companyname-abc123`) |\n"
    "\n"
    "> **IMPORTANT:** The `ORG_REGISTRATION_TOKEN`",
    "    | `replace-with-a-unique-org-token-for-agent-registration` "
    "| A unique token agents use to register (e.g., `rmm-prod-2026-companyname-abc123`) |\n"
    "    | `YourSuperAdminPassword123` | A strong password (min 10 chars) for the built-in superadmin account. "
    "**Required** \u2014 the API will refuse to start without this set. |\n"
    "\n"
    "> **IMPORTANT:** The `ORG_REGISTRATION_TOKEN`",
    "substitutions table"
)

# 3. Health check JSON response
patch(
    '`{"status": "ok", "database": "connected", "redis": "connected"}`\n'
    '3. If any service shows "disconnected", check that respective service is running.',
    '`{"status": "ok", "db": true, "redis": true, "version": "1.0.0"}`. '
    'A `"status": "degraded"` response means PostgreSQL or Redis is unreachable \u2014 '
    'the health endpoint now tests actual connectivity.\n'
    '3. If `db` or `redis` is `false`, check that the respective service is running.',
    "health check JSON"
)

# 4. Login step 7 -- add MFA note (exact Unicode arrow in source)
patch(
    "7. Correct credentials take you to the RMM Dashboard.\n"
    "8. \u201cInvalid credentials\u201d means wrong email or password. Check Caps Lock.\n"
    "\n"
    "> **NOTE:** Your session token is stored in browser memory only \u2014 it is not in the URL. "
    "If you share a page URL, the recipient must log in with their own credentials.",
    "7. If your account has **Multi-Factor Authentication (MFA)** enabled, you will see a "
    "second screen asking for a 6-digit code from your authenticator app. "
    "Enter the code and click **Verify \u2192**. See Chapter 9a for full MFA details.\n"
    "8. Correct credentials (and MFA code if required) take you to the RMM Dashboard.\n"
    "9. \u201cInvalid credentials\u201d means wrong email or password. Check Caps Lock.\n"
    "\n"
    "> **NOTE:** Your session is maintained in browser memory. "
    "If you share a page URL, the recipient must log in with their own credentials.",
    "login MFA note"
)

# 5. Superadmin default credentials
patch(
    "**Default credentials** (change these immediately after installation):\n"
    "- Email: `superadmin@rmm.local`\n"
    "- Password: `SuperAdmin@RMM1`",
    "**Credentials** are set via environment variables in `.env`:\n"
    "- Email: `SUPERADMIN_EMAIL` (default: `superadmin@rmm.local`)\n"
    "- Password: `SUPERADMIN_PASSWORD` \u2014 **this is now required**. "
    "The API will refuse to start if `SUPERADMIN_PASSWORD` is not set in `.env`. "
    "There is no built-in default password.",
    "superadmin credentials"
)

# 6. Superadmin env section -- add IMPORTANT note
patch(
    "Then restart the Flask API. The account will be updated on next startup.\n"
    "\n"
    "> **WARNING:** Keep the superadmin password",
    "Then restart the Flask API. The account will be updated on next startup.\n"
    "\n"
    "> **IMPORTANT:** `SUPERADMIN_PASSWORD` must be set before starting the API. "
    "If it is missing or blank, the API will raise a `RuntimeError` and refuse to start. "
    "Minimum length is 10 characters.\n"
    "\n"
    "> **WARNING:** Keep the superadmin password",
    "superadmin env note"
)

# 7. Devices CSV export
patch(
    "### Step-by-step: Investigating a Device After an Alert\n"
    "\n"
    "You have received an alert that ACME-SRV01 has high CPU.",
    "### Exporting Devices to CSV\n"
    "\n"
    "A **Download CSV** button at the top of the Devices page exports all currently-filtered "
    "devices to a CSV file. The export includes: hostname, IP address, platform, online status, "
    "CPU%, RAM%, Disk%, and last seen timestamp. The active OS tab and search box filter apply "
    "before export.\n"
    "\n"
    "### Step-by-step: Investigating a Device After an Alert\n"
    "\n"
    "You have received an alert that ACME-SRV01 has high CPU.",
    "devices CSV export"
)

# 8. Delete confirmation
patch(
    "> **NOTE:** Agentless devices do not report CPU, RAM, or disk metrics. "
    "They are presence-monitored only \u2014 the system confirms they are reachable on the network, nothing more.",
    "> **NOTE:** Agentless devices do not report CPU, RAM, or disk metrics. "
    "They are presence-monitored only \u2014 the system confirms they are reachable on the network, nothing more.\n"
    "\n"
    "### Delete Confirmation\n"
    "\n"
    "Deleting a device is a two-step process to prevent accidental removal. "
    "The first click on **Delete** changes the button to **Sure? Confirm / Cancel**. "
    "You must click **Confirm** within the same page load to proceed. "
    "Navigating away or clicking **Cancel** abandons the deletion. "
    "This applies to both agent-managed and agentless devices.",
    "device delete confirmation"
)

# 9. Tickets CSV export
patch(
    "### Step-by-step: Updating a Ticket Status\n"
    "\n"
    "1. Find and expand the ticket.",
    "### Exporting Tickets to CSV\n"
    "\n"
    "A **Download CSV** button at the top of the Tickets page exports all currently-filtered "
    "tickets to a CSV file with: ID, title, customer, priority, status, and created date.\n"
    "\n"
    "### Step-by-step: Updating a Ticket Status\n"
    "\n"
    "1. Find and expand the ticket.",
    "tickets CSV export"
)

# 10. Alerts CSV export
patch(
    "### Step-by-step: Acknowledging an Alert\n"
    "\n"
    "Acknowledging means \u201cI have seen this and I am dealing with it.\u201d",
    "### Exporting Alerts to CSV\n"
    "\n"
    "A **Download CSV** button at the top of the Active Alerts tab exports all currently-filtered "
    "alerts to a CSV file with: device, rule name, severity, status, and triggered date.\n"
    "\n"
    "### Step-by-step: Acknowledging an Alert\n"
    "\n"
    "Acknowledging means \u201cI have seen this and I am dealing with it.\u201d",
    "alerts CSV export"
)

# 11. Audit log CSV export
patch(
    "**Filtering:** Use the Action type dropdown and date range pickers to narrow results.\n"
    "\n"
    "### Step-by-step: Investigating a Suspicious Action",
    "**Filtering:** Use the Action type dropdown and date range pickers to narrow results.\n"
    "\n"
    "**Export to CSV:** A **Download CSV** button exports the currently-filtered audit log entries "
    "(timestamp, user, action, resource type, resource ID, IP address) to a CSV file.\n"
    "\n"
    "### Step-by-step: Investigating a Suspicious Action",
    "audit log CSV export"
)

# 12. Insert Chapter 9a + 9b before Chapter 10
patch(
    "## Chapter 10: Your Role and What You Can Access",
    """\
## Chapter 9a: Multi-Factor Authentication (MFA)

### What it is

Multi-Factor Authentication (MFA) adds a second verification step to the login process. After entering your email and password, you are asked for a 6-digit time-based code from an authenticator app on your phone (such as Google Authenticator, Authy, or Microsoft Authenticator). Even if someone knows your password, they cannot log in without the code.

### Who uses it

Any user can enable MFA on their own account. Administrators are strongly encouraged to enable it.

### Logging In with MFA Enabled

1. Enter your email and password on the login page and click **Sign In \u2192**.
2. A new screen appears: **Two-Factor Authentication Required**.
3. Open your authenticator app and find the RMM entry.
4. Enter the current 6-digit code shown in the app.
5. Click **Verify \u2192**.
6. You are taken to the RMM dashboard.

The 6-digit code refreshes every 30 seconds \u2014 use the current code shown in the app. If you click **Back**, you return to the login screen.

> **NOTE:** If you lose access to your authenticator app, contact your system administrator. They can disable MFA on your account via Admin \u2192 Users \u2192 Edit.

### Setting Up MFA on Your Account

1. Log in to the RMM dashboard.
2. Click **My Profile** in the sidebar (under ACCOUNT at the bottom).
3. On the right side of the page, find the **Multi-Factor Authentication** section.
4. The badge shows **DISABLED** in red if MFA is not yet set up.
5. Click **Enable MFA**.
6. A QR code appears along with a text backup key.
7. Open your authenticator app on your phone and scan the QR code.
8. The app will show a 6-digit code for "RMM System".
9. Enter that 6-digit code in the **Verify Code** field and click **Activate MFA**.
10. The badge changes to **ENABLED** in green. MFA is now active on your account.

> **TIP:** Copy the text key shown under the QR code and store it securely. This is your backup key if you need to add the account to a new phone.

### Disabling MFA on Your Account

1. Go to **My Profile** in the sidebar.
2. In the MFA section, the badge shows **ENABLED**.
3. Enter your current password in the confirmation field.
4. Click **Disable MFA**.
5. The badge changes to **DISABLED**.

> **WARNING:** Disabling MFA reduces your account security. Only do this if you are replacing your authenticator app or device \u2014 set MFA up again immediately after.

### Administrator: Disabling MFA for a Locked-Out User

If a user loses their authenticator app and cannot log in:

1. Go to **Admin** \u2192 **Users** tab.
2. Find the user and click **Edit**.
3. Uncheck **MFA Enabled** and save.
4. The user can now log in with just their password and re-enroll MFA from My Profile.

---

## Chapter 9b: My Profile Page

### What it is

The My Profile page is a personal settings page accessible to every logged-in user. It allows you to view your account details, change your password, and manage MFA \u2014 all without requiring admin assistance.

### Accessing My Profile

Look for **My Profile** in the sidebar under the **ACCOUNT** section at the bottom. Click it to open the page.

### Left Column \u2014 Account Details and Password

Shows your full name, email address, and role badge. Below that, the **Change Password** form lets you enter your current password and set a new one (minimum 8 characters). Click **Update Password** to save. The change takes effect immediately.

### Right Column \u2014 MFA Management

Shows the current MFA status badge (green ENABLED or red DISABLED) and the appropriate action form. See **Chapter 9a** for step-by-step MFA instructions.

---

## Chapter 10: Your Role and What You Can Access""",
    "Chapter 9a + 9b inserted"
)

# 13. Docker chapter before PART II
patch(
    "# PART II \u2014 GETTING STARTED",
    """\
## Chapter 7a: Docker Deployment (Alternative Installation)

### What it is

Docker Compose is an alternative to the manual installation in Chapters 2\u20136. It starts all six services (PostgreSQL, Redis, Flask API, Celery worker, Celery beat, and Streamlit dashboard) with a single command. This is the recommended method for production deployments.

### What you need

- **Docker Desktop** installed on the server. Download from docker.com/products/docker-desktop.
- The RMM project folder on the server (e.g. `C:\\RMM\\RemoteManagementSystem\\`).

> **NOTE:** Docker includes PostgreSQL, Redis, and Python inside containers. No separate installation of those is required.

### Step 1: Create the API Environment File

Create `api\\.env` as described in Chapter 4. When using Docker, the database host must be `db` (the service name), not `localhost`:

```
SECRET_KEY=replace-with-32-char-random-string
DATABASE_URL=postgresql://rmm_app:changeme@db:5432/rmmdb
JWT_SECRET_KEY=replace-with-another-32-char-string
ORG_REGISTRATION_TOKEN=replace-with-unique-token
SUPERADMIN_PASSWORD=YourSuperAdminPassword123
SUPERADMIN_EMAIL=superadmin@rmm.local
CORS_ORIGINS=http://localhost:8501
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

> **IMPORTANT:** Use `@db:5432` not `@localhost:5432` in `DATABASE_URL`.

### Step 2: Start All Services

```powershell
Set-Location C:\\RMM\\RemoteManagementSystem
docker-compose up -d
```

Wait 15\u201320 seconds, then verify all containers are running:

```powershell
docker-compose ps
```

All six services should show status `Up`.

### Step 3: Verify

Open **http://localhost:8501** \u2014 the login page should appear.

Health check: `http://localhost:5000/api/health` should return `{"db": true, "redis": true, "status": "ok", "version": "1.0.0"}`.

### Useful Commands

```powershell
# View logs
docker-compose logs -f api
docker-compose logs -f celery_worker

# Stop all services (data preserved)
docker-compose down

# Stop and delete all data (IRREVERSIBLE)
docker-compose down -v

# Rebuild after code changes
docker-compose build api dashboard
docker-compose up -d
```

> **WARNING:** `docker-compose down -v` permanently deletes the database. All devices, tickets, users, and reports are lost.

### Docker vs Manual Installation

| Situation | Recommended method |
|---|---|
| Production server | Docker (Chapter 7a) |
| Clean lab / demo | Docker (Chapter 7a) |
| Local dev with debugger | Manual (Chapters 2\u20136) |
| Reusing existing PostgreSQL/Redis | Manual (Chapters 2\u20136) |

---

# PART II \u2014 GETTING STARTED""",
    "Docker chapter"
)

# 14. Update Table of Contents
patch(
    "**PART I \u2014 INSTALLATION AND SETUP**\n"
    "- Chapter 1: System Requirements\n"
    "- Chapter 2: Installing Prerequisites\n"
    "- Chapter 3: Setting Up the RMM Application\n"
    "- Chapter 4: First-Time Configuration\n"
    "- Chapter 5: Starting All Services\n"
    "- Chapter 6: Deploying the Agent on Managed Machines\n"
    "- Chapter 7: First-Time Setup Walkthrough\n"
    "\n"
    "**PART II \u2014 GETTING STARTED**\n"
    "- Chapter 8: What is the RMM System?\n"
    "- Chapter 9: Logging In and Navigation\n"
    "- Chapter 10: Your Role and What You Can Access",
    "**PART I \u2014 INSTALLATION AND SETUP**\n"
    "- Chapter 1: System Requirements\n"
    "- Chapter 2: Installing Prerequisites\n"
    "- Chapter 3: Setting Up the RMM Application\n"
    "- Chapter 4: First-Time Configuration\n"
    "- Chapter 5: Starting All Services\n"
    "- Chapter 6: Deploying the Agent on Managed Machines\n"
    "- Chapter 7: First-Time Setup Walkthrough\n"
    "- Chapter 7a: Docker Deployment (Alternative Installation)\n"
    "\n"
    "**PART II \u2014 GETTING STARTED**\n"
    "- Chapter 8: What is the RMM System?\n"
    "- Chapter 9: Logging In and Navigation\n"
    "- Chapter 9a: Multi-Factor Authentication (MFA)\n"
    "- Chapter 9b: My Profile Page\n"
    "- Chapter 10: Your Role and What You Can Access",
    "TOC update"
)

# 15. Admin monthly checklist
patch(
    "- [ ] Review Audit Log for unexpected DELETE events\n"
    "- [ ] Review Audit Log for unusual LOGIN IP addresses\n"
    "- [ ] Verify all Users are current employees\n"
    "- [ ] Check System Info",
    "- [ ] Review Audit Log for unexpected DELETE events (use CSV export for records)\n"
    "- [ ] Review Audit Log for unusual LOGIN IP addresses\n"
    "- [ ] Verify all Users are current employees\n"
    "- [ ] Confirm all admin accounts have MFA enabled (My Profile \u2192 MFA section)\n"
    "- [ ] Check System Info",
    "admin checklist MFA"
)

# 16. MFA glossary
patch(
    "| Memurai | Windows-native Redis-compatible server.",
    "| MFA | Multi-Factor Authentication. A second login step requiring a 6-digit code "
    "from an authenticator app. Enabled per user from the My Profile page. |\n"
    "| Memurai | Windows-native Redis-compatible server.",
    "MFA glossary"
)

# 17. Docker glossary
patch(
    "| Defragmentation | Disk maintenance for HDDs",
    "| Docker | Container platform. Used for one-command deployment via `docker-compose up -d`. "
    "See Chapter 7a. |\n"
    "| Defragmentation | Disk maintenance for HDDs",
    "Docker glossary"
)

# 18. MFA troubleshooting
patch(
    '### Problem: Cannot access Admin page \u2014 "Admin access required"',
    '### Problem: MFA code rejected \u2014 "Invalid or expired code"\n'
    '\n'
    '**Cause:** Code entered after it expired, or phone and server clocks are out of sync.\n'
    '\n'
    '**Steps:**\n'
    '1. Wait for the code to refresh in your authenticator app (timer resets to full).\n'
    '2. Enter the fresh code immediately.\n'
    '3. If still failing, set your phone time to automatic/network time \u2014 TOTP requires synchronized clocks.\n'
    '4. If locked out permanently (lost phone), contact an administrator to disable MFA on your account.\n'
    '\n'
    '---\n'
    '\n'
    '### Problem: API refuses to start \u2014 RuntimeError about SUPERADMIN_PASSWORD\n'
    '\n'
    '**Cause:** `SUPERADMIN_PASSWORD` is missing from `api\\.env` or is less than 10 characters.\n'
    '\n'
    '**Steps:**\n'
    '1. Open `api\\.env` in a text editor.\n'
    '2. Add: `SUPERADMIN_PASSWORD=YourStrongPassword123` (min 10 characters).\n'
    '3. Restart the API.\n'
    '\n'
    '---\n'
    '\n'
    '### Problem: Cannot access Admin page \u2014 "Admin access required"',
    "MFA + superadmin troubleshooting"
)

# 19. Docker troubleshooting
patch(
    "### Starting All Services \u2014 Quick Reference",
    "### Problem: Docker container 'api' exits immediately\n"
    "\n"
    "**Cause:** Missing or invalid `api\\.env`, or `SUPERADMIN_PASSWORD` not set.\n"
    "\n"
    "**Steps:**\n"
    "1. Run `docker-compose logs api` and look for a `RuntimeError` message.\n"
    "2. Verify `api\\.env` exists with all required variables (see Chapter 7a).\n"
    "3. Ensure `DATABASE_URL` uses `@db:5432`, not `@localhost:5432`.\n"
    "4. After fixing `.env`, run `docker-compose up -d api` to restart the API container.\n"
    "\n"
    "---\n"
    "\n"
    "### Starting All Services \u2014 Quick Reference",
    "Docker troubleshooting"
)

# Save
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"SAVED. {len(changes)} changes applied. Size: {len(content)} chars (was {original_len})")
print("Changes:", changes)
