"""AI Assistant — context-aware chat endpoint for dashboard guidance."""
import os
import re
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from extensions import db, limiter
from models.audit import AuditLog

log = logging.getLogger(__name__)

assistant_bp = Blueprint("assistant", __name__)

# ── High-risk pages: AI restricted to navigation guidance only ────────────────
_RESTRICTED_PAGES = {"Remote Terminal", "Scripts"}

# ── Patterns that flag a response as potentially destructive ──────────────────
_DANGER_PATTERNS = [
    re.compile(r'\brm\s+-rf?\b', re.IGNORECASE),
    re.compile(r'\bdrop\s+(?:table|database|schema)\b', re.IGNORECASE),
    re.compile(r'\bformat\s+[a-z]:\\', re.IGNORECASE),
    re.compile(r'--force\b', re.IGNORECASE),
    re.compile(r'\bkill\s+-9\b', re.IGNORECASE),
    re.compile(r'\bshutdown\s+(?:/s|/r|now|-h|-r)\b', re.IGNORECASE),
    re.compile(r'\btruncate\s+table\b', re.IGNORECASE),
    re.compile(r'\brd\s+/s\b', re.IGNORECASE),
    re.compile(r'\bdel\s+/[fqs]\b', re.IGNORECASE),
    re.compile(r'Remove-Item\s+-Recurse\s+-Force\b', re.IGNORECASE),
    re.compile(r'\bwipe\s+(?:disk|drive|all|data)\b', re.IGNORECASE),
]

_CODE_BLOCK_RE = re.compile(r'```[\s\S]*?```', re.MULTILINE)

# ── Page descriptions (injected into system prompt) ───────────────────────────
_PAGE_INFO = {
    "Overview": (
        "Live dashboard showing overall system health: device counts (total/online/offline/critical/warning), "
        "open alerts, open tickets, recent activity, and a device health map. "
        "This is the first page users see after login."
    ),
    "Tickets": (
        "Helpdesk ticket management. Create, view, update, and close support tickets. "
        "Filter by status (open/in-progress/resolved/closed), priority (low/medium/high/critical), "
        "and customer. Assign tickets to technicians. Add comments."
    ),
    "Customers": (
        "Customer organisation management. Add new customers, search existing ones, "
        "view associated devices and sites. Each customer can have multiple sites."
    ),
    "Devices": (
        "Device inventory for all enrolled endpoints — Windows, macOS, Linux, Android, iOS, and agentless WiFi devices. "
        "Filter by OS using tabs. Click a device row to expand: view CPU/RAM/disk metrics, last-seen time, run scripts, "
        "manage patches, edit device details, or delete the device."
    ),
    "Alerts": (
        "Active alert management. View open alerts filtered by severity (critical/warning/info). "
        "Acknowledge alerts to mark them as seen. Resolve alerts when the issue is fixed. "
        "Also configure alert rules (thresholds that trigger alerts automatically)."
    ),
    "Network Discovery": (
        "Scan the local network for devices (computers, phones, printers, routers) using ICMP ping sweep. "
        "Enter a subnet (e.g. 192.168.1.0/24) and click Scan. "
        "Discovered devices are listed with hostname, IP, MAC, and vendor. "
        "Save devices you want to track as agentless devices."
    ),
    "OS Patches": (
        "Operating system patch management. View pending Windows/macOS/Linux updates for online devices. "
        "Select a device from the dropdown, view available patches, and deploy them. "
        "Patches run via the device agent — the device must be online."
    ),
    "Software Patches": (
        "Third-party software update management. View outdated software on enrolled devices. "
        "Select a device, view software with available updates, and deploy updates via winget. "
        "Agent-managed devices only (agentless/mobile devices are excluded)."
    ),
    "Scripts": (
        "Script library for remote execution. Run built-in PowerShell scripts (disk cleanup, defrag, temp clean, etc.) "
        "or create and upload custom scripts. Select a device and click Run. View execution history and output."
    ),
    "Remote Terminal": (
        "Remote terminal sessions for direct command-line access to managed devices. "
        "SSH for Linux/macOS, RDP for Windows. Connect by selecting a device and clicking Connect. "
        "Requires the device to be online and the technician role or higher."
    ),
    "Disk Management": (
        "Disk usage analysis and cleanup for managed devices. "
        "Select a device to view disk space breakdown. Run cleanup tasks to free space. "
        "Schedule automatic cleanup for recurring maintenance."
    ),
    "Maintenance": (
        "Scheduled maintenance task management. "
        "Run or schedule tasks like disk defrag, temp file cleanup, Windows Update, and system optimisation. "
        "Tasks are dispatched to the device agent and run in the background."
    ),
    "Automation": (
        "Automation rule builder. Create rules that trigger actions automatically based on conditions "
        "(e.g. alert triggered → run script, device offline → create ticket). "
        "Enable/disable rules. View rule execution history."
    ),
    "Reports": (
        "Business reporting. Generate device health reports, patch compliance reports, ticket summary reports, "
        "and billing reports. Reports are exported as CSV. "
        "Select report type, date range, and optional customer filter, then click Generate."
    ),
    "Billing": (
        "Invoice and billing management. View monthly recurring revenue (MRR), create invoices, "
        "mark invoices as paid, add line items. Stripe integration available for online payment links. "
        "Admin and technician access required."
    ),
    "Admin Panel": (
        "System administration. Manage users (create, edit, delete, set roles, force password change). "
        "View and change organisation name, logo, and branding. "
        "Copy the agent enrollment token for deploying new agents. "
        "Manage subscription settings. Admin or superadmin access required."
    ),
    "My Profile": (
        "User account settings. Change your display name, update your password, "
        "enable or disable two-factor authentication (MFA/TOTP). "
        "View your current role and account details."
    ),
    "Client Portal": (
        "Client self-service portal. Clients can view their own tickets and submit new support requests. "
        "This view is restricted to the client role — technicians and admins use the main Tickets page."
    ),
    "Client Tickets": (
        "Client ticket view. Submit new tickets, view existing tickets, "
        "add comments, and track resolution status. Limited to the client's own tickets."
    ),
    "App Center": (
        "Installed software inventory across all managed devices. "
        "Select a device to view all software installed on it, including version numbers and publishers. "
        "Useful for auditing software compliance and identifying unauthorised installations."
    ),
}

