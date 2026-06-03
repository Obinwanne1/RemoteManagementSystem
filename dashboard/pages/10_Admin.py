import os
import streamlit as st
from utils.styles import inject_css, badge, BRAND, STATUS_COLORS
from utils.formatters import fmt_datetime
from utils.auth import require_auth, current_user
from utils.nav import render_sidebar

st.set_page_config(page_title="Admin — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()
user = current_user() or {}

# ── Role guard ─────────────────────────────────────────────────────────────────
if user.get("role") != "admin":
    st.error("Admin access required. This page is restricted to admin users.")
    from utils.auth import logout
    if st.button("Sign Out / Switch Account", type="primary"):
        logout()
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

    # ── Agent Enrollment Token ────────────────────────────────────────────────
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    org_data, org_err = client.get_org_token()
    org_token_val = org_data.get("org_token", "") if org_data else ""

    masked = org_token_val[:6] + "•" * (len(org_token_val) - 6) if len(org_token_val) > 6 else "••••••••"
    show_key = "admin_show_org_token"
    if show_key not in st.session_state:
        st.session_state[show_key] = False

    st.markdown(
        f'<div style="{CARD}">'
        f'<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:#6B7B6B;margin-bottom:0.75rem">Agent Enrollment Token</div>'
        f'<div style="font-size:0.8rem;color:#4B5B4B;margin-bottom:0.75rem">'
        f'Paste this token into <code>config.ini → org_token</code> on any machine you want to enroll. '
        f'Keep it secret — anyone with this token can register devices to your org.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if org_err:
        st.warning(f"Could not load org token: {org_err}")
    elif org_token_val:
        tok_col, btn_col, copy_col = st.columns([6, 1, 1])
        with tok_col:
            display_val = org_token_val if st.session_state[show_key] else masked
            st.code(display_val, language=None)
        with btn_col:
            label = "Hide" if st.session_state[show_key] else "Reveal"
            if st.button(label, key="toggle_org_token", use_container_width=True):
                st.session_state[show_key] = not st.session_state[show_key]
                st.rerun()
        with copy_col:
            st.button("Copy", key="copy_org_token", use_container_width=True,
                      help="Click Reveal first, then copy from the code block above.")

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
            user_email     = item.get("user_email") or ""
            user_full_name = item.get("user_full_name") or ""
            # Build user cell: "Full Name\nemail" or just email/dash
            if user_full_name and user_full_name != "—":
                user_cell = (
                    f'<span style="font-weight:600;color:#1A1A1A">{user_full_name}</span>'
                    f'<br><span style="color:#6B7B6B;font-size:0.73rem">{user_email}</span>'
                )
            elif user_email and user_email != "—":
                user_cell = f'<span style="color:#1A1A1A">{user_email}</span>'
            else:
                user_cell = '<span style="color:#6B7B6B">—</span>'
            color = ACTION_COLORS.get(action, "#6B7B6B")
            resource_display = f"{resource_type}:{resource_id}" if resource_id else resource_type
            rows_html = (rows_html
                + f'<tr>'
                + f'<td style="padding:0.5rem 0.75rem;white-space:nowrap"><span style="background:{color}1A;color:{color};padding:2px 9px;border-radius:5px;font-size:0.7rem;font-weight:700;border:1px solid {color}33">{action}</span></td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.82rem;color:#1A1A1A;font-weight:500">{resource_display}</td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.78rem;color:#6B7B6B;white-space:nowrap">{ts}</td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.78rem;color:#6B7B6B;font-family:monospace">{ip}</td>'
                + f'<td style="padding:0.5rem 0.75rem;font-size:0.82rem;line-height:1.4">{user_cell}</td>'
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

    ROLE_COLORS = {
        "admin": "#407E3C",
        "technician": "#3B82F6",
        "viewer": "#6B7B6B",
    }

    # ── Create user form ──────────────────────────────────────────────────────
    with st.expander("+ Create New User", expanded=False):
        with st.form("create_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_name  = st.text_input("Full Name")
                new_email = st.text_input("Email")
            with c2:
                new_role  = st.selectbox("Role", ["technician", "viewer", "admin"])
                new_pass  = st.text_input("Password", type="password", help="Min 8 characters")
            submitted = st.form_submit_button("Create User", use_container_width=True)
            if submitted:
                if not new_name or not new_email or not new_pass:
                    st.error("Name, email, and password are required.")
                else:
                    _, cerr = client.create_user({
                        "full_name": new_name,
                        "email": new_email,
                        "role": new_role,
                        "password": new_pass,
                    })
                    if cerr:
                        st.error(f"Failed: {cerr}")
                    else:
                        st.success(f"User {new_email} created.")
                        st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── User list ─────────────────────────────────────────────────────────────
    users_data, users_err = client.list_users()
    if users_err:
        st.warning(f"Could not load users — {users_err}")
    else:
        user_list = users_data.get("users", []) if isinstance(users_data, dict) else users_data

        st.markdown(
            f'<div style="font-size:0.8rem;color:#6B7B6B;margin-bottom:0.6rem"><b>{len(user_list)}</b> user(s)</div>',
            unsafe_allow_html=True,
        )

        current_uid = user.get("id", "")

        for u in user_list:
            uid   = u.get("id", "")
            uname = u.get("full_name") or "—"
            uemail = u.get("email", "—")
            urole = (u.get("role") or "viewer").lower()
            uactive = u.get("is_active", True)
            rc = ROLE_COLORS.get(urole, "#6B7B6B")
            created = fmt_datetime(u.get("created_at", ""))
            is_self = uid == current_uid

            with st.container():
                col_info, col_actions = st.columns([4, 2])
                with col_info:
                    st.markdown(
                        f'<div style="background:#FFFFFF;border:1px solid #DDE8DD;border-radius:10px;'
                        f'padding:0.75rem 1rem;margin-bottom:0.5rem">'
                        f'<div style="display:flex;align-items:center;gap:10px">'
                        f'<div style="font-weight:600;color:#1A1A1A;font-size:0.88rem">{uname}</div>'
                        f'<span style="background:{rc}1A;color:{rc};padding:2px 8px;border-radius:5px;font-size:0.68rem;font-weight:700;border:1px solid {rc}33">{urole.upper()}</span>'
                        + ('' if uactive else '<span style="background:#EF444415;color:#EF4444;padding:2px 8px;border-radius:5px;font-size:0.68rem;font-weight:700;border:1px solid #EF444433;margin-left:4px">INACTIVE</span>')
                        + f'</div>'
                        f'<div style="font-size:0.78rem;color:#6B7B6B;margin-top:2px">{uemail} · Created {created}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_actions:
                    ea, da = st.columns(2)
                    with ea:
                        if st.button("Edit", key=f"edit_btn_{uid}", use_container_width=True):
                            st.session_state[f"edit_open_{uid}"] = not st.session_state.get(f"edit_open_{uid}", False)
                    with da:
                        if not is_self:
                            if st.button("Delete", key=f"del_btn_{uid}", use_container_width=True, type="primary"):
                                st.session_state[f"del_confirm_{uid}"] = True

                # Delete confirmation
                if st.session_state.get(f"del_confirm_{uid}"):
                    st.warning(f"Delete **{uname}** ({uemail})? This cannot be undone.")
                    cy, cn = st.columns(2)
                    with cy:
                        if st.button("Yes, delete", key=f"del_yes_{uid}", use_container_width=True):
                            _, derr = client.delete_user(uid)
                            if derr:
                                st.error(f"Failed: {derr}")
                            else:
                                st.success("User deleted.")
                                st.session_state.pop(f"del_confirm_{uid}", None)
                                st.rerun()
                    with cn:
                        if st.button("Cancel", key=f"del_no_{uid}", use_container_width=True):
                            st.session_state.pop(f"del_confirm_{uid}", None)
                            st.rerun()

                # Edit form
                if st.session_state.get(f"edit_open_{uid}"):
                    with st.form(f"edit_user_{uid}"):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_name = st.text_input("Full Name", value=uname)
                            e_role = st.selectbox("Role", ["technician", "viewer", "admin"],
                                                  index=["technician","viewer","admin"].index(urole) if urole in ["technician","viewer","admin"] else 0)
                        with ec2:
                            e_active = st.checkbox("Active", value=uactive)
                            e_pass   = st.text_input("New Password (leave blank to keep)", type="password")
                        save = st.form_submit_button("Save Changes", use_container_width=True)
                        if save:
                            payload = {"full_name": e_name, "role": e_role, "is_active": e_active}
                            if e_pass:
                                payload["password"] = e_pass
                            _, uerr = client.update_user(uid, payload)
                            if uerr:
                                st.error(f"Failed: {uerr}")
                            else:
                                st.success("User updated.")
                                st.session_state.pop(f"edit_open_{uid}", None)
                                st.rerun()
