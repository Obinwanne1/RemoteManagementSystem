import os
import streamlit as st
from utils.styles import inject_css, badge, BRAND, STATUS_COLORS
from utils.formatters import fmt_datetime
from utils.auth import require_auth, current_user

st.set_page_config(page_title="Admin — RMM", layout="wide")
inject_css()

client = require_auth()
user = current_user() or {}

# ── Role guard ─────────────────────────────────────────────────────────────────
if user.get("role") != "admin":
    st.error("Admin access required. This page is restricted to admin users.")
    st.stop()

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown('<h1 style="margin:0">Admin</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">System administration and audit</p>', unsafe_allow_html=True)

CARD = (
    "background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;"
    "border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem"
)

ACTION_COLORS = {
    "CREATE": "#22C55E",
    "UPDATE": "#3B82F6",
    "DELETE": "#EF4444",
    "LOGIN":  "#8B5CF6",
    "LOGOUT": "#F59E0B",
}

API_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
DASH_URL = "http://localhost:8501"

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_sysinfo, tab_audit, tab_users = st.tabs(["System Info", "Audit Log", "Users"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — System Info
# ═══════════════════════════════════════════════════════════════════════════════
with tab_sysinfo:
    st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

    col_user, col_system, col_services = st.columns(3)

    with col_user:
        st.markdown(
            f'<div style="{CARD}">'
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.75rem">Current User</div>'
            f'<div style="font-size:1.1rem;font-weight:700;color:#1A1A1A;margin-bottom:0.25rem">{user.get("full_name") or user.get("email","—")}</div>'
            f'<div style="margin-bottom:0.5rem">'
            + badge(user.get("role","unknown"), "#407E3C")
            + f'</div>'
            f'<div style="display:flex;gap:6px;margin-bottom:0.3rem"><span style="font-size:0.8rem;color:#6B7B6B;min-width:48px">Email</span><span style="font-size:0.8rem;color:#1A1A1A">{user.get("email","—")}</span></div>'
            f'<div style="display:flex;gap:6px"><span style="font-size:0.8rem;color:#6B7B6B;min-width:48px">Role</span><span style="font-size:0.8rem;color:#1A1A1A;text-transform:capitalize">{user.get("role","—")}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_system:
        st.markdown(
            f'<div style="{CARD}">'
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.75rem">System</div>'
            f'<div style="display:flex;gap:6px;margin-bottom:0.5rem"><span style="font-size:0.8rem;color:#6B7B6B;min-width:72px">API URL</span>'
            f'<span style="font-size:0.8rem;color:#407E3C;font-family:monospace;word-break:break-all">{API_URL}</span></div>'
            f'<div style="display:flex;gap:6px;margin-bottom:0.5rem"><span style="font-size:0.8rem;color:#6B7B6B;min-width:72px">Dashboard</span>'
            f'<span style="font-size:0.8rem;color:#407E3C;font-family:monospace;word-break:break-all">{DASH_URL}</span></div>'
            f'<div style="display:flex;gap:6px"><span style="font-size:0.8rem;color:#6B7B6B;min-width:72px">DB</span>'
            f'<span style="font-size:0.8rem;color:#1A1A1A;font-family:monospace">localhost:5432 / rmmdb</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_services:
        # Probe API health
        health_data, health_err = client._get("/api/health") if hasattr(client, "_get") else (None, "n/a")
        api_ok = health_err is None and health_data is not None
        api_dot = "#22C55E" if api_ok else "#EF4444"
        api_label = "Online" if api_ok else "Unreachable"

        st.markdown(
            f'<div style="{CARD}">'
            f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.75rem">Services</div>'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.55rem">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:{api_dot};flex-shrink:0"></div>'
            f'<span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">Flask API</span>'
            f'<span style="font-size:0.75rem;color:{api_dot};margin-left:auto">{api_label}</span></div>'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.55rem">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:#22C55E;flex-shrink:0"></div>'
            f'<span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">Streamlit Dashboard</span>'
            f'<span style="font-size:0.75rem;color:#22C55E;margin-left:auto">Running</span></div>'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.55rem">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:#F59E0B;flex-shrink:0"></div>'
            f'<span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">PostgreSQL</span>'
            f'<span style="font-size:0.75rem;color:#F59E0B;margin-left:auto">localhost:5432</span></div>'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:#F59E0B;flex-shrink:0"></div>'
            f'<span style="font-size:0.82rem;color:#1A1A1A;font-weight:500">Redis / Celery</span>'
            f'<span style="font-size:0.75rem;color:#F59E0B;margin-left:auto">localhost:6379</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Audit Log
# ═══════════════════════════════════════════════════════════════════════════════
with tab_audit:
    st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

    # ── Filters ──
    f1, f2, f3 = st.columns([2, 2, 3])
    with f1:
        action_filter = st.selectbox(
            "Action type",
            ["All", "CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT"],
            label_visibility="visible",
        )
    with f2:
        date_from = st.date_input("From date", value=None, label_visibility="visible")
    with f3:
        date_to = st.date_input("To date", value=None, label_visibility="visible")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    feed, ferr = client.get_activity_feed()
    if ferr:
        st.error(f"API error: {ferr}")
    elif not feed:
        st.markdown(
            f'<div style="{CARD};text-align:center;padding:2.5rem 1.5rem">'
            f'<div style="font-size:1.8rem;margin-bottom:0.5rem">&#128221;</div>'
            f'<div style="font-size:0.95rem;font-weight:600;color:#1A1A1A">No audit events yet</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        # Apply filters client-side
        items = feed if isinstance(feed, list) else feed.get("items", [])

        if action_filter != "All":
            items = [i for i in items if (i.get("action") or "").upper() == action_filter]
        if date_from:
            items = [i for i in items if i.get("created_at", "") >= str(date_from)]
        if date_to:
            items = [i for i in items if i.get("created_at", "") <= str(date_to) + "T23:59:59"]

        st.markdown(
            f'<div style="font-size:0.8rem;color:#6B7B6B;margin-bottom:0.6rem"><b>{len(items)}</b> events</div>',
            unsafe_allow_html=True,
        )

        # ── Render as HTML table for performance ──
        rows_html = ""
        for item in items:
            action = (item.get("action") or "—").upper()
            resource_type = item.get("resource_type") or "—"
            resource_id = item.get("resource_id") or ""
            ts = fmt_datetime(item.get("created_at", ""))
            ip = item.get("ip_address") or "—"
            email = item.get("user_email") or "—"
            color = ACTION_COLORS.get(action, "#6B7B6B")
            resource_display = f"{resource_type}:{resource_id}" if resource_id else resource_type
            rows_html = (rows_html
                + f'<tr>'
                + f'<td style="padding:0.5rem 0.75rem;white-space:nowrap"><span style="background:{color}1A;color:{color};padding:2px 9px;border-radius:5px;font-size:0.7rem;font-weight:700;border:1px solid {color}33">{action}</span></td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.82rem;color:#1A1A1A;font-weight:500">{resource_display}</td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.78rem;color:#6B7B6B;white-space:nowrap">{ts}</td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.78rem;color:#6B7B6B;font-family:monospace">{ip}</td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.78rem;color:#6B7B6B">{email}</td>'
                + f'</tr>'
            )

        table_html = (
            f'<div style="{CARD};padding:0;overflow:hidden">'
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="border-bottom:1px solid #DDE8DD;background:#FAFCFA">'
            f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;white-space:nowrap">Action</th>'
            f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">Resource</th>'
            f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;white-space:nowrap">Timestamp</th>'
            f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">IP Address</th>'
            f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">User</th>'
            f'</tr></thead>'
            f'<tbody>'
            + rows_html
            + f'</tbody></table></div>'
        )

        st.markdown(table_html, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Users
# ═══════════════════════════════════════════════════════════════════════════════
with tab_users:
    st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

    users_data, users_err = client._get("/api/admin/users")

    if users_err:
        st.markdown(
            f'<div style="{CARD};border-left:3px solid #F59E0B">'
            f'<div style="font-size:0.85rem;font-weight:600;color:#1A1A1A;margin-bottom:0.25rem">No user management API yet</div>'
            f'<div style="font-size:0.8rem;color:#6B7B6B">The <code style="background:#F4F6F4;padding:1px 5px;border-radius:3px">/api/admin/users</code> endpoint is not available. Implement it in the Flask API to enable user management here.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        user_list = users_data if isinstance(users_data, list) else users_data.get("items", users_data.get("users", []))

        if not user_list:
            st.markdown(
                f'<div style="{CARD};text-align:center;padding:2rem">'
                f'<div style="font-size:0.95rem;color:#6B7B6B">No users returned by API.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:0.8rem;color:#6B7B6B;margin-bottom:0.6rem"><b>{len(user_list)}</b> users</div>',
                unsafe_allow_html=True,
            )

            rows_html = ""
            for u in user_list:
                role = (u.get("role") or "user").lower()
                role_color = "#407E3C" if role == "admin" else "#3B82F6" if role == "manager" else "#6B7B6B"
                created = fmt_datetime(u.get("created_at", ""))
                rows_html = (rows_html
                    + f'<tr style="border-bottom:1px solid #EEF2EE">'
                    + f'<td style="padding:0.55rem 0.75rem;font-size:0.82rem;color:#1A1A1A;font-weight:500">{u.get("full_name") or "—"}</td>'
                    + f'<td style="padding:0.55rem 0.75rem;font-size:0.82rem;color:#1A1A1A">{u.get("email","—")}</td>'
                    + f'<td style="padding:0.55rem 0.75rem"><span style="background:{role_color}1A;color:{role_color};padding:2px 9px;border-radius:5px;font-size:0.7rem;font-weight:700;border:1px solid {role_color}33">{role.upper()}</span></td>'
                    + f'<td style="padding:0.55rem 0.75rem;font-size:0.78rem;color:#6B7B6B;white-space:nowrap">{created}</td>'
                    + f'</tr>'
                )

            table_html = (
                f'<div style="{CARD};padding:0;overflow:hidden">'
                f'<table style="width:100%;border-collapse:collapse">'
                f'<thead><tr style="border-bottom:1px solid #DDE8DD;background:#FAFCFA">'
                f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">Name</th>'
                f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">Email</th>'
                f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">Role</th>'
                f'<th style="padding:0.6rem 0.75rem;text-align:left;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;white-space:nowrap">Created</th>'
                f'</tr></thead>'
                f'<tbody>' + rows_html + f'</tbody></table></div>'
            )

            st.markdown(table_html, unsafe_allow_html=True)