_ROLE_CAPABILITIES = {
    "viewer": (
        "read-only access — can view the dashboard, devices, alerts, tickets, customers, and reports "
        "but CANNOT create, edit, delete, or run any actions"
    ),
    "technician": (
        "operational access — can manage devices, run scripts, deploy patches, handle tickets, "
        "acknowledge and resolve alerts, use remote terminal, view reports and billing. "
        "Cannot manage users, change org settings, or access admin functions"
    ),
    "admin": (
        "full access — all technician capabilities plus user management, org branding, "
        "billing management, enrollment token management, and all admin panel functions"
    ),
    "superadmin": (
        "full system access — all admin capabilities plus platform-level superadmin controls. "
        "The superadmin account cannot be deleted or modified by other users"
    ),
    "client": (
        "client portal access — can only view and create support tickets for their own organisation. "
        "Cannot access monitoring, devices, alerts, scripts, or admin functions"
    ),
}

# ── Suggested quick actions per page ─────────────────────────────────────────
_PAGE_ACTIONS = {
    "Overview":          ["View open alerts", "Check offline devices", "Create a ticket"],
    "Tickets":           ["Create a new ticket", "Filter by priority", "Assign a ticket"],
    "Customers":         ["Add a new customer", "Search for a customer"],
    "Devices":           ["Filter devices by OS", "Run a script on a device", "View device metrics"],
    "Alerts":            ["Acknowledge an alert", "Resolve an alert", "Create an alert rule"],
    "Network Discovery": ["Start a network scan", "Save a discovered device", "What is an agentless device?"],
    "OS Patches":        ["Deploy OS patches", "Check patch status", "What devices need updates?"],
    "Software Patches":  ["Scan a device for updates", "Deploy a software update"],
    "Scripts":           ["Run a built-in script", "Create a custom script", "View run history"],
    "Remote Terminal":   ["Connect to a device", "Difference between SSH and RDP"],
    "Disk Management":   ["Run a disk cleanup", "View disk usage", "Schedule cleanup"],
    "Maintenance":       ["Run a maintenance task now", "Schedule a recurring task"],
    "Automation":        ["Create an automation rule", "Enable or disable a rule"],
    "Reports":           ["Generate a report", "Download report as CSV"],
    "Billing":           ["Create an invoice", "Mark an invoice as paid", "Add a billing item"],
    "Admin Panel":       ["Add a new user", "Change organisation name", "Get enrollment token"],
    "My Profile":        ["Change my password", "Enable two-factor authentication"],
    "Client Tickets":   ["Submit a new ticket", "View ticket status", "Add a comment"],
    "App Center":       ["View installed software on a device", "Check software versions", "Find a specific app"],
}


