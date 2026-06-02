# RMM System — Complete Handover and User Guide

**Remote Monitoring and Management Platform**
Version 1.0 — NinjaOne-style, built in-house

---

**Prepared for:** All staff — new joiners, IT support, technicians, administrators, and developers
**System URL:** http://localhost:8501
**API URL:** http://localhost:5000
**Document version:** 1.0

---

## Foreword

This document is the definitive reference for everyone who uses, operates, or maintains the RMM system. It is written to serve several audiences at once: the junior staff member who has never used an RMM tool before, the experienced technician who needs a quick reference, the administrator who manages users and automation, and the developer who extends or maintains the codebase.

Read the section that applies to your role. If you are unsure which sections apply to you, consult the "How to Use This Book" chapter immediately following the Table of Contents.

This guide reflects the actual codebase as implemented. All step-by-step instructions refer to real UI elements, real field names, and real system behavior. Where a feature is queued for a future phase, this is noted explicitly so you are not confused when you cannot find it.

---

## Table of Contents

**How to Use This Book**

**PART I — GETTING STARTED (for everyone)**
- Chapter 1: What is the RMM System?
- Chapter 2: Logging In and Navigation
- Chapter 3: Your Role and What You Can Access

**PART II — DAILY OPERATIONS (beginner-friendly)**
- Chapter 4: The Dashboard — Your Command Center
- Chapter 5: Managing Tickets
- Chapter 6: Working with Customers
- Chapter 7: Devices — Monitoring Your Fleet
- Chapter 8: Alerts — Staying Ahead of Problems
- Chapter 9: App Center — Software Inventory
- Chapter 10: Network Discovery
- Chapter 11: Reports
- Chapter 12: Billing

**PART III — ADVANCED OPERATIONS (technicians and admins)**
- Chapter 13: Administration
- Chapter 14: Automation Profiles
- Chapter 15: OS Patch Management
- Chapter 16: Software Patches
- Chapter 17: Disk Management
- Chapter 18: Maintenance Actions
- Chapter 19: Scripts — Running and Writing

**PART IV — TECHNICAL REFERENCE (developers and admins)**
- Chapter 20: System Architecture Overview
- Chapter 21: Script Writing Guide
- Chapter 22: Alert Rules — Writing Effective Rules
- Chapter 23: Automation Profile Design
- Chapter 24: User Roles and Permissions Matrix
- Chapter 25: Common Troubleshooting

**Appendix A: Glossary**
**Appendix B: Quick Reference Cards**

---

## How to Use This Book

This book is structured for different readers. You do not need to read it cover to cover. Use the table below to find your relevant chapters.

| Your Role | Essential Reading | Also Useful |
|---|---|---|
| New/junior staff (first week) | Chapters 1, 2, 3, 4 | Chapter 5, 7 |
| IT Support staff | Chapters 1, 2, 3, 4, 5, 6, 7, 8 | Chapters 9, 11 |
| Technicians | Chapters 1–10, 14–19 | Chapters 20–22 |
| System Administrators | All of Parts I, II, III | Part IV |
| Developers | Parts I, IV | Parts II, III |

**Callout boxes** are used throughout this document:

> **NOTE:** Extra context or background information.

> **TIP:** A faster or smarter way to do something.

> **WARNING:** Something that can cause problems if done incorrectly.

> **IMPORTANT:** Information you must not skip.

---

# PART I — GETTING STARTED

---

## Chapter 1: What is the RMM System?

### What it is

RMM stands for Remote Monitoring and Management. An RMM system is a platform used by IT teams to monitor, manage, and support computers and servers — often for multiple clients — from a single central dashboard.

Think of it like a control tower for an airport. Every aircraft (your managed devices) sends constant status updates. The tower (the RMM) watches all of them, raises alarms when something is wrong, and allows controllers (your IT staff) to take action remotely.

This system is modeled after industry tools like NinjaOne and ConnectWise Automate but built specifically for your organization. It is composed of four main components:

**1. The Dashboard (Streamlit frontend)**
A web-based interface running at http://localhost:8501. This is what you see when you open the system in your browser. It provides all the pages: tickets, devices, alerts, reports, billing, scripts, and more.

**2. The API (Flask backend)**
Running at http://localhost:5000, this is the engine that powers the dashboard. It stores and retrieves all data, handles authentication, and processes commands. You will interact with it indirectly through the dashboard, though developers and advanced admins can also call it directly.

**3. The Agent (Python)**
A small program installed on each managed Windows machine. The agent runs continuously, sending a "heartbeat" to the API every 60 seconds. With each heartbeat it reports:
- CPU usage percentage
- RAM usage percentage
- Disk usage per drive
- Uptime in seconds
- Installed software (every 6 hours)

The agent also receives commands from the API — such as "run this script" or "reboot" — and executes them.

**4. The Database (PostgreSQL)**
All data — devices, tickets, alerts, customers, scripts, patches, billing — is stored in a PostgreSQL database called `rmmdb` running on localhost port 5432.

### Who uses it

| Role | What they primarily do |
|---|---|
| Viewers | Read-only access — can see dashboards and device status |
| Technicians | Manage devices, handle tickets, run scripts, manage patches |
| Administrators | Everything technicians do, plus manage users, billing, automation, system config |

### How it fits your workflow

When a client's machine has a problem — say the hard drive is nearly full — the following chain of events occurs automatically:

1. The agent on that machine reports disk usage of 92% in its heartbeat.
2. The API evaluates this against configured alert rules. If a rule exists for "disk > 90% → critical alert", an alert is created.
3. The alert appears on the Alerts page and the Dashboard.
4. Optionally, an email notification is sent to the configured address.
5. Optionally, a ticket is automatically created.
6. A technician sees the alert, investigates the device, and runs a cleanup script.
7. The ticket is updated and closed.

This entire process can happen without any manual intervention up to step 6 — that is the power of an RMM system.

---

## Chapter 2: Logging In and Navigation

### What it is

The login page is the entry point to the system. You need a valid email address and password to access any part of the platform.

### Who uses it

Everyone.

### Step-by-step: Logging In

1. Open your web browser (Chrome, Firefox, or Edge are recommended).
2. Go to: **http://localhost:8501**
3. You will see the RMM System login page. The page has a dark green background with a centered login card.
4. In the **Email address** field, type your full email address (e.g., `admin@company.com`).
5. In the **Password** field, type your password. The characters will be hidden as dots.
6. Click the green **Sign In →** button.
7. If your credentials are correct, you will be taken to the main RMM Dashboard.
8. If you see "Invalid credentials", check that your email has no typos and that your Caps Lock key is not on.

> **NOTE:** The system uses JWT tokens for authentication. After logging in, you will notice a `?tok=...` parameter in the URL. This token is how the system keeps you logged in as you navigate between pages. Do not share your URL with this token in it, as it contains your active session.

> **WARNING:** There is no "forgot password" button in the current version. If you are locked out, contact your system administrator to have your password reset directly in the database.

### Understanding the Interface Layout

After logging in, the screen is divided into two sections:

**The Sidebar (left panel)**
This is your navigation menu. It is always visible and contains links to every page, grouped by category:

- **MONITORING:** Overview (live charts), Devices, Alerts
- **MANAGEMENT:** Tickets, Customers, Automation
- **PATCHING:** OS Patches, Software Patches
- **TOOLS:** Scripts, Disk Management, Maintenance, Network Discovery
- **BUSINESS:** Reports, Billing, Admin

At the very top of the sidebar, you will see your name, email, and a colored role badge (ADMIN, TECHNICIAN, or VIEWER). At the bottom is the **Sign Out** button.

**The Main Content Area (right panel)**
This is where each page's content appears. Every page has a title at the top, optional filters or action buttons, and the main data display below.

### Step-by-step: Navigating Between Pages

1. Look at the sidebar on the left side of the screen.
2. Find the section heading (MONITORING, MANAGEMENT, etc.) for the page you want.
3. Click the page name. For example, click **Devices** under the MONITORING section.
4. The main content area on the right will load the Devices page.
5. Your current token is automatically included in the navigation link, so you remain logged in.

> **TIP:** Each page link in the sidebar appends `?tok=YOUR_TOKEN` to the URL. If you bookmark a page, the bookmark will include your token. Be aware that tokens expire over time. If you bookmark a page and cannot access it later, return to http://localhost:8501 and log in again.

### Step-by-step: Signing Out

1. Scroll to the bottom of the sidebar.
2. Click the **Sign Out** button.
3. You will be returned to the login screen. Your session token is cleared.

> **IMPORTANT:** Always sign out when you are done, especially on shared computers. Leaving an active session open on a shared machine is a security risk.

### Practical Example: First Login as a New Employee

You are Sarah, a new junior technician. It is your first day.

1. Your manager tells you your credentials: `sarah@company.com` / `Welcome123!`
2. You open Chrome and go to http://localhost:8501.
3. You type `sarah@company.com` in the email field.
4. You type `Welcome123!` in the password field.
5. You click **Sign In →**.
6. You see the RMM Dashboard with your name "Sarah" displayed at the top of the sidebar with a yellow TECHNICIAN badge.
7. You click **Devices** in the sidebar to see all managed machines.

---

## Chapter 3: Your Role and What You Can Access

### What it is

The RMM system uses Role-Based Access Control (RBAC). This means different users see different options and have different levels of permission depending on their assigned role. There are three roles: **admin**, **technician**, and **viewer**.

### Who uses it

Everyone should understand this chapter. Admins need it to manage other users. New staff need it to understand what they can and cannot do.

### The Three Roles Explained

**Viewer**
A viewer can see information but cannot make changes. Viewers can browse the dashboard, look at device metrics, read alerts, and view tickets. They cannot create tickets, run scripts, approve patches, or access the Admin page. This role is suitable for managers or clients who need read-only visibility.

**Technician**
A technician can do most day-to-day operational work. They can:
- Create and update tickets
- Acknowledge and resolve alerts
- View and manage devices
- Run scripts on devices
- Approve and manage patches
- Perform maintenance actions (reboot, shutdown, etc.)
- Manage customers
- Create and edit automation profiles

Technicians cannot access the Admin page, manage other users, or configure billing.

**Administrator**
An administrator has full access to everything, including:
- The Admin page (System Info, Audit Log, Users tab)
- User management (create, edit, deactivate users)
- Billing and invoice generation
- All technician capabilities

> **IMPORTANT:** The Admin page is hard-restricted to admin role only. If you navigate to Admin without the admin role, you will see an error message and the page will stop loading.

### How Roles Are Displayed

Your role is shown in the sidebar as a colored badge:
- **ADMIN** — red badge
- **TECHNICIAN** — yellow/amber badge
- **VIEWER** — green badge

### What Happens If You Try to Access Something Outside Your Role

If you are a viewer or technician and try to access the Admin page, you will see a red error message: "Admin access required. This page is restricted to admin users." The page will not load further.

For other restrictions (such as a viewer trying to create a ticket), the system enforces this at the API level — the action button may appear but the API will return a permission error.

### Practical Example: Understanding What You Can Do

Mark is a technician. On Monday morning, he notices a critical alert on the dashboard. He can:
- Click the alert to view its details — YES
- Click Acknowledge on the alert — YES
- Click Resolve on the alert — YES
- Go to Admin page to see the Audit Log — NO (admin only)
- Go to Billing to generate an invoice — YES (technicians can access billing pages; invoice creation may be admin-restricted depending on configuration)

---

# PART II — DAILY OPERATIONS

---

## Chapter 4: The Dashboard — Your Command Center

### What it is

The Dashboard is the first page you land on after logging in. It is your at-a-glance health check for the entire system. There are actually two dashboard views:

1. **The Home Page** (`app.py`) — shows the five key stat cards plus a navigation hint. This is what you see immediately after login.
2. **The Overview Page** (`01_Dashboard.py`) — a richer view with charts, device health map, recent alerts, and an activity feed. Access it by clicking **Overview** in the sidebar under MONITORING.

### Who uses it

Everyone. The dashboard is the starting point for all roles.

### The Five Stat Cards

Both the home page and the Overview page display five stat cards across the top of the screen. These are live numbers pulled from the API:

| Card | What it shows |
|---|---|
| Total Devices | Total number of devices registered in the system |
| Online | How many devices are currently online (sent a heartbeat in the last few minutes) |
| Warning / Critical | Devices in a degraded or critical state based on metrics |
| Open Alerts | Total number of unresolved alerts |
| Open Tickets | Total number of tickets that are not yet resolved or closed |