def _build_system_prompt(role: str, page: str, context: dict) -> str:
    role_desc = _ROLE_CAPABILITIES.get(role, "standard platform user")
    page_desc = _PAGE_INFO.get(page, "a page in the Remote Management System")

    ctx_lines = [f"- {k}: {v}" for k, v in context.items() if k and v is not None]
    has_live_data = bool(ctx_lines) and not (len(ctx_lines) == 1 and "navigation_only" in str(ctx_lines[0]))
    ctx_text = "\n".join(ctx_lines) if ctx_lines else "No specific context data available."

    base = f"""You are the AI Assistant embedded in Remote Management System (RMS) — a professional Remote Monitoring & Management platform similar to NinjaOne and ConnectWise. Your sole job is to help users navigate and use this platform effectively.

USER ROLE: {role}
ROLE PERMISSIONS: {role_desc}

CURRENT PAGE: {page}
PAGE PURPOSE: {page_desc}

LIVE CONTEXT (current state of the page):
{ctx_text}

RESPONSE RULES:
1. Be concise and direct. 2-4 sentences for simple questions; numbered steps for how-to guides.
2. Always refer to UI elements by their exact names as the user would see them (button labels, tab names, section headings).
3. ONLY describe features that exist in this system. Never invent pages, buttons, API endpoints, or settings that aren't real.
4. Respect the user's role: if a feature requires a higher role, say so clearly (e.g. "This requires admin access").
5. For viewer roles: never suggest create, edit, delete, or run actions — guide them to what they CAN see.
6. If asked something unrelated to this RMM platform, say: "I can only help with navigating this system. For other questions, please contact your administrator."
7. Use plain language. Assume the user may be new to RMM tools — avoid jargon unless explaining it.
8. For multi-step tasks, number the steps clearly.
9. If the live context shows a problem (e.g. offline devices, critical alerts), proactively mention the most urgent action first.
10. {"If you do not see specific numbers in LIVE CONTEXT above, do NOT state or estimate any counts, percentages, or status values — say: 'I don't have live data for this page right now. I can describe the UI, but check the page directly for current values.'" if not has_live_data else "You have live context data — use it. Do not contradict it or invent additional values."}
11. Never state specific numbers (device counts, alert counts, revenue figures) unless they appear explicitly in LIVE CONTEXT.
12. For any action that modifies, deletes, or executes something, end your response with: "Verify this step before proceeding."
13. When you are uncertain about any detail, say "I'm not certain — verify with your administrator or documentation." Never present uncertain information as fact."""

    if page in _RESTRICTED_PAGES:
        base += """

RESTRICTED MODE — HIGH-RISK PAGE:
- You are in navigation-only mode. This page can execute commands on remote devices.
- NEVER suggest any commands, scripts, terminal inputs, shell syntax, or code of any kind.
- NEVER complete or continue partial commands the user pastes.
- NEVER recommend running, executing, or pasting anything in the terminal or script fields.
- If asked for a command or script, respond exactly: "I can't suggest commands on this page — consult your documentation or administrator for safe command references."
- Only answer: how to navigate the UI, what buttons/fields do, how to connect/disconnect, what permissions are needed."""

    return base


@assistant_bp.route("/chat", methods=["POST"])
@jwt_required()
@limiter.limit("30 per minute")
def chat():
    if os.getenv("AI_ASSISTANT_ENABLED", "true").lower() == "false":
        return jsonify({"error": "AI assistant is disabled for this organisation"}), 503

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "AI assistant is not configured — ANTHROPIC_API_KEY missing"}), 503

    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    page = str(body.get("page") or "Overview")[:60]
    raw_context = body.get("context") or {}
    raw_history = body.get("history") or []

    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > 1000:
        message = message[:1000]

    # Sanitise context keys/values
    safe_context = {
        str(k)[:60]: str(v)[:300]
        for k, v in raw_context.items()
        if k and v is not None and str(v).strip()
    }

    role = get_jwt().get("role", "viewer")

    system_prompt = _build_system_prompt(role, page, safe_context)

    # Build message list (cap at last 10 turns to limit token spend)
    messages = []
    for turn in raw_history[-10:]:
        r = turn.get("role", "")
        c = (turn.get("content") or "")[:600]
        if r in ("user", "assistant") and c.strip():
            messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": message})

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = os.getenv("AI_ASSISTANT_MODEL", "claude-haiku-4-5-20251001")
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            system=system_prompt,
            messages=messages,
        )
        reply = resp.content[0].text if resp.content else "I couldn't generate a response. Please try again."
    except Exception as exc:
        exc_name = type(exc).__name__
        if "AuthenticationError" in exc_name or "Authentication" in str(exc):
            return jsonify({"error": "AI service configuration error — check ANTHROPIC_API_KEY"}), 503
        if "RateLimitError" in exc_name or "rate_limit" in str(exc).lower():
            return jsonify({"error": "AI service is busy. Please try again in a moment."}), 429
        return jsonify({"error": "AI assistant temporarily unavailable"}), 503

    # ── Post-process: strip code blocks on restricted pages ───────────────────
    if page in _RESTRICTED_PAGES:
        reply = _CODE_BLOCK_RE.sub("[code removed — command suggestions are disabled on this page]", reply)

    # ── Danger pattern detection ──────────────────────────────────────────────
    contains_warning = any(p.search(reply) for p in _DANGER_PATTERNS)
    if contains_warning:
        reply = (
            "⚠️ **CAUTION:** This response references a potentially destructive operation. "
            "Do not execute without supervisor review.\n\n" + reply
        )

    # ── Audit log (fire-and-forget — never block the response) ───────────────
    try:
        user_id = get_jwt_identity()
        db.session.add(AuditLog(
            user_id=user_id,
            action="ai_assistant_chat",
            resource_type="page",
            resource_id=page[:36],
            ip_address=request.remote_addr,
            payload={"msg_len": len(message), "contains_warning": contains_warning},
        ))
        db.session.commit()
    except Exception:
        log.exception("AI assistant audit log write failed")
        try:
            db.session.rollback()
        except Exception:
            pass

    suggested = _PAGE_ACTIONS.get(page, [])
    return jsonify({"reply": reply, "suggested_actions": suggested, "contains_warning": contains_warning})