The numbers update each time you load or refresh the page. They do not auto-refresh — you must manually reload the page (press F5 or click your browser's refresh button) to see updated numbers.

> **TIP:** The colored accent under each card tells you the health status. Green means normal, amber means caution, red means action required.

### The Overview Page

Click **Overview** in the sidebar to go to the full dashboard view. It has four additional sections below the stat cards:

**Device Status Donut Chart (left panel)**
A circle chart that divides your device fleet into four categories: Healthy, Warning, Critical, and Offline. Hovering over a slice shows the exact count. The center of the circle displays the total device count.

**Device Health Map (right panel)**
A grid of mini device cards. Each card shows the device hostname, its online/offline status (green dot = online, grey dot = offline), and its CPU, RAM, and disk usage. This gives you a quick visual scan of your entire fleet.

**Recent Alerts (bottom left)**
A list of the most recent 10 open alerts. Each alert row shows the severity color bar (red for critical, amber for warning, blue for info), the alert message, and the timestamp.

**Activity Feed (bottom right)**
A real-time log of system actions — logins, ticket creations, device registrations, alert acknowledgements, and more. This is useful for understanding what has recently happened in the system.

### Step-by-step: Morning Health Check

This is the recommended routine to start your shift:

1. Log in at http://localhost:8501.
2. Look at the five stat cards. Note any red numbers in Critical or Open Alerts.
3. Click **Overview** in the sidebar.
4. Scan the Device Status donut chart. If the Critical slice is non-zero, you need to investigate.
5. Scan the Device Health Map. Look for any devices showing high CPU (>90%), high RAM, or high disk usage.
6. Read the Recent Alerts panel. Are there any critical alerts you haven't seen before?
7. Glance at the Activity Feed to see if any unexpected actions occurred overnight.
8. If everything looks healthy, proceed with your normal work. If something needs attention, navigate to the relevant page (Alerts, Devices, or Tickets) from the sidebar.

### Practical Example: Client Has a Server Down

ACME Corp calls you at 9am saying their server is unresponsive. Here is exactly what you do:

1. Open the Dashboard Overview.
2. Look at the Device Health Map for any device associated with ACME Corp that shows as offline (grey dot).
3. If you see an offline device, note its hostname.
4. Click **Devices** in the sidebar.
5. Search or scroll to find the ACME Corp server hostname.
6. Check the **Last Seen** time. If it was more than a few minutes ago, the device is truly offline — the agent has stopped sending heartbeats.
7. Check the **Alerts** page to see if an alert was generated for this device going offline.
8. Create a ticket (see Chapter 5) to document the issue.
9. Contact ACME Corp to let them know you are investigating.

### Tips and Gotchas

- The dashboard does not auto-refresh. Always press F5 before making decisions based on numbers you see.
- If the dashboard shows "No data yet. Start the agent to register devices." — this means no agents have connected to this instance yet. The API may be offline, or agents have not been deployed.
- If you see "API error: [message]" on the dashboard, the Flask API is likely not running. Contact your system administrator.

---

## Chapter 5: Managing Tickets

### What it is

The Tickets page is the helpdesk ticketing system. Every support request, incident, or task should have a corresponding ticket. Tickets allow you to track work, communicate with team members, and maintain a history of what was done for each client.

### Who uses it

IT support staff, technicians, and administrators. Viewers can see tickets but cannot create or update them.

### Ticket Fields

| Field | Description | Options |
|---|---|---|
| Title | Brief summary of the issue | Free text (required) |
| Description | Detailed explanation | Free text |
| Customer | Which client this relates to | Dropdown of registered customers (required) |
| Device | Which specific device (optional) | Not in the current create form — add via description |
| Priority | Urgency level | low, medium, high, critical |
| Status | Current state | open, in_progress, resolved, closed |
| Source | How was it created | manual, alert (auto-created), agent |

### Step-by-step: Creating a New Ticket

1. Click **Tickets** in the sidebar under MANAGEMENT.
2. At the top of the page, click the **+ New Ticket** expander. It will expand to show a form.
3. In the **Title** field, type a brief description. Example: "Server offline — ACME Corp"
4. In the **Priority** dropdown, select the appropriate urgency. Use **critical** for outages, **high** for significant problems, **medium** for non-urgent issues, **low** for requests.
5. In the **Description** text area, provide full details: what the issue is, when it started, what has been tried.
6. In the **Customer** dropdown, select the relevant customer. You must select a real customer — if the customer does not appear, they need to be created first (see Chapter 6).
7. Click **Create Ticket**.
8. If successful, you will see a green "Ticket created successfully!" message and the ticket will appear in the list below.

> **WARNING:** You must have at least one customer created before you can create a ticket. If the customer dropdown shows "— no customers —", go to the Customers page and add the customer first.

### Step-by-step: Finding a Ticket

1. Click **Tickets** in the sidebar.
2. Use the filter bar at the top of the ticket list to narrow results:
   - **Search field:** Type any word from the ticket title or description. Results filter as you type.
   - **Status dropdown:** Select "open", "in_progress", "resolved", or "closed" to show only tickets in that state. Select "All" to see everything.
   - **Priority dropdown:** Select a priority level to filter by urgency.
3. The ticket count caption below the filters shows how many tickets match your current filters.

### Step-by-step: Updating a Ticket Status

1. Find the ticket using the search/filter steps above.
2. Click the ticket title to expand it. You will see the full description, current status, customer name, and creation time.
3. On the left side of the expanded view, you will see a **Update Status** section with a dropdown.
4. Click the dropdown and select the new status:
   - **open** — just created, not yet being worked on
   - **in_progress** — someone is actively working on this
   - **resolved** — the issue has been fixed but is awaiting confirmation
   - **closed** — fully completed, no further action needed
5. Click the **Update Status** button.
6. You will see a green "Status updated." confirmation, and the badge on the ticket will change color.

### Step-by-step: Adding a Comment to a Ticket

1. Find and expand the ticket.
2. On the right side of the expanded view, you will see an **Add Comment** section.
3. Type your comment in the text area. Comments can be updates, notes about what was done, or requests for information.
4. If your comment is for internal team use only (clients should not see it), tick the **Internal note** checkbox. Internal notes are typically shown in a different style to distinguish them.
5. Click **Post Comment**.
6. You will see "Comment posted." confirmation.

> **TIP:** Use comments to keep a running log of everything you do on a ticket. Future team members reading the ticket should be able to understand the full history from comments alone.

### Ticket Status Colors

- **open** — red badge (needs attention)
- **in_progress** — amber badge (being worked on)
- **resolved** — green badge (fix applied)
- **closed** — grey badge (done)

### Priority Colors

- **critical** — red
- **high** — orange
- **medium** — amber
- **low** — grey/muted

### Practical Example: Client Calls With a Complaint

It is 2pm. TechCorp Ltd calls and says their accounting software is running very slowly. Here is exactly what you do:

1. Go to **Tickets** in the sidebar.
2. Click **+ New Ticket** to expand the creation form.
3. Title: "Accounting software slow performance — TechCorp Ltd"
4. Priority: **high** (the business is impacted but not completely down)
5. Description: "Client reports QuickBooks running extremely slowly since this morning. All 5 workstations affected. No recent changes reported. Need to investigate CPU/RAM on their server."
6. Customer: Select "TechCorp Ltd" from the dropdown.
7. Click **Create Ticket**. Note the ticket ID.
8. Go to **Devices** and find TechCorp Ltd's server. Check its CPU and RAM.
9. If you find the server is at 98% CPU, return to the ticket, expand it, and add a comment: "Checked server TECHCORP-SRV01 — CPU at 98%. Investigating running processes."
10. Update status to **in_progress**.
11. Resolve the issue, then add another comment explaining what was done.
12. Update status to **resolved** and contact the client to confirm.
13. After client confirmation, update to **closed**.

### Tips and Gotchas

- There is no email notification to clients when a ticket is created or updated yet (this is a planned feature). Follow up with clients manually.
- Tickets created automatically from alerts will have source = "alert". These show up in the same list.
- The search filter is case-insensitive and searches both title and description fields.

---

## Chapter 6: Working with Customers

### What it is

The Customers page manages the client organizations that own the devices you support. Every device belongs to a customer. Every ticket must be associated with a customer. Customer records hold contact information and support tier details.

### Who uses it

IT support staff, technicians, and administrators.

### Customer Fields

| Field | Description | Options |
|---|---|---|
| Name | Company or client name | Free text (required) |
| Email | Primary contact email | Email format |
| Phone | Contact phone number | Free text |
| Tier | Support level | standard, premium, enterprise |
| Primary Technician | Assigned team member | Selected from users |

### Step-by-step: Creating a New Customer

1. Click **Customers** in the sidebar under MANAGEMENT.
2. Find the **+ New Customer** or **Add Customer** button/expander at the top of the page.
3. Fill in the **Name** field — this is required and is how the customer will be identified throughout the system.
4. Fill in the **Email** field with the primary contact email.
5. Fill in the **Phone** field.
6. Select the appropriate **Tier**:
   - **standard** — basic support, standard response times
   - **premium** — priority support, faster response
   - **enterprise** — highest tier, dedicated support
7. Optionally assign a **Primary Technician** from the dropdown.
8. Click **Save** or **Create Customer**.
9. The customer will now appear in the list and be available in dropdowns throughout the system (Tickets, Devices, Billing).

### Step-by-step: Editing a Customer

1. On the Customers page, find the customer in the list. Customers are displayed as expandable cards.
2. Click the card or expander to open the customer details.
3. Edit the fields you need to change.
4. Click **Save** or **Update**.

### Step-by-step: Viewing Customer Details

1. On the Customers page, click any customer card to expand it.
2. You will see all the customer's details: contact info, tier, assigned technician.
3. From the customer detail view, you may also see links to their devices and recent tickets.

### Practical Example: Onboarding a New Client

You have just signed a new client: Greenway Manufacturing Ltd. Here is how to set them up:

1. Go to **Customers** in the sidebar.
2. Click **+ New Customer**.
3. Name: "Greenway Manufacturing Ltd"
4. Email: `it-contact@greenway.com`
5. Phone: `+1 555 234 5678`
6. Tier: **premium** (they have signed a premium support contract)
7. Primary Technician: Select yourself or the assigned technician from the dropdown.
8. Click **Save**.
9. Now go to the agent installation guide (Chapter 20) and deploy the agent on Greenway's machines.
10. Once agents are running, the devices will appear under Greenway Manufacturing Ltd in the Devices page.

### Tips and Gotchas

- Customer names must be unique. If you try to create a customer with a name that already exists, the API will return an error.
- Deleting a customer may fail if they have associated devices or tickets. You should archive or reassign those records first.
- The tier field affects billing calculations in the Billing page — make sure it is set correctly when onboarding.

---

## Chapter 7: Devices — Monitoring Your Fleet

### What it is

The Devices page shows every registered device — every computer, server, or workstation that has the RMM agent installed and has checked in with the system. This is the most information-dense page in the system.

### Who uses it

All roles. Technicians and administrators interact most frequently with this page.

### What You See on the Devices Page

The Devices page shows a list or table of all registered devices. For each device, you see:

| Column | Description |
|---|---|
| Hostname | The device's computer name (e.g., ACME-SRV01) |
| IP Address | The device's local IP address |
| OS | Operating system (e.g., Windows 10, Windows Server 2022) |
| Status | Online (green dot) or Offline (grey dot) |
| Last Seen | Timestamp of the last heartbeat received from the agent |
| CPU % | Current CPU usage percentage |
| RAM % | Current RAM usage percentage |
| Disk % | Disk usage of the primary drive |
| Customer | Which customer this device belongs to |

### Understanding Online vs Offline

A device is considered **online** if its agent has sent a heartbeat within the last few minutes. If no heartbeat has been received — because the machine is powered off, the agent crashed, or there is a network issue — the device is marked **offline**.

> **IMPORTANT:** An offline device is not necessarily broken. It could simply be powered off outside business hours, or be on a network that is currently unreachable. Always check the Last Seen timestamp to understand how long the device has been offline.

### Step-by-step: Viewing a Device's Detailed Metrics

1. Click **Devices** in the sidebar.
2. Find the device you want to inspect. Use any search or filter controls at the top if available.
3. Click the device's row or name to expand it or navigate to its detail page.
4. You will see expanded information including:
   - Full OS name and version
   - Platform (Windows, Linux, macOS)
   - CPU, RAM, and disk metrics with history
   - Last seen timestamp
   - Uptime
   - Agent registration date
5. Historical metric graphs may be shown if the device has been reporting for some time.

### Status Indicators

The green or grey dot next to each device is the most important visual indicator on this page:

- **Green dot with glow:** Device is online and reporting normally.
- **Grey dot:** Device is offline or the agent is not reporting.

On the Overview dashboard, devices are also categorized as:
- **Healthy:** Online with all metrics in normal range
- **Warning:** Online but with at least one metric in the warning range (75–90%)
- **Critical:** Online but with at least one metric in the critical range (>90%) — or has an active critical alert
- **Offline:** Agent not reporting

### Step-by-step: Investigating a Device After an Alert

You have received an alert that ACME-SRV01 has high CPU. Here is what to do:

1. Go to **Devices** in the sidebar.
2. Find ACME-SRV01 in the list.
3. Check the CPU column — if it is still high, the issue is ongoing.
4. Click the device to expand details.
5. Look at the CPU history graph if available. Is it a spike or sustained high load?
6. Note the Last Seen timestamp — is the device still reporting (online)?
7. If the device is online and CPU is high, consider:
   - Going to **Scripts** and running a "Get Running Processes" script
   - Going to **Maintenance** and scheduling a reboot if appropriate (after checking with the customer)
8. Create or update a ticket with your findings.

### Practical Example: New Employee Finding Their Assigned Devices

James is a new technician assigned to three small business clients. On his first day, he wants to see all their devices.

1. James goes to **Customers** in the sidebar.
2. He sees his three clients listed: SmithLaw Ltd, QuickPrint Co, and Beta Retail.
3. He goes to **Devices** in the sidebar.
4. He looks for any device with "SmithLaw", "QuickPrint", or "Beta" in the customer column.
5. He notes which ones are online, their current health, and any with high metrics.
6. He goes back to the **Dashboard Overview** and looks at the Device Health Map to get a visual summary.

> **TIP:** If a device has not been seen for several hours during business hours, proactively contact the customer to verify the machine is powered on and network is working. Do not wait for the customer to call you.

### Tips and Gotchas

- Last Seen time is shown in your local timezone. If your system time is wrong, the timestamps may appear incorrect.
- A device showing very high disk usage (>90%) will generate a critical alert automatically if an alert rule is configured. Check Chapter 8 for how to set up these rules.
- Devices only appear in the list once the agent has registered. A freshly deployed agent machine will appear after its first heartbeat.

---

## Chapter 8: Alerts — Staying Ahead of Problems

### What it is

The Alerts page is where you manage all active system notifications. An alert is generated when a device's metrics cross a threshold you have defined — for example, CPU usage above 90% for 5 minutes, or a disk at 95% capacity. Alerts are your early warning system.

The page has two tabs: **Active Alerts** and **Alert Rules**.

### Who uses it

All roles can view alerts. Technicians and administrators can acknowledge, resolve, and create alert rules.

### The Active Alerts Tab

**Four stat cards at the top:**
- **Open Alerts:** Total number of unresolved alerts
- **Critical:** How many are critical severity
- **Acknowledged:** How many have been acknowledged (seen but not yet resolved)
- **Warning:** How many are warning severity

**The severity filter dropdown** lets you show only critical, warning, or info alerts. Select "All" to see everything.

**The alert list** shows each alert as an expandable row. The title shows the first 90 characters of the alert message. When expanded, you see:

- A colored severity bar on the left (red = critical, amber = warning, blue = info)
- A severity badge and status badge
- Which device triggered it
- The timestamp
- The full alert message
- Two action buttons: **Acknowledge** and **Resolve**

### Alert Severity Levels

| Severity | Color | Meaning |
|---|---|---|
| critical | Red | Immediate action required — service may be impacted |
| warning | Amber | Attention needed soon — degraded performance |
| info | Blue | Informational — no immediate action needed |

### Alert Status

| Status | Meaning |
|---|---|
| open | New alert, not yet seen by anyone |
| acknowledged | A technician has seen it and is aware |
| resolved | The underlying issue has been fixed |

### Step-by-step: Acknowledging an Alert

Acknowledging an alert means "I have seen this and I am dealing with it." It does not mean the problem is fixed — it just stops the alert from appearing as new/unseen.

1. Click **Alerts** in the sidebar.
2. Find the alert in the list. Critical alerts appear first.
3. Click the alert to expand it.
4. Click the **Acknowledge** button.
5. You will see "Alert acknowledged." confirmation. The alert status badge will change from OPEN to ACKNOWLEDGED.

### Step-by-step: Resolving an Alert

Resolving means the problem has been fixed. You should only resolve an alert after you have actually addressed the underlying issue.

1. Find and expand the alert.
2. Verify the problem is actually fixed (check the device metrics on the Devices page).
3. Click the **Resolve** button.
4. You will see "Alert resolved." The alert will be removed from the Active Alerts list.

### The Alert Rules Tab

Alert rules define when alerts are created. Without rules, no alerts will ever be generated regardless of how bad device metrics become.

**Existing rules** are shown as expandable cards. Each shows:
- Rule name
- Metric being monitored (cpu, ram, disk, battery, offline)
- Condition (operator + threshold, e.g., `gt 90` means "greater than 90%")
- Cooldown period (how many minutes must pass before the same rule fires again)
- Severity level
- Active/Inactive status

Each rule has a **Deactivate/Activate** toggle and a **Delete** button.

### Step-by-step: Creating an Alert Rule

1. Click **Alerts** in the sidebar.
2. Click the **Alert Rules** tab.
3. Scroll down to the **Create Alert Rule** section.
4. Fill in the form:
   - **Rule Name:** Give it a clear name. Example: "High CPU Warning"
   - **Severity:** Choose critical, warning, or info based on how urgent this condition is.
   - **Metric:** What to monitor — cpu, ram, disk, battery, or offline (device goes offline).
   - **Operator:** The comparison. `gt` = greater than, `gte` = greater than or equal to, `lt` = less than, `lte` = less than or equal to.
   - **Threshold (%):** The value to compare against. For "CPU over 90%", set operator=`gt` and threshold=`90`.
   - **Cooldown (min):** How long before this rule can fire again for the same device. Set to 15 minutes to avoid being flooded with repeated alerts.
   - **Auto-create ticket:** Check this if you want a ticket to be automatically created every time this rule fires.
5. Click **Create Rule**.
6. The rule will appear in the rules list and will start evaluating on the next heartbeat from agents.

### Practical Example: Alert Fires at 2am

It is 2am. The on-call technician, Alex, receives an email notification: "CRITICAL: Disk usage on CORP-SRV02 is at 97%."

Here is exactly what Alex does:

1. Alex opens the system on their phone or laptop: http://localhost:8501
2. Alex logs in with their credentials.
3. Alex goes to **Alerts** in the sidebar.
4. Alex sees a red critical alert: "Disk usage on CORP-SRV02 is at 97.3% — Disk C:"
5. Alex clicks the alert to expand it. The alert shows it was triggered 4 minutes ago.
6. Alex clicks **Acknowledge** to mark it as seen.
7. Alex navigates to **Devices** and finds CORP-SRV02.
8. Alex clicks the device to see full disk details. Drive C: is at 97.3% — only 8GB free on a 500GB drive.
9. Alex goes to **Maintenance** and selects CORP-SRV02.
10. Alex confirms the action checkbox and clicks **Delete Temp Files**.
11. Alex checks back in 5 minutes. The disk is now at 94% — some space freed but still critical.
12. Alex creates a ticket: "CORP-SRV02 critical disk usage — need full cleanup" with priority Critical.
13. Alex goes to **Scripts** and runs a "Get Largest Files" script on CORP-SRV02 to identify what is consuming space.
14. Alex adds a comment to the ticket with the script output.
15. Alex resolves the alert (the immediate crisis is managed).
16. In the morning, a senior technician completes a full cleanup and closes the ticket.

### Step-by-step: Creating an Alert Rule for Disk Space

Here is the recommended disk space alert rule to set up for every environment:

1. Go to **Alerts** → **Alert Rules** tab.
2. Click the Create Alert Rule form.
3. Rule Name: "Critical Disk Usage"
4. Severity: `critical`
5. Metric: `disk`
6. Operator: `gt`
7. Threshold: `90`
8. Cooldown: `60` (1 hour — avoid constant re-alerting once disk is full)
9. Auto-create ticket: Checked (always create a ticket for disk issues)
10. Click **Create Rule**.

Repeat for a warning rule at 75%:
1. Rule Name: "Warning Disk Usage"
2. Severity: `warning`
3. Metric: `disk`
4. Operator: `gt`
5. Threshold: `75`
6. Cooldown: `120`
7. Auto-create ticket: Unchecked (warning only — no ticket yet)

### Tips and Gotchas

- If you get flooded with repeated alerts for the same device, check the cooldown setting. A cooldown of 5 minutes means a rule can fire 12 times per hour for a single device.
- The "offline" metric is special — it triggers when a device stops sending heartbeats. Use this to detect machines that have gone down unexpectedly.
- Resolving an alert does not fix the underlying problem. Always investigate and address the root cause before resolving.
- Alerts that are auto-created by alert rules will reference the rule name and metric in their message.

---

## Chapter 9: App Center — Software Inventory

### What it is

The App Center (Software Inventory) page shows you all the software installed on a selected device. This is useful for auditing what is running on client machines, identifying unauthorized software, checking software versions, and preparing for software patch management.

### Who uses it

IT support staff and technicians primarily. Also useful for administrators conducting software audits.

### What You See

The App Center page has a device selector at the top. Once you select a device:

- A summary shows how many software packages are installed on that device
- A searchable, filterable table lists every installed application with:
  - Software name
  - Version number
  - Publisher

A **Check for Updates** button is visible. In the current version, clicking it shows an informational message (full update functionality is part of Phase 6 and Software Patches).

### Step-by-step: Viewing Installed Software on a Device

1. Click **App Center** in the sidebar (you may need to scroll down to find it under one of the navigation groups — it may be listed as "App Center" or accessible via a sidebar link).
2. Use the device selector dropdown to choose the device you want to inspect.
3. The page will load a table of all software installed on that device.
4. Use the **Search** field to filter by application name, version, or publisher.
5. The total installed count is shown above the table.

> **NOTE:** Software inventory is collected by the agent every 6 hours (configurable via `software_interval` in the agent's `config.ini`). The data you see reflects the last software scan, not necessarily the current state. If software was installed in the last 6 hours, it may not appear yet.

### Step-by-step: Checking for a Specific Application

1. Open App Center and select the device.
2. In the search field, type the application name (e.g., "Adobe", "Chrome", "Java").
3. The table will filter in real-time to show only matching entries.
4. Check the version number to verify it matches the expected version.

### Practical Example: Software Audit for Compliance

Your manager asks you to confirm that all devices for DataSafe Ltd have Adobe Acrobat version 2024 or later.

1. Go to **Customers** and note all devices associated with DataSafe Ltd.
2. Go to **App Center**.
3. For each device:
   a. Select the device from the dropdown.
   b. Search for "Adobe Acrobat".
   c. Note the version.
4. Create a spreadsheet or ticket with your findings.
5. For any devices not meeting the requirement, create a ticket or note for the technician to update that device.

### Tips and Gotchas

- The software list can be very long on a busy Windows machine (100+ applications). Use the search filter to find what you need quickly.
- Version numbers are reported exactly as the agent finds them in the Windows registry. Some may appear as "1.0.0.0" or with build numbers — this is normal.
- If a device shows no software installed, it may be that the agent's software scan has not run yet (it runs every 6 hours after startup).

---

## Chapter 10: Network Discovery

### What it is

Network Discovery scans the local network and reports all hosts it can find — computers, servers, network devices, printers. This is useful for discovering unregistered devices, auditing network exposure, or identifying what is connected to a client's network.

### Who uses it

Technicians and administrators.

### What the Scan Returns

After running a network scan, the results table shows:

| Column | Description |
|---|---|
| IP Address | The IP of the discovered host |
| Hostname | DNS name if resolvable, otherwise blank |
| MAC Address | Hardware MAC address if available |
| Open Ports | List of detected open ports |
| Status | Whether the host responded to probes |

### Step-by-step: Running a Network Scan

1. Click **Network Discovery** in the sidebar (under TOOLS).
2. Click the **Run Scan** button.
3. Wait for the scan to complete. Depending on the network size, this can take between 30 seconds and a few minutes.
4. The results table will populate with all discovered hosts.
5. The results are saved in your session — they will persist while you are on this page and will not disappear if you scroll. However, navigating away and returning will require running a new scan.

> **NOTE:** Network Discovery scans the local network segment that the RMM server is on. It does not scan remote client networks unless a scan agent is deployed on-site at those networks.

> **WARNING:** Running a network scan on a network that monitors for intrusion detection may trigger alerts. Check with the client before running scans on sensitive networks.

### Practical Example: Discovering Unauthorized Devices

A client suspects someone has connected an unauthorized device to their office network. You run Network Discovery and compare the results against the list of known devices registered in the RMM system. Any IP addresses or MAC addresses not matching a known device warrant investigation.

### Tips and Gotchas

- Results are session-persisted, meaning they will remain on screen during your session but will not be saved to the database. Take a screenshot or note key findings if you need to refer to them later.
- Some devices on the network may not respond to scan probes (e.g., if their firewalls block ICMP). These will not appear in results.
- Running scans during business hours on a large network can generate noticeable network traffic. Prefer to run during off-hours for large environments.

---

## Chapter 11: Reports

### What it is

The Reports page lets you generate formal reports about your managed environment. Reports are useful for client meetings, monthly reviews, compliance audits, and billing. Reports can be generated as PDF or Excel files.

### Who uses it

Administrators and senior technicians.

### Report Templates Available

| Template | What it covers |
|---|---|
| device_summary | All devices, their status, OS versions, last seen times |
| patch_summary | Patch compliance, pending patches, deployed patches |
| alert_summary | All alerts in the date range, by severity and device |
| billing_summary | Billing totals, invoices generated, amounts due |

### Step-by-step: Generating a Report

1. Click **Reports** in the sidebar (under BUSINESS).
2. Click the **Generate** tab.
3. Select a **Template** from the dropdown.
4. Select the **Customer** you want to report on. If reporting on all customers, there may be an "All" option.
5. Set the **Date Range** using the Start Date and End Date fields.
6. Click the **Generate** button.
7. The report will be created and should prompt a download or display a download link. Depending on the template, the output will be a PDF or Excel file.

### Step-by-step: Viewing Report History

1. Click **Reports** in the sidebar.
2. Click the **History** tab.
3. You will see a list of previously generated reports. Each entry shows:
   - Report type
   - Customer
   - Date range
   - Generated timestamp
   - A **Download** button to re-download the file.

### Practical Example: Monthly Client Report

At the end of each month, you send each client a summary of their device health and any incidents. Here is the process:

1. Go to **Reports** → **Generate** tab.
2. Template: `device_summary`
3. Customer: Select "ACME Corp"
4. Date range: First to last day of the previous month
5. Click **Generate**. Download the PDF.
6. Repeat for `alert_summary` and `patch_summary`.
7. Email the three reports to the client contact.

### Tips and Gotchas

- If no data exists for the selected date range, the report may be empty or show "No data". Verify that devices were active and reporting during that period.
- Large date ranges with many devices can take a few seconds to generate. Be patient.
- Reports are stored in the system's report history and can be re-downloaded at any time.

---

## Chapter 12: Billing

### What it is

The Billing page allows administrators to generate invoices for clients based on the number of devices managed during a billing period. It also tracks invoice status: draft, sent, or paid.

### Who uses it

Administrators. Technicians may view billing but typically do not create invoices.

### Billing Fields

| Field | Description |
|---|---|
| Customer | The client being billed |
| Period Start | Start date of the billing period |
| Period End | End date of the billing period |
| Device Count | Number of managed devices in that period |
| Per-Device Rate | Monthly rate per device (in your currency) |

### Step-by-step: Generating an Invoice

1. Click **Billing** in the sidebar (under BUSINESS).
2. Find the invoice creation form. It may be at the top of the page or in a tab.
3. Select the **Customer** from the dropdown.
4. Set the **Period Start** and **Period End** dates.
5. Enter the **Device Count** (how many devices were managed during this period).
6. Enter the **Per-Device Rate** (e.g., 25.00 for $25 per device per month).
7. Click **Generate Invoice** or **Create**.
8. The invoice will appear in the list with status "draft".

### Invoice Status

| Status | Meaning |
|---|---|
| draft | Created but not yet sent to the client |
| sent | Emailed or delivered to the client |
| paid | Client has paid |

### Step-by-step: Updating Invoice Status

1. Go to **Billing** in the sidebar.
2. Find the invoice in the list.
3. Click or expand the invoice.
4. Update the status field (e.g., change from "draft" to "sent" after you email the invoice).
5. Save the change.

### Billing Summary Metrics

At the top of the Billing page you will see summary cards showing:
- **Total Invoiced:** Sum of all invoice amounts regardless of status
- **Paid:** Sum of invoices with "paid" status
- **Outstanding:** Total invoiced minus paid (what clients still owe)

### Practical Example: End-of-Month Billing Run

1. At the end of every month, go to **Billing**.
2. Check the Device count for each customer (you can verify this on the Devices page by filtering by customer).
3. Create an invoice for each customer using their contracted per-device rate.
4. Export or note the invoice amounts.
5. Email the invoices to each client.
6. Mark each invoice as "sent".
7. When payment is received, mark the invoice as "paid".
8. The Outstanding metric will decrease automatically.

### Tips and Gotchas

- Device count is entered manually. Always verify the actual number of managed devices before creating an invoice to avoid billing errors.
- There is no automated payment processing in the current version. Marking invoices as "paid" is a manual step.
- The per-device rate is per invoice and can differ between invoices for the same customer. This allows for promo rates, trial periods, etc.

---

# PART III — ADVANCED OPERATIONS

---

## Chapter 13: Administration

### What it is

The Admin page is restricted to admin role users only. It provides three tabs: System Info, Audit Log, and Users. This is where you check system health, review all user actions, and manage user accounts.

### Who uses it

Administrators only. Attempting to access this page as a technician or viewer shows an error.

### Tab 1: System Info

The System Info tab shows three cards:

**Current User card:**
Displays your full name, email, and role badge. This is your active session information.

**System card:**
Shows the configured API URL (`http://localhost:5000`), dashboard URL (`http://localhost:8501`), and database connection string (`localhost:5432 / rmmdb`).

**Services card:**
Live probe of service status:
- **Flask API** — probes the `/api/health` endpoint. Shows green "Online" or red "Unreachable".
- **Streamlit Dashboard** — always shows as Running (since you are using it).
- **PostgreSQL** — shows configured connection address.
- **Redis / Celery** — shows configured connection address.

> **NOTE:** PostgreSQL and Redis status dots show amber with the address rather than a live probe. This is the configured address, not necessarily a live connection test. If you need to verify database connectivity, check the Flask API logs.

### Tab 2: Audit Log

The Audit Log records every state-changing action in the system. This includes:

| Action Type | Color | Examples |
|---|---|---|
| CREATE | Green | Ticket created, device registered, user created |
| UPDATE | Blue | Ticket status changed, device updated |
| DELETE | Red | Rule deleted, device removed |
| LOGIN | Purple | User logged in |
| LOGOUT | Amber | User logged out |

The audit log shows:
- Action type (color-coded badge)
- Resource type and ID (e.g., "ticket:abc123")
- Timestamp
- IP address of the user who performed the action
- Email of the user

**Filtering the Audit Log:**
- Use the **Action type** dropdown to show only CREATE, UPDATE, DELETE, LOGIN, or LOGOUT events.
- Use the **From date** and **To date** date pickers to narrow to a specific date range.

### Step-by-step: Investigating a Suspicious Action

1. Go to **Admin** in the sidebar.
2. Click the **Audit Log** tab.
3. Set the **Action type** filter to "DELETE".
4. Set a date range if you know approximately when the action occurred.
5. Look for any DELETE events you did not expect — e.g., a device or rule being deleted.
6. Note the "User" column to identify who performed the action.
7. Note the IP address to verify it was from an expected location.

### Tab 3: Users

The Users tab shows a table of all registered users in the system. Columns:
- Full Name
- Email
- Role (color-coded: green for admin, blue for manager/technician, grey for others)
- Created Date

**User management actions** (creating, editing, deactivating users) are available through the API endpoint `/api/admin/users`. The UI table in the current version is read-only. To create or modify users, use the API directly or a database admin tool.

> **NOTE:** If you see "No user management API yet" message in the Users tab, the `/api/admin/users` endpoint has not been implemented in your current deployment. Check the API routes to verify endpoint availability.

### Step-by-step: Deactivating a Departed Employee

When a team member leaves, their account must be deactivated promptly to prevent unauthorized access.

1. Go to **Admin** → **Users** tab.
2. Find the departing employee in the user table.
3. Note their email address.
4. Currently, deactivation requires a direct API call or database update. Contact your developer or database administrator with the user's email and request deactivation.
5. After deactivation, verify by checking the Audit Log for any LOGIN events from that email after the deactivation date.

> **WARNING:** JWT tokens have an expiry time. Even after deactivating an account, if the user has a valid token they may still have access until that token expires. Force-expire tokens by rotating the JWT secret key if immediate lockout is required.

### Practical Example: Monthly Admin Review

On the first Monday of each month, the administrator performs a security review:

1. Go to **Admin** → **Audit Log**.
2. Filter by the previous month's date range.
3. Look for:
   - Unexpected DELETE actions
   - LOGIN attempts from unusual IP addresses
   - A large number of failed actions (may indicate someone testing permissions)
4. Go to the **Users** tab. Verify that all listed users are current employees.
5. Check **System Info** → Services card. Ensure all services show as healthy.

### Tips and Gotchas

- The Audit Log is your accountability trail. Every admin action is logged with IP and user. Do not attempt to hide actions — they are always recorded.
- If the Services card shows Flask API as "Unreachable", check if `python app.py` is running in the `api/` directory. See Chapter 25 for troubleshooting.
- The Users tab is read-only in the current UI version. User creation and role changes must be done via the API or directly in the database.

---

## Chapter 14: Automation Profiles

### What it is

Automation Profiles let you define a bundle of maintenance tasks that run automatically on a schedule — daily, weekly, monthly, or on demand. Each profile combines OS patching, software patching, disk maintenance, and cleanup tasks into a single workflow that can be run across many devices with no manual intervention.

### Who uses it

Administrators and senior technicians.

### Understanding the Profile Structure

An automation profile has:

- **Name and status:** The profile's identifier and whether it is active or inactive.
- **Schedule:** When to run — daily, weekly, monthly, or once. Plus a specific day of week and time.
- **Notification emails:** Comma-separated list of email addresses to notify after the profile runs.
- **Run on newly installed agents:** Whether new devices automatically get this profile.
- **Four task columns:** Each column configures a category of tasks:

| Column | Tasks Covered |
|---|---|
| OS Patch Management | Which Windows update categories to install |
| Software Patch Management | Which software packages to update, which to exclude |
| Disk Management | Defragment, Check Disk |
| Maintenance | Restore Point, Temp Files, Browser History, Reboot, Shutdown |

There is also a **Scripts** section where you can attach custom scripts to run as part of the profile.

### The Profile List Tab

The Profile List tab shows all existing profiles as cards. Each card displays:
- A green or grey status dot (active/inactive)
- Profile name
- Active/Inactive badge
- Schedule type (Daily, Weekly, etc.)
- Last run timestamp
- A **Run Now** button

Clicking **Run Now** immediately queues the profile's tasks on all assigned devices.

### Step-by-step: Creating an Automation Profile

1. Click **Automation** in the sidebar (under MANAGEMENT).
2. Click the **Create / Edit Profile** tab.
3. In the "Select profile to edit" dropdown, leave it on **— New Profile —**.
4. Enter a **Profile Name**. Example: "Weekly Maintenance — Standard Clients"
5. Check the **Active** checkbox to enable the profile.
6. Optionally check **Run on newly installed agents** if new devices should automatically use this profile.

**Schedule setup:**
7. Set **Run profile** to `weekly`.
8. Set **Day** to `sunday` (off-hours for minimal disruption).
9. Set **Time** to `02:00` AM.
10. In **Send email to**, enter the notification email address(es), comma-separated.

**Task configuration:**
11. Under **OS PATCH MANAGEMENT**:
    - Check "Install all Windows patch updates".
    - Check "Critical updates".
    - Check "Security updates".
    - Check "Definition updates".
    - Leave "Hardware driver updates" and "Feature packs" unchecked (these can cause instability).

12. Under **SOFTWARE PATCH MANAGEMENT**:
    - Optionally check "Update All" to update all detected software.
    - In the "EXCLUDED SOFTWARE PATCHES" text area, type any application names to skip (one per line), e.g., software with known update compatibility issues.

13. Under **DISK MANAGEMENT**:
    - Optionally check "Defragment (All disks)" for HDDs. Leave unchecked for SSDs (defragmentation is unnecessary and harmful for SSDs).
    - Check "Run Checkdisk (All disks)" to scan for disk errors.

14. Under **MAINTENANCE**:
    - Check "Create System Restore Point" — always recommended before patching.
    - Check "Delete Temp Files" — safe and reduces disk usage.
    - Leave "Reboot" unchecked unless you have confirmed with clients that a reboot is acceptable.

15. In the **SCRIPTS** section, you can attach any scripts from the library to run after maintenance.

16. Click **Save Profile**.
17. You will see "Profile saved!" and the profile will appear in the Profile List tab.

### Step-by-step: Running a Profile Immediately

1. Go to **Automation** → **Profile List** tab.
2. Find the profile you want to run.
3. Click the **Run Now** button next to that profile.
4. A confirmation message will show how many devices the profile has been queued on.
5. Navigate to **Maintenance** to see the run log as tasks complete.

### Practical Example: Setting Up Weekly Patching for a New Client

Greenway Manufacturing has just been onboarded. They need weekly security patches every Sunday night.

1. Go to **Automation** → **Create / Edit Profile**.
2. Profile Name: "Greenway Manufacturing — Weekly Security Patches"
3. Active: Checked
4. Schedule: weekly, Sunday, 23:00
5. Email notification: `it-contact@greenway.com`, `your.email@company.com`
6. OS Patches: Critical updates and Security updates checked only.
7. Maintenance: Create Restore Point checked, Delete Temp Files checked.
8. Click **Save**.
9. On Monday morning, check the **Maintenance** run log to confirm patches were applied.
10. Review the **OS Patches** page to verify compliance has improved.

### Disabling and Deleting Profiles

To **disable** a profile without deleting it:
1. Go to **Create / Edit Profile**.
2. Select the profile from the dropdown.
3. Uncheck the **Active** checkbox.
4. Click the **Disable** button or save.
5. The profile dot in the list will turn grey.

To **delete** a profile:
1. Select it in the dropdown.
2. Click the **Delete** button.
3. The profile will be permanently removed.

> **WARNING:** Deleting a profile cannot be undone. If you only want to pause it temporarily, disable it instead.

### Tips and Gotchas

- Rebooting is part of the Maintenance column but is a high-impact action. Always coordinate with clients before enabling the Reboot checkbox in any automated profile.
- If "Upgrade Windows 10 (latest build)" is checked under Software Patches, the agent may initiate a major Windows feature update — this is a significant operation. Only enable for environments where you have tested and approved the upgrade.
- The "Run on newly installed agents" option is powerful — it means every new device automatically gets patched. Ensure the profile's tasks are safe before enabling this.

---

## Chapter 15: OS Patch Management

### What it is

The OS Patches page manages Windows Update deployment across all your managed devices. You can see which patches are pending approval, approve batches of patches, review patch history, and configure policies.

### Who uses it

Technicians and administrators.

### The Four Stat Cards

| Card | Description |
|---|---|
| Pending | Patches waiting for your approval before deployment |
| Approved | Patches approved but not yet deployed to devices |
| Deployed | Patches successfully deployed to devices |
| Compliance % | Percentage of devices that are fully patched |

Compliance color coding:
- **Green (90%+):** Good patch health
- **Amber (70–89%):** Needs attention
- **Red (<70%):** Poor compliance — many devices are out of date

### The Pending Patches Tab

This tab shows all patches waiting for your approval. Each patch shows:
- Patch name (descriptive name including the KB number)
- Type badge (critical, security, definition, rollup, feature, driver, update)
- KB number
- Which device reported this patch as available

**Approving patches:**
1. Use the checkboxes on the left of each patch row to select patches you want to approve.
2. Select one, several, or all patches.
3. Click the **Approve Selected (N)** button (where N is the count of selected patches).
4. Approved patches will be queued for deployment to the relevant devices on their next agent check-in.

> **NOTE:** Approving a patch does not immediately install it. The agent on the target device will receive the approval on its next heartbeat cycle and then proceed with installation.

### The Patch History Tab

This tab shows all patches across all statuses — pending, approved, deployed, and failed. It is displayed as a structured table with columns:

| Column | Description |
|---|---|
| Patch Name | Full descriptive name |
| Type | Color-coded patch type badge |
| Status | Current status (DEPLOYED, APPROVED, PENDING, FAILED) |
| Device | Which device this patch applies to |
| Date | Deployment or creation date |

Use this tab for compliance audits and to verify that specific patches have been applied.

### The Policies Tab

The Policies tab links to Automation Profiles for granular patch policy configuration. Patch policies — including auto-approval rules, maintenance windows, and exclusions — are managed through Automation Profiles (Chapter 14).

### Step-by-step: Approving This Week's Security Patches

1. Go to **OS Patches** in the sidebar.
2. Check the **Pending Patches** tab. Look at the count.
3. Filter visually by type: prioritize any patches with a red "critical" or orange "security" badge.
4. Check the checkbox next to all critical and security patches.
5. Click **Approve Selected (N)**.
6. A success message confirms how many were approved.
7. Check back in a few hours (after agents have checked in) and switch to **Patch History** to verify they show as "DEPLOYED".

### Practical Example: Checking Patch Compliance for a Client

The client DataSafe Ltd asks you to confirm that all their servers have the latest security patches. Here is how:

1. Go to **OS Patches** → **Patch History** tab.
2. Look at the Device column for any device names belonging to DataSafe Ltd.
3. Filter the table to show DataSafe devices (if filtering is available, use it; otherwise scroll).
4. Check that all patches show status DEPLOYED.
5. Look at the **Compliance %** stat card. If it is below 90%, there are devices still needing patches.
6. Go back to **Pending Patches** and approve any remaining patches for DataSafe devices.
7. Export a Report (Chapter 11) with template `patch_summary` for DataSafe Ltd to provide documentation.

### Tips and Gotchas

- Patch deployment requires the agent to be online. Devices that are offline will not receive patches until they reconnect and the agent checks in.
- Definition updates (antivirus signature files) are frequent and low risk. It is safe to auto-approve these via an Automation Profile.
- Feature packs and service packs are high-risk — they can cause compatibility issues. Only approve these in controlled maintenance windows after testing.

---

## Chapter 16: Software Patches

### What it is

The Software Patches page manages third-party software updates on individual devices — applications like Chrome, Firefox, 7-Zip, VLC, and others that can be updated via winget or chocolatey package managers.

### Who uses it

Technicians and administrators.

### Page Layout

The page has a **two-column layout**:

**Left column:**
- A device selector dropdown showing only online devices.
- A device info card displaying hostname, OS, IP, and other details.
- A **Check for Updates** button.

**Right column:**
- A searchable table of all installed software packages detected on the selected device (winget/chocolatey packages).

### Step-by-step: Checking for Software Updates on a Device

1. Click **Software Patches** in the sidebar (under PATCHING).
2. In the left column, use the device selector dropdown to choose an online device.
3. The device info card will show the selected device's hostname, OS, and IP.
4. Click the **Check for Updates** button.
5. The system will check available updates for installed packages and display any that need updating.
6. The right column will update to show the full software list with update status indicators.

> **NOTE:** Only online devices appear in the Software Patches device selector. If a device is offline, it cannot be patched remotely until it comes back online.

### Understanding the Software Table

The right column shows the software inventory for the selected device. Each row shows the package name, version, and publisher. For packages detected as having available updates, this may be highlighted.

### Practical Example: Updating Chrome on a Device

1. Go to **Software Patches**.
2. Select the target device from the left column dropdown.
3. Click **Check for Updates**.
4. Look in the right column for "Google Chrome".
5. If an update is available, select it (or use the appropriate button to queue the update).
6. The update will be queued to the agent on that device.

### Tips and Gotchas

- Software patching via winget/chocolatey requires that these package managers are available on the device. Most modern Windows 10/11 systems have winget by default.
- Some enterprise software cannot be updated via winget. Those packages will appear in the inventory but updates must be handled manually.
- Unlike OS patches, software patches are done device-by-device through this interface. For bulk software patching across many devices, use Automation Profiles (Chapter 14).

---

## Chapter 17: Disk Management

### What it is

Disk Management gives you a visual and actionable view of disk usage across any selected device. It shows gauge charts for each disk drive and provides action buttons to perform disk maintenance remotely.

### Who uses it

Technicians and administrators.

### What You See

After selecting a device, the page shows:

**Gauge Charts (up to 4 drives):**
Each drive gets a Plotly gauge chart showing the percentage of disk space used. The gauge has color coding:
- **Green:** Under 75% used (healthy)
- **Yellow/Amber:** 75–90% used (warning zone)
- **Red:** Over 90% used (critical — needs immediate attention)

**Summary Table:**
Below the gauges is a table listing all disks with their used space, total capacity, and percentage.

**Action Buttons:**
- **Defragment** — Schedules a disk defragmentation job on the agent (best for HDDs only, not SSDs).
- **Check Disk** — Runs a chkdsk analysis on the selected disk.
- **Clean Temp Files** — Deletes temporary files to free space.

These actions are queued via the agent and executed remotely.

### Step-by-step: Investigating High Disk Usage

1. Click **Disk Management** in the sidebar (under TOOLS).
2. Select the target device from the dropdown at the top.
3. View the gauge charts. Any gauge in the red zone requires attention.
4. Read the summary table to see exact GB used and available.
5. If space is critically low:
   a. Click **Clean Temp Files** to free up common temp locations.
   b. If still critical, go to **Scripts** and run a "Get Largest Files" script to find what is taking space.
   c. Consider defragmentation only if the drive is an HDD and fragmentation is the suspected issue.
6. After running cleanup actions, wait for the agent to confirm completion (check the maintenance run log).
7. Refresh the page to see updated disk metrics.

### Practical Example: Emergency Disk Cleanup

Alert fires at 3pm: RETAIL-PC05 disk usage at 93%. The machine cannot be rebooted during business hours.

1. Go to **Disk Management**.
2. Select RETAIL-PC05.
3. The Drive C: gauge is deep red at 93%.
4. Click **Clean Temp Files**. A success/queued message appears.
5. Wait 2 minutes for the agent to process the command.
6. Go to **Devices**, select RETAIL-PC05, and check the disk metric.
7. If disk is now at 88% (yellow zone), the immediate crisis is resolved.
8. Create a ticket for a full disk audit to be done during the next maintenance window.

### Tips and Gotchas

- Do not defragment SSDs. Defragmentation wears out SSD cells and provides no performance benefit. Only run Defragment on traditional spinning hard drives (HDDs).
- Cleaning temp files is safe and non-destructive. It targets Windows temp directories, browser caches, and similar locations.
- If a gauge shows 100% disk used, the system may be unable to function properly. This is an emergency — escalate immediately.

---

## Chapter 18: Maintenance Actions

### What it is

The Maintenance page lets you perform direct remote actions on a selected online device: reboot, shutdown, create restore points, delete temp files, clear browser history, and run a disk check. It also shows a log of recent maintenance runs.

### Who uses it

Technicians and administrators.

### Critical Safety Features

**Only online devices are shown.** The device selector only lists devices that are currently online. If a device is offline, it will not appear.

**Confirmation checkbox required.** Before any action button becomes effective, you must check the confirmation box: "I confirm this action on the selected device." If you click any action button without checking this box, you get a warning message and nothing happens.

> **IMPORTANT:** Reboot and Shutdown are live commands — they execute immediately on the device. Rebooting a server in use will disconnect all connected users. Shutting down a server will take it completely offline. Always confirm with the client before executing these actions.

### The Device Info Card

After selecting a device, a card shows:
- Hostname and IP address (with green online indicator dot)
- Operating System and version
- Platform
- Last Seen timestamp
- Uptime (how long since last reboot)

This card helps you confirm you have selected the correct device before taking any action.

### Available Actions

| Button | Effect | Risk Level |
|---|---|---|
| Reboot | Sends an immediate reboot command to the device | HIGH — interrupts active users |
| Shutdown | Sends an immediate shutdown command | HIGH — takes device offline |
| Create Restore Point | Creates a Windows system restore point | LOW — safe, no disruption |
| Delete Temp Files | Removes temporary files to free space | LOW — safe, no disruption |
| Clear Browser History | Clears saved browser data | MEDIUM — may affect users with saved sessions |
| Check Disk | Runs a disk health check (chkdsk) | LOW — read-only scan |

> **NOTE:** Create Restore Point, Delete Temp Files, Clear Browser History, and Check Disk are queued via the agent and will be available in Phase 5 of development. In the current version, clicking these buttons shows an informational message. Reboot and Shutdown are live and fully functional.

### Step-by-step: Rebooting a Device

1. Click **Maintenance** in the sidebar (under TOOLS).
2. Select the target device from the dropdown. Only online devices appear.
3. Confirm the device info card shows the correct machine — check hostname and IP.
4. Before proceeding:
   - Verify the device is not actively in use (contact the user or check activity)
   - Confirm with the customer that a reboot is acceptable
5. Check the **"I confirm this action on the selected device"** checkbox.
6. Click the **Reboot** button.
7. A spinner shows "Sending reboot command to [hostname]..."
8. You will see "Reboot command sent to [hostname]." — the command has been dispatched.
9. The device will reboot and will appear offline in the Devices page for a few minutes.
10. After reboot, the agent will reconnect and the device will return to online status.
11. Verify the device is back online by checking the Devices page after 5–10 minutes.

### Step-by-step: Checking Recent Maintenance Runs

1. Scroll to the bottom of the Maintenance page (after selecting a device).
2. The **Recent Maintenance Runs** section shows a table of the last 20 automation profile runs.
3. Columns: Profile name, Device, Started, Finished, Status badge.
4. Status colors:
   - **success** (green): Completed successfully
   - **failed** (red): Encountered an error
   - **running** (amber): Currently in progress
   - **pending** (grey): Queued but not yet started

### Practical Example: Coordinated Reboot of a Server After Patching

After an OS patch has been applied to CORP-SRV01, a reboot is required to complete installation. It is 8pm (after hours).

1. Go to **Maintenance**.
2. Select CORP-SRV01 from the dropdown.
3. Check the Uptime in the device info card — it shows the machine has been up for 3 days and was last seen 2 minutes ago (still online).
4. Check: "I confirm this action on the selected device."
5. Click **Reboot**.
6. Confirm: "Reboot command sent to CORP-SRV01."
7. Go to **Devices** and watch for CORP-SRV01 to go offline, then come back online.
8. Once it returns online (5–10 minutes), verify the patch applied correctly via the **OS Patches** → Patch History tab.
9. Add a comment to the relevant ticket: "CORP-SRV01 rebooted at 8:02pm. Back online at 8:09pm. Patch verified applied."

### Tips and Gotchas

- The confirmation checkbox state is per device per session. If you switch devices, the checkbox resets.
- Do not click Shutdown on a server during business hours without explicit approval. Shutting down a server can cause significant disruption.
- If a reboot or shutdown command is sent but the device does not come back online within 20 minutes, escalate to on-site support — there may be a hardware or startup issue.

---

## Chapter 19: Scripts — Running and Writing

### What it is

The Scripts page is one of the most powerful features of the RMM system. It lets you run automated scripts on managed devices from a central interface — no need to remote desktop into machines individually. You can run built-in scripts from the library, upload custom scripts, and review the execution history of all past runs.

### Who uses it

Technicians and administrators for day-to-day use. Developers for creating and maintaining the script library.

### Supported Script Types

| Type | Badge Color | Language | Typical Use |
|---|---|---|---|
| ps1 | Blue | PowerShell | Windows automation, registry, services, users |
| bat | Orange | Windows Batch | Simple system commands, legacy compatibility |
| py | Green (#407E3C) | Python | Complex logic, API calls, cross-platform |
| sh | Purple | Shell/Bash | Linux/macOS tasks (if running non-Windows agents) |

### The Three Tabs

**Library Tab**
Browse all available scripts. Each script shows as an expandable card in the list:
- A tag indicating whether it is a built-in script (📌 Built-in) or a custom upload (📝 Custom)
- Script name and type in the expander label
- On expansion: type badge, OS target, creation date, description
- A device multi-select to choose which online devices to run it on
- A timeout setting (10–900 seconds, default 300)
- A **Run** button

Use the search field at the top to filter scripts by name or description.

**Upload Tab**
Create a new script from scratch directly in the browser:
- Script Name (required)
- Type dropdown (ps1, bat, py, sh)
- Description (what the script does)
- Script Content text area (where you write or paste the code)

Click **Upload Script** to save it to the library.

**Run History Tab**
Shows the last 50 script executions. Each entry shows:
- Status icon: ✅ success, ❌ failed, ⏳ queued, 🔄 running, ⏰ timeout
- Script name
- Device hostname
- Status
- Triggered timestamp

Expanding a run entry shows:
- Duration (calculated from started_at and completed_at)
- Exit code (0 = success on most scripts, non-zero = error)
- stdout output (what the script printed to standard output)
- stderr output (any error messages)

### Step-by-step: Running a Script on a Single Device

1. Click **Scripts** in the sidebar (under TOOLS).
2. On the **Library** tab, use the search field to find the script you want.
3. Click the script entry to expand it.
4. In the **"Run on online devices"** multi-select, click to open the dropdown and select the target device.
5. Adjust the **Timeout (s)** if needed. The default of 300 seconds (5 minutes) is suitable for most scripts. Increase for long-running operations like disk scans.
6. Click **Run**.
7. A success message appears: "Queued on 1 device(s)."
8. Go to the **Run History** tab. The run will appear with status ⏳ QUEUED.
9. After a minute or so, refresh the page. The status will change to ✅ SUCCESS or ❌ FAILED.
10. Expand the run entry to see the script output.

### Step-by-step: Running a Script on Multiple Devices at Once

1. Follow steps 1–4 above.
2. In the multi-select, click multiple device names. Each selected device will be highlighted.
3. Click **Run**.
4. The success message will show "Queued on [N] device(s)" where N is the count you selected.
5. In Run History, you will see one entry per device.

### Practical Example: Running a Cleanup Script on 10 Devices at Once

Your manager asks you to run the "Clear Temp Files" script on all 10 devices belonging to QuickPrint Co during off-hours.

1. Go to **Scripts** → **Library** tab.
2. Search for "temp" or "cleanup".
3. Find and expand the appropriate script.
4. In the device multi-select, select all 10 QuickPrint Co devices (they must be online — confirm on the Devices page first).
5. Set timeout to 120 seconds (temp cleanup is fast).
6. Click **Run**.
7. Confirm: "Queued on 10 device(s)."
8. Check **Run History** after 5 minutes. All 10 runs should show ✅ SUCCESS.
9. If any show ❌ FAILED, expand that entry to read the stderr output and diagnose the failure.

### Step-by-step: Uploading a New Script

1. Click **Scripts** in the sidebar.
2. Click the **Upload** tab.
3. In **Script Name**, enter a clear descriptive name: "Get Top 10 Largest Files"
4. Select the **Type**: `ps1` (PowerShell for Windows)
5. In **Description**, explain what it does: "Lists the 10 largest files on Drive C: sorted by size in descending order."
6. In the **Script Content** text area, paste or write the script code (see Chapter 21 for guidance).
7. Click **Upload Script**.
8. A "Script uploaded!" success message appears.
9. Switch to the **Library** tab and search for your script to confirm it is there.
10. It will now be available to run on any device.

### Reading Script Output

When a script completes, the output is captured by the agent and sent back to the API. To read it:

1. Go to **Run History** tab.
2. Find your run entry.
3. Expand it.
4. **stdout** shows normal output — what the script printed. This is your result data.
5. **stderr** shows error output — error messages, exceptions, warnings.

A successful script (exit code 0) with output in stdout is the expected pattern. If you see output in stderr, investigate even if exit code is 0 — the script may have encountered non-fatal warnings.

### Tips and Gotchas

- Only online devices appear in the device multi-select. If a target device is not shown, it is offline.
- A "timeout" status means the script ran longer than the configured timeout. Increase the timeout value and try again, or investigate why the script is taking so long.
- Script content is stored in the database in plain text. Do not include passwords, API keys, or sensitive credentials in scripts. Use environment variables or secure input prompts instead.
- PowerShell scripts run with the permissions of the agent service account. If the agent runs as a standard user, it may not have permission to perform admin-level actions. Run the agent as Administrator for full capability.

---

# PART IV — TECHNICAL REFERENCE

---

## Chapter 20: System Architecture Overview

### Component Map

```
┌─────────────────────────────────────────────────────┐
│  Browser (http://localhost:8501)                     │
│  Streamlit Dashboard — Python/Streamlit              │
│  dashboard/app.py + dashboard/pages/*.py             │
└────────────────┬────────────────────────────────────┘
                 │ HTTP REST API calls
                 │ (JWT Bearer token in headers)
┌────────────────▼────────────────────────────────────┐
│  Flask API (http://localhost:5000)                   │
│  api/app.py, api/routes/*.py                         │
│  api/models/*.py (SQLAlchemy ORM)                    │
│  api/services/*.py (business logic)                  │
│  api/tasks/*.py (Celery async tasks)                 │
└──────┬─────────────────┬───────────────┬────────────┘
       │                 │               │
   PostgreSQL        Redis/Celery    Agent API
   localhost:5432    localhost:6379  /api/agent/*
   db: rmmdb         Task queue
                         │
              ┌──────────▼──────────┐
              │  Celery Workers      │
              │  Background tasks:   │
              │  - Alert evaluation  │
              │  - Patch deployment  │
              │  - Script dispatch   │
              └─────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Python Agent        │
              │  agent/rmm_agent.py  │
              │  Runs on managed     │
              │  Windows machines    │
              │  Heartbeat: 60s      │
              │  SW scan: 6h         │
              └─────────────────────┘
```

### Service Startup Order

Services must be started in this order:

1. **PostgreSQL** — must be running before anything else. On Windows with Memurai: ensure the service is running in Windows Services.
2. **Redis/Memurai** — required by Celery. Start the Redis server.
3. **Flask API** — `cd api ; python app.py`
4. **Celery Worker** — `cd api ; celery -A tasks.celery_app worker --pool=solo -l info`
5. **Celery Beat** — `cd api ; celery -A tasks.celery_app beat -l info`
6. **Streamlit Dashboard** — `cd dashboard ; streamlit run app.py`
7. **Agent (on managed machines)** — `cd agent ; python rmm_agent.py` (run as Administrator for full capability)

### Directory Structure

```
RemoteManagementSystem/
├── api/
│   ├── app.py              # Flask application factory
│   ├── config.py           # Configuration class
│   ├── extensions.py       # SQLAlchemy, JWT, Celery setup
│   ├── models/             # Database models (SQLAlchemy)
│   ├── routes/             # API endpoint blueprints
│   ├── schemas/            # Marshmallow serialization schemas
│   ├── services/           # Business logic layer
│   ├── tasks/              # Celery async tasks
│   ├── migrations/         # Alembic database migrations
│   └── tests/              # pytest test suite
├── agent/
│   ├── rmm_agent.py        # Main agent loop (register/heartbeat/execute)
│   ├── collector.py        # Hardware info, metrics, software inventory
│   ├── heartbeat.py        # API client for agent communication
│   ├── executor.py         # Task execution engine
│   ├── script_runner.py    # Script execution (ps1, bat, py, sh)
│   └── config.ini          # Agent configuration
├── dashboard/
│   ├── app.py              # Login page and sidebar scaffold
│   ├── pages/              # One file per page (Streamlit multipage)
│   ├── components/         # Reusable UI components
│   └── utils/
│       ├── auth.py         # JWT login/logout/session management
│       ├── api_client.py   # HTTP client wrapping all API calls
│       ├── styles.py       # CSS injection, stat cards, badge HTML
│       └── formatters.py   # Date, byte, color formatting utilities
├── scripts_library/        # Built-in script files stored on disk
├── docs/                   # Additional documentation
└── CLAUDE.md               # Project-level AI assistant instructions
```

### Authentication Flow

1. User submits email + password to dashboard login form.
2. Dashboard's `utils/auth.py` calls `POST /api/auth/login` on the Flask API.
3. API validates credentials against the `users` table using bcrypt password hashing.
4. If valid, API returns a JWT access token signed with `JWT_SECRET_KEY`.
5. Dashboard stores the token in `st.session_state["access_token"]`.
6. The token is appended to sidebar navigation links as `?tok=<token>`.
7. On each page load, `_restore_from_query_params()` reads the token from the URL and restores the session.
8. All subsequent API calls from `utils/api_client.py` include the token as `Authorization: Bearer <token>`.
9. Flask's `@jwt_required()` decorator validates the token on protected routes.

### Agent Registration Flow

1. Agent reads `config.ini` on startup.
2. If `device_id` is blank, the agent is unregistered.
3. Agent calls `POST /api/agent/register` with hardware info (hostname, OS, CPU, RAM, disk) and the `org_token` from config.
4. API creates a device record in the database and returns a `device_id` and `agent_token`.
5. Agent saves these to `config.ini`.
6. On subsequent startups, agent uses stored `device_id` and `agent_token`.
7. Every 60 seconds, agent calls `POST /api/agent/heartbeat` with current metrics.
8. API updates the device's `last_seen` timestamp and latest metrics.
9. API evaluates alert rules against the new metrics.
10. If tasks (scripts, patches, maintenance) are queued, they are returned in the heartbeat response.
11. Agent executes any returned tasks.

### Database Models Overview

| Model | Table | Key Fields |
|---|---|---|
| User | users | id, email, password_hash, role, is_active |
| Customer | customers | id, name, email, phone, tier |
| Device | devices | id, hostname, ip_address, os_name, customer_id, is_online, last_seen |
| DeviceMetrics | device_metrics | id, device_id, cpu_pct, ram_pct, disk_pct, timestamp |
| Alert | alerts | id, device_id, severity, message, status, triggered_at |
| AlertRule | alert_rules | id, name, metric, operator, threshold, severity, cooldown_minutes |
| Ticket | tickets | id, title, description, customer_id, priority, status, source |
| Script | scripts | id, name, file_type, content, is_builtin |
| ScriptRun | script_runs | id, script_id, device_id, status, exit_code, stdout, stderr |
| Patch | patches | id, device_id, patch_name, kb_id, patch_type, status |
| AutomationProfile | automation_profiles | id, name, schedule_type, is_active, os_patch_config, ... |
| Invoice | invoices | id, customer_id, period_start, period_end, device_count, amount, status |

---

## Chapter 21: Script Writing Guide

### Overview

Scripts are the automation workhorses of the RMM system. You can write scripts in PowerShell (ps1), Windows Batch (bat), Python (py), or Shell (sh). The agent executes them on the managed device and captures stdout and stderr output, which is sent back to the RMM and displayed in Run History.

### PowerShell (ps1) — Recommended for Windows

PowerShell is the preferred language for Windows automation. It has access to .NET, WMI, registry, COM objects, and all Windows management APIs.

**Basic template:**
```powershell
# Script: Get System Information
# Description: Returns OS, CPU, RAM, and disk info

try {
    $os = Get-WmiObject Win32_OperatingSystem
    $cpu = Get-WmiObject Win32_Processor
    $disk = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3"

    Write-Output "=== System Information ==="
    Write-Output "OS: $($os.Caption) Build $($os.BuildNumber)"
    Write-Output "CPU: $($cpu.Name)"
    Write-Output "RAM: $([math]::Round($os.TotalVisibleMemorySize / 1MB, 2)) GB total"
    Write-Output ""
    Write-Output "=== Disk Usage ==="
    foreach ($d in $disk) {
        $pct = [math]::Round((1 - ($d.FreeSpace / $d.Size)) * 100, 1)
        Write-Output "Drive $($d.DeviceID): $pct% used ($([math]::Round($d.FreeSpace/1GB,1)) GB free)"
    }
    exit 0
} catch {
    Write-Error "Script failed: $_"
    exit 1
}
```

**Key conventions for PS1 scripts:**
- Use `Write-Output` (not `Write-Host`) for output you want captured. `Write-Host` goes to the console, not stdout.
- Use `Write-Error` for error output — this appears in stderr.
- Exit with `exit 0` on success, `exit 1` (or non-zero) on failure.
- Wrap in try/catch blocks to handle exceptions gracefully.
- Use `-ErrorAction Stop` in cmdlets where you want exceptions to be catchable.

**Example: Get 10 Largest Files on C:**
```powershell
# Script: Get Top 10 Largest Files
# Description: Lists the 10 largest files on C: sorted by size

try {
    $files = Get-ChildItem -Path "C:\" -Recurse -File -ErrorAction SilentlyContinue |
             Sort-Object Length -Descending |
             Select-Object -First 10

    Write-Output "Top 10 largest files on C:"
    Write-Output "----------------------------------------"
    foreach ($f in $files) {
        $sizeMB = [math]::Round($f.Length / 1MB, 1)
        Write-Output "$sizeMB MB  $($f.FullName)"
    }
    exit 0
} catch {
    Write-Error "Error: $_"
    exit 1
}
```

**Example: Clear Temp Files:**
```powershell
# Script: Clear Temp Files
# Description: Removes files from Windows temp directories

$tempPaths = @(
    $env:TEMP,
    $env:TMP,
    "C:\Windows\Temp",
    "C:\Windows\Prefetch"
)

$freed = 0
foreach ($path in $tempPaths) {
    if (Test-Path $path) {
        $files = Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue
        foreach ($file in $files) {
            try {
                $freed += $file.Length
                Remove-Item $file.FullName -Force -ErrorAction SilentlyContinue
            } catch { }
        }
    }
}

$freedMB = [math]::Round($freed / 1MB, 1)
Write-Output "Freed approximately $freedMB MB from temp directories."
exit 0
```

### Windows Batch (bat)

Batch scripts are simpler and suitable for basic command execution. Less preferred than PowerShell but useful for legacy compatibility.

**Template:**
```batch
@echo off
:: Script: List Running Services
:: Description: Shows all running Windows services

net start
if %ERRORLEVEL% EQU 0 (
    echo Services listed successfully.
    exit /b 0
) else (
    echo Error listing services. Error code: %ERRORLEVEL%
    exit /b 1
)
```

**Key conventions for BAT scripts:**
- Use `@echo off` at the top to suppress command echoing.
- Write comments with `::`.
- Exit codes: `exit /b 0` for success, `exit /b 1` for failure.
- All output goes to stdout by default (no distinction needed like PS1).

### Python (py)

Python scripts are useful for complex logic, data processing, or tasks that need libraries. The agent runs these using the Python interpreter.

**Template:**
```python
#!/usr/bin/env python3
"""
Script: Get Process CPU Usage
Description: Lists top 10 processes by CPU usage
"""

import sys
import subprocess

def main():
    try:
        # Use PowerShell from Python for Windows process info
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 | Format-Table Name,CPU,WorkingSet -AutoSize"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(result.stdout)
            return 0
        else:
            print(f"Error: {result.stderr}", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Script error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Key conventions for Python scripts:**
- Write output to `sys.stdout` or use `print()`.
- Write errors to `sys.stderr` using `print(..., file=sys.stderr)`.
- Exit with `sys.exit(0)` for success, `sys.exit(1)` for failure.
- Keep dependencies minimal — only standard library where possible. The agent's Python environment may not have third-party packages installed.

### Shell (sh)

Shell scripts run on Linux/macOS agents. Use for non-Windows managed devices.

**Template:**
```bash
#!/bin/bash
# Script: Disk Usage Summary
# Description: Shows disk usage for all mounted filesystems

df -h
if [ $? -eq 0 ]; then
    echo "Disk usage listed successfully."
    exit 0
else
    echo "Error running df command." >&2
    exit 1
fi
```

### Best Practices for All Script Types

1. **Always include a description** — future team members will thank you.
2. **Use exit codes correctly** — 0 = success, non-zero = failure. The system uses exit codes to determine FAILED vs SUCCESS status.
3. **Handle errors** — do not let scripts crash silently. Catch errors and write them to stderr.
4. **Limit output** — scripts with hundreds of MB of output will fill the database. Use `Select-Object -First 50` or similar to limit results.
5. **Test before deploying to production** — test scripts on a dev/test device before running on client machines.
6. **Never hardcode credentials** — do not include passwords, API keys, or tokens in scripts. Use environment variables or Windows Credential Manager instead.
7. **Idempotent where possible** — a script that can be safely run multiple times (same result each time) is safer than one that changes things permanently on each run.

---

## Chapter 22: Alert Rules — Writing Effective Rules

### Overview

Alert rules define the conditions under which the system automatically generates an alert. Each rule monitors one metric on one comparison operator with one threshold. Multiple rules combine to give you comprehensive coverage.

### Rule Anatomy

```
Rule: "Critical CPU Alert"
├── Metric:    cpu
├── Operator:  gt (greater than)
├── Threshold: 90 (%)
├── Severity:  critical
├── Cooldown:  15 (minutes)
└── Auto-ticket: true
```

When any device's CPU metric exceeds 90%, a critical alert is created. It will not fire again for the same device for 15 minutes (cooldown). A ticket is auto-created.

### Available Metrics

| Metric | What It Measures | Threshold Unit |
|---|---|---|
| cpu | CPU usage percentage from latest heartbeat | % (0–100) |
| ram | RAM usage percentage from latest heartbeat | % (0–100) |
| disk | Primary disk usage percentage | % (0–100) |
| battery | Battery level percentage (laptops) | % (0–100) |
| offline | Device stops sending heartbeats | N/A — threshold ignored |

### Operators

| Operator | Symbol | Use When |
|---|---|---|
| gt | > (greater than) | Alert when metric goes above a level |
| gte | >= (greater than or equal) | Alert when metric reaches or exceeds a level |
| lt | < (less than) | Alert when metric drops below a level (e.g., low battery) |
| lte | <= (less than or equal) | Alert when metric falls to or below a level |

### Recommended Rule Set

For a standard managed environment, implement these rules as a baseline:

```
1. Critical CPU Alert
   Metric: cpu, Operator: gt, Threshold: 90, Severity: critical, Cooldown: 15min, Auto-ticket: yes

2. High CPU Warning
   Metric: cpu, Operator: gt, Threshold: 75, Severity: warning, Cooldown: 30min, Auto-ticket: no

3. Critical RAM Alert
   Metric: ram, Operator: gt, Threshold: 90, Severity: critical, Cooldown: 15min, Auto-ticket: yes

4. High RAM Warning
   Metric: ram, Operator: gt, Threshold: 80, Severity: warning, Cooldown: 30min, Auto-ticket: no

5. Critical Disk Alert
   Metric: disk, Operator: gt, Threshold: 90, Severity: critical, Cooldown: 60min, Auto-ticket: yes

6. Disk Warning
   Metric: disk, Operator: gt, Threshold: 75, Severity: warning, Cooldown: 120min, Auto-ticket: no

7. Device Offline Alert
   Metric: offline, Severity: warning, Cooldown: 60min, Auto-ticket: no

8. Low Battery Warning (for laptops)
   Metric: battery, Operator: lt, Threshold: 20, Severity: warning, Cooldown: 60min, Auto-ticket: no
```

### Cooldown Tuning

The cooldown period is critical to avoid alert fatigue. If a device's CPU is consistently at 95%, and your cooldown is 5 minutes, you will receive 12 alerts per hour for that one device. This drowns out other alerts and causes fatigue.

**Recommended cooldowns by severity:**

| Severity | Recommended Cooldown |
|---|---|
| critical | 15–30 minutes |
| warning | 60–120 minutes |
| info | 240+ minutes |

For the "offline" metric, use a longer cooldown (60+ minutes) because network fluctuations can cause brief disconnects that are not real outages.

### Auto-Ticket Policy

Use auto-create ticket conservatively:
- **Enable for:** critical alerts (CPU >90%, disk >90%, device offline during business hours)
- **Disable for:** warning-level alerts and informational alerts — these can be reviewed and tickets created manually if needed

An environment with too many auto-created tickets becomes noisy and technicians start ignoring them.

---

## Chapter 23: Automation Profile Design

### Design Principles

A well-designed automation profile answers these questions:
1. What tasks need to run?
2. How often?
3. At what time to minimize disruption?
4. On which devices?
5. What should happen if something fails?

### Profile Templates

**Template 1: Nightly Security Maintenance (Standard)**
```
Schedule: daily, 02:00
OS Patches: critical + security only
Software Patches: update_all = false, excluded = [known problem packages]
Disk: checkdisk = true, defrag = false
Maintenance: restore_point = true, delete_temp = true
Reboot: false
```
Use for: all standard client devices, every night.

**Template 2: Weekend Full Maintenance**
```
Schedule: weekly, Sunday, 23:00
OS Patches: all categories including rollups
Software Patches: update_all = true
Disk: defrag = true (for HDDs only), checkdisk = true
Maintenance: restore_point = true, delete_temp = true, clear_history = true
Reboot: true (at end of maintenance window)
```
Use for: servers and workstations where a weekly full maintenance is acceptable.

**Template 3: Monthly Patch Tuesday**
```
Schedule: monthly, second Tuesday, 22:00
OS Patches: critical + security + definitions
Software Patches: update_all = false
Disk: checkdisk = true
Maintenance: restore_point = true
Reboot: true
```
Use for: enterprise clients who prefer controlled monthly patching aligned with Microsoft's Patch Tuesday.

### Avoiding Common Automation Mistakes

1. **Do not schedule reboots on devices that are always in use.** Check with clients before enabling Reboot in any profile.

2. **Test on one device before fleet-wide rollout.** Create the profile, set it to manual (on_demand), run it on one test device, and verify before activating the schedule.

3. **Exclude known problematic packages.** If a software update consistently breaks an application, add it to the excluded list in the Software Patch Management column.

4. **Stagger schedules across clients.** If all clients run their profiles at exactly 2:00 AM, the API and database will be hit simultaneously. Spread profiles across different times (2:00, 2:30, 3:00, etc.).

5. **Review run history.** After each profile run, check the Maintenance run log for failed runs. A profile that consistently fails on the same device needs investigation.

---

## Chapter 24: User Roles and Permissions Matrix

### Full Permissions Matrix

| Feature / Action | Viewer | Technician | Admin |
|---|---|---|---|
| **Dashboard** | | | |
| View Dashboard Overview | Yes | Yes | Yes |
| **Tickets** | | | |
| View tickets | Yes | Yes | Yes |
| Create tickets | No | Yes | Yes |
| Update ticket status | No | Yes | Yes |
| Add comments (public) | No | Yes | Yes |
| Add comments (internal) | No | Yes | Yes |
| Delete tickets | No | No | Yes |
| **Customers** | | | |
| View customers | Yes | Yes | Yes |
| Create customers | No | Yes | Yes |
| Edit customers | No | Yes | Yes |
| Delete customers | No | No | Yes |
| **Devices** | | | |
| View device list | Yes | Yes | Yes |
| View device metrics | Yes | Yes | Yes |
| View device history | Yes | Yes | Yes |
| **Alerts** | | | |
| View alerts | Yes | Yes | Yes |
| Acknowledge alerts | No | Yes | Yes |
| Resolve alerts | No | Yes | Yes |
| Create alert rules | No | Yes | Yes |
| Toggle/delete alert rules | No | Yes | Yes |
| **App Center** | | | |
| View software inventory | Yes | Yes | Yes |
| **Network Discovery** | | | |
| Run network scan | No | Yes | Yes |
| View scan results | Yes | Yes | Yes |
| **Reports** | | | |
| Generate reports | No | Yes | Yes |
| View report history | Yes | Yes | Yes |
| Download reports | Yes | Yes | Yes |
| **Billing** | | | |
| View invoices | Yes | Yes | Yes |
| Create invoices | No | No | Yes |
| Update invoice status | No | No | Yes |
| **Administration** | | | |
| Access Admin page | No | No | Yes |
| View Audit Log | No | No | Yes |
| View Users tab | No | No | Yes |
| Manage users (API) | No | No | Yes |
| **Automation** | | | |
| View profiles | Yes | Yes | Yes |
| Create/edit profiles | No | Yes | Yes |
| Run profile now | No | Yes | Yes |
| Delete profiles | No | No | Yes |
| **OS Patches** | | | |
| View pending patches | Yes | Yes | Yes |
| Approve patches | No | Yes | Yes |
| View patch history | Yes | Yes | Yes |
| **Software Patches** | | | |
| View software list | Yes | Yes | Yes |
| Check for updates | No | Yes | Yes |
| **Disk Management** | | | |
| View disk gauges | Yes | Yes | Yes |
| Run disk actions | No | Yes | Yes |
| **Maintenance** | | | |
| View maintenance page | Yes | Yes | Yes |
| Reboot/Shutdown devices | No | Yes | Yes |
| Run maintenance actions | No | Yes | Yes |
| **Scripts** | | | |
| View script library | Yes | Yes | Yes |
| Run scripts | No | Yes | Yes |
| Upload scripts | No | Yes | Yes |
| View run history | Yes | Yes | Yes |

---

## Chapter 25: Common Troubleshooting

### Problem: Cannot log in — "Invalid credentials"

**Cause:** Wrong email, wrong password, or account is deactivated.

**Steps:**
1. Verify the email address (no typos, correct domain).
2. Check Caps Lock is off.
3. If you recently changed your password, try the new password.
4. If locked out, contact an administrator to verify your account status in the database.

---

### Problem: Dashboard shows "API error: [message]"

**Cause:** The Flask API at http://localhost:5000 is not responding.

**Steps:**
1. Open a terminal on the server machine.
2. Check if the API is running: `netstat -ano | findstr :5000`
3. If no process is on port 5000, start the API: `cd api ; python app.py`
4. Wait 3 seconds, then refresh the dashboard.
5. If the API starts but immediately crashes, check `api/app.py` logs for the error message. Common causes:
   - PostgreSQL is not running (check port 5432)
   - Database connection string is wrong (check `api/.env` → `DATABASE_URL`)
   - Missing Python dependencies (run `pip install -r requirements.txt` in the `api/` directory)

---

### Problem: Devices showing as offline when they should be online

**Cause:** The agent on the device has stopped running, the device is off, or there is a network issue.

**Steps:**
1. Check the device's Last Seen timestamp on the Devices page. How long ago was it?
2. If recent (< 5 minutes): temporary network glitch — wait and check again.
3. If longer (> 10 minutes): physically check or remote into the device.
4. On the device, check if the agent is running:
   - Open Task Manager or run: `Get-Process python | Where-Object {$_.MainWindowTitle -like "*rmm*"}`
   - Check if `rmm_agent.py` is in the running process list.
5. If the agent is not running, restart it: `cd C:\path\to\agent ; python rmm_agent.py`
6. Check `agent\rmm_agent.log` for errors.

---

### Problem: Agent won't register — "Registration failed"

**Cause:** Wrong API URL in config.ini, wrong org_token, or API is not running.

**Steps:**
1. Open `agent/config.ini` on the managed device.
2. Verify the `[api]` section:
   ```ini
   [api]
   url = http://YOUR_SERVER_IP:5000
   org_token = YOUR_ORG_TOKEN
   ```
3. Ensure the IP address and port are correct and reachable from the device.
4. Test connectivity: open a browser on the device and navigate to `http://YOUR_SERVER_IP:5000/api/health`. You should get a JSON response.
5. Verify the `org_token` matches the one configured in the API's environment.

---

### Problem: Scripts not running — stuck in "queued" status

**Cause:** The agent is offline or not polling for tasks, or Celery is not running.

**Steps:**
1. Verify the target device is online (green dot on Devices page).
2. The agent polls for tasks on each heartbeat (every 60 seconds). Wait up to 2 minutes.
3. If still queued after 5 minutes, check that Celery worker is running: `celery -A tasks.celery_app worker --pool=solo -l info`
4. Check Celery logs for errors.
5. If Celery is running but tasks are not dispatching, check Redis is running on port 6379.

---

### Problem: "No pending patches" but devices are clearly not updated

**Cause:** The agent's patch discovery has not run yet, or the patch discovery feature is not yet fully implemented.

**Steps:**
1. Patch discovery happens via the agent. Verify the agent is online for those devices.
2. Check if the device has Windows Update configured to report available patches. This may require a scheduled Celery task to query the Windows Update API via the agent.
3. If the Pending Patches tab is consistently empty despite known missing patches, check the API's patch detection logic and Celery beat schedule.

---

### Problem: Automation profile runs show as "failed"

**Cause:** A task in the profile encountered an error during execution.

**Steps:**
1. Go to **Maintenance** page → Recent Maintenance Runs section.
2. Find the failed run entry.
3. Note which profile and which device failed.
4. Go to **Scripts** → Run History if the failure involves a script.
5. Check the stderr output for the error message.
6. Common causes:
   - Device went offline during execution
   - Agent did not have sufficient permissions for the task
   - A specific patch installation failed
7. Investigate the root cause before re-running.

---

### Problem: Cannot access Admin page — "Admin access required"

**Cause:** Your account has the technician or viewer role, not admin.

**Steps:**
1. This is intentional by design — Admin is restricted to admin role users only.
2. If you believe you should have admin access, contact your system administrator to update your user role in the database.
3. If you are the only user and need admin access, update the role directly in the PostgreSQL database:
   ```sql
   UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
   ```

---

### Problem: Dashboard is blank or shows error after navigating

**Cause:** JWT token has expired or is invalid.

**Steps:**
1. Navigate back to http://localhost:8501 (the main URL, no query params).
2. If you see the login screen, your session has expired. Log in again.
3. After logging in, the token will be refreshed in session state and URLs.

---

### Starting All Services — Quick Reference

```powershell
# 1. Verify PostgreSQL is running (check Windows Services)

# 2. Start Redis/Memurai (Windows service or standalone)
# Check: Test-NetConnection -ComputerName localhost -Port 6379

# 3. Start Flask API
Set-Location C:\Users\rigwe\Desktop\RemoteManagementSystem\api
python app.py

# 4. In a new terminal — Start Celery Worker
Set-Location C:\Users\rigwe\Desktop\RemoteManagementSystem\api
celery -A tasks.celery_app worker --pool=solo -l info

# 5. In a new terminal — Start Celery Beat
Set-Location C:\Users\rigwe\Desktop\RemoteManagementSystem\api
celery -A tasks.celery_app beat -l info

# 6. In a new terminal — Start Streamlit Dashboard
Set-Location C:\Users\rigwe\Desktop\RemoteManagementSystem\dashboard
streamlit run app.py

# 7. On each managed machine — Start Agent (as Administrator)
Set-Location C:\path\to\RemoteManagementSystem\agent
python rmm_agent.py
```

---

# APPENDIX A: GLOSSARY

| Term | Definition |
|---|---|
| Agent | The Python program (`rmm_agent.py`) installed on managed Windows machines. It collects metrics and sends heartbeats to the API every 60 seconds. |
| Alert | An automatic notification generated when a device metric crosses a configured threshold. |
| Alert Rule | A configuration defining when alerts are triggered: which metric, at what threshold, with what severity. |
| API | Application Programming Interface. In this system, the Flask web server at http://localhost:5000 that handles all data operations. |
| Automation Profile | A bundle of maintenance tasks (patching, disk, cleanup) scheduled to run on a recurring basis. |
| BAT | Windows Batch file format. A simple scripting language for Windows commands. |
| Celery | A distributed task queue system. Used here to run background tasks (alert evaluation, patch deployment) asynchronously. |
| Compliance % | The percentage of managed devices that are fully patched and up to date. |
| Cooldown | The minimum time that must pass before an alert rule can fire again for the same device. Prevents alert flooding. |
| Critical | The highest alert severity level. Requires immediate action. |
| CRUD | Create, Read, Update, Delete — the four basic database operations. |
| Dashboard | The Streamlit web interface at http://localhost:8501. Also refers to the Overview page with charts. |
| Defragmentation | A disk maintenance process for HDDs that reorganizes fragmented files. Not needed or recommended for SSDs. |
| Device | A managed machine (computer, server, workstation) with the RMM agent installed. |
| Exit Code | A number returned by a script when it finishes. 0 means success; non-zero means an error occurred. |
| Flask | The Python web framework used to build the RMM API server. |
| Heartbeat | The regular check-in signal sent by the agent to the API every 60 seconds, reporting current device metrics. |
| HDD | Hard Disk Drive — a traditional spinning magnetic disk. Slower than SSDs but can benefit from defragmentation. |
| Info | The lowest alert severity level. Informational only; no immediate action needed. |
| Invoice | A billing document generated for a customer showing managed devices and the amount owed. |
| JWT | JSON Web Token — the authentication token format used by this system. Stored in session state and URL params. |
| KB | Knowledge Base article number. A unique identifier for Windows patches (e.g., KB5034441). |
| Last Seen | The timestamp of the most recent heartbeat received from a device's agent. |
| Offline | A device whose agent has not sent a heartbeat recently. May be powered off or unreachable. |
| Online | A device whose agent is actively sending heartbeats to the API. |
| Org Token | An organization-level authentication token configured in the agent's config.ini, used during device registration. |
| OS | Operating System — the software that manages a computer's hardware and software resources. |
| Patch | A software update, typically addressing a security vulnerability, bug, or performance issue. |
| PostgreSQL | The relational database system used to store all RMM data. Runs on port 5432. |
| Priority | The urgency level of a ticket: low, medium, high, or critical. |
| ps1 | PowerShell script file extension. |
| RBAC | Role-Based Access Control — access permissions determined by user role (admin, technician, viewer). |
| Redis | An in-memory data store used as the Celery message broker. Runs on port 6379. |
| RMM | Remote Monitoring and Management. A category of IT management tools. |
| Script | A file containing code (PS1, BAT, PY, or SH) that can be executed remotely on a managed device. |
| Session | An active user login. Stored in Streamlit session state and represented by a JWT token. |
| Severity | The importance level of an alert: info, warning, or critical. |
| SSD | Solid State Drive — a fast storage device with no moving parts. Does not benefit from defragmentation. |
| Streamlit | The Python web app framework used to build the RMM dashboard. |
| Technician | A user role with permissions to manage devices, tickets, scripts, and patches, but not users or billing. |
| Tier | Customer support level: standard, premium, or enterprise. |
| Timeout | The maximum time allowed for a script to run before it is forcibly terminated. |
| Token | See JWT. A cryptographic string proving a user is authenticated. |
| Viewer | A user role with read-only access to the system. Cannot make changes. |
| Warning | A medium severity alert level. Indicates degraded performance that needs attention soon. |
| Winget | Windows Package Manager — a command-line tool for installing and updating software on Windows. |

---

# APPENDIX B: QUICK REFERENCE CARDS

---

## Quick Reference Card — IT Support Staff

**Your daily routine:**
1. Open http://localhost:8501 — log in
2. Check Dashboard stat cards — note any red numbers
3. Go to Alerts — acknowledge any new alerts
4. Go to Tickets — check for open tickets
5. Respond to client calls — create tickets, investigate devices
6. Update ticket statuses throughout the day

**Creating a ticket:**
Tickets → + New Ticket → fill Title, Priority, Customer → Create Ticket

**Finding a device:**
Devices → search or scroll for hostname → click to expand → read CPU/RAM/disk

**Acknowledging an alert:**
Alerts → Active Alerts tab → expand alert → click Acknowledge

**Updating ticket status:**
Tickets → expand ticket → Status dropdown → select new status → Update Status

**Sign out when done:**
Sidebar bottom → Sign Out button

---

## Quick Reference Card — Technicians

**Run a script on multiple devices:**
Scripts → Library tab → find script → expand → select devices → set timeout → Run

**Approve OS patches:**
OS Patches → Pending Patches tab → check boxes → Approve Selected

**Reboot a device:**
Maintenance → select device → check "I confirm..." → click Reboot

**Create an alert rule:**
Alerts → Alert Rules tab → scroll to Create Alert Rule → fill form → Create Rule

**Create an automation profile:**
Automation → Create / Edit Profile tab → fill fields → configure task columns → Save Profile

**View disk health:**
Disk Management → select device → view gauges → run cleanup if needed

**Check script output:**
Scripts → Run History tab → expand run entry → read stdout/stderr

**Alert severity colors:**
- Red = critical (immediate action)
- Amber = warning (attention needed)
- Blue = info (no action needed)

**Ticket status cycle:**
open → in_progress → resolved → closed

---

## Quick Reference Card — Administrators

**Access user management:**
Admin → Users tab (requires /api/admin/users endpoint)

**View audit log:**
Admin → Audit Log tab → filter by action type and date range

**Check service health:**
Admin → System Info tab → Services card

**Create invoice:**
Billing → create invoice form → select customer, set dates, enter device count and rate

**Deactivate departed employee:**
Admin → Users tab → note email → API call or DB: `UPDATE users SET is_active = false WHERE email = '...'`

**Service ports:**
- Dashboard: http://localhost:8501
- Flask API: http://localhost:5000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

**Restart all services (PowerShell):**
```powershell
# Kill port 5000 first, then:
cd C:\...\api ; python app.py
# New terminal:
cd C:\...\api ; celery -A tasks.celery_app worker --pool=solo -l info
# New terminal:
cd C:\...\dashboard ; streamlit run app.py
```

---

## Quick Reference Card — Developers

**Dashboard entry point:** `dashboard/app.py`
**All pages:** `dashboard/pages/01_Dashboard.py` through `16_Scripts.py`
**API client:** `dashboard/utils/api_client.py`
**Auth utilities:** `dashboard/utils/auth.py`
**CSS/UI helpers:** `dashboard/utils/styles.py`
**Flask routes:** `api/routes/`
**Models:** `api/models/`
**Celery tasks:** `api/tasks/`
**Agent main loop:** `agent/rmm_agent.py`
**Metric collector:** `agent/collector.py`
**Script executor:** `agent/script_runner.py`

**Brand colors:**
- Primary: `#407E3C`
- Accent: `#5a9e56`
- White: `#FFFFFF`
- Danger: `#EF4444`
- Warning: `#F59E0B`
- Success: `#22C55E`
- Info: `#3B82F6`

**Authentication in dashboard pages:**
```python
from utils.auth import require_auth
client = require_auth()  # Returns APIClient or redirects to login
```

**API call pattern:**
```python
data, err = client.list_devices(per_page=100)
if err:
    st.error(f"API error: {err}")
else:
    devices = data.get("items", [])
```

**Agent heartbeat interval:** 60 seconds (configurable: `config.ini → [agent] → heartbeat_interval`)
**Software scan interval:** 21600 seconds / 6 hours (configurable: `config.ini → [agent] → software_interval`)

**Script exit code convention:** 0 = SUCCESS, non-zero = FAILED

**Run tests:**
```powershell
cd C:\...\api
pytest tests/ -v
```

---

*End of RMM System Handover and User Guide — Version 1.0*

*For questions about this guide, contact your system administrator or development team.*
