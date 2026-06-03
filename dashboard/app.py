"""
RMM Dashboard — Streamlit entrypoint & login page.
"""
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="RMM System",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.styles import inject_css, stat_card, BRAND

inject_css()

# ── Login ─────────────────────────────────────────────────────────────────────
_LOGIN_CSS = """
<style>
/* Dark page background — targets the whole app shell */
.stApp {
    background: linear-gradient(160deg, #0A1409 0%, #0F1B10 60%, #0c1a0d 100%) !important;
}
/* Login card */
.login-card {
    background: #152416;
    border: 1px solid #1E3A20;
    border-radius: 16px;
    padding: 2.25rem 2.25rem 1.75rem;
    box-shadow: 0 24px 64px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04);
}
/* Form labels white */
.login-card label {
    color: #7EA87E !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}
/* Form inputs dark */
.login-card input {
    background: rgba(255,255,255,0.04) !important;
    border: 1.5px solid #1E3A20 !important;
    color: #E0F0E0 !important;
    border-radius: 8px !important;
}
.login-card input:focus {
    border-color: #407E3C !important;
    box-shadow: 0 0 0 3px rgba(64,126,60,0.18) !important;
}
.login-card input::placeholder { color: #2A4A2A !important; }
/* Submit button */
.login-card .stButton > button {
    background: linear-gradient(135deg, #2D5C29, #407E3C) !important;
    color: #FFFFFF !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    padding: 0.6rem 1rem !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 14px rgba(64,126,60,0.4) !important;
    border: none !important;
    margin-top: 0.25rem;
}
.login-card .stButton > button:hover {
    background: linear-gradient(135deg, #356630, #4E9848) !important;
    box-shadow: 0 6px 20px rgba(64,126,60,0.5) !important;
}
</style>
"""


def show_login():
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)

        # Logo + brand
        st.markdown("""
        <div style="text-align:center;margin-bottom:2rem">
            <div style="display:inline-flex;align-items:center;justify-content:center;
                        width:68px;height:68px;margin-bottom:1rem;
                        background:linear-gradient(135deg,#1A3C18,#2D5C29);
                        border-radius:18px;font-size:2rem;
                        box-shadow:0 8px 24px rgba(64,126,60,0.4)">
                🖥️
            </div>
            <h1 style="font-size:1.85rem;font-weight:800;color:#FFFFFF;margin:0;
                       letter-spacing:-0.02em;text-shadow:0 2px 8px rgba(0,0,0,0.4)">
                RMM System
            </h1>
            <p style="color:#3A6A3A;font-size:0.88rem;margin:6px 0 0">
                Remote Monitoring &amp; Management
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Card wrapper — single markdown block containing only styling div
        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        with st.form("login_form"):
            email    = st.text_input("Email address", placeholder="admin@company.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center;margin-top:1.25rem;color:#1E3A1E;font-size:0.75rem">
            RMM System v1.0 · Authorized access only
        </div>
        """, unsafe_allow_html=True)

    if submitted:
        if not email or not password:
            st.error("Enter email and password.")
        else:
            from utils.auth import login
            with st.spinner("Authenticating…"):
                if not login(email, password):
                    st.error("Invalid credentials.")


# ── Home (post-login) ─────────────────────────────────────────────────────────
def show_dashboard_home():
    from utils.auth import current_user, logout, require_auth

    client = require_auth()
    user   = current_user()

    with st.sidebar:
        _role_pill = {
            "admin":      ("#EF4444", "#EF444415"),
            "technician": ("#F59E0B", "#F59E0B15"),
            "viewer":     ("#22C55E", "#22C55E15"),
        }
        rc, rb = _role_pill.get(user.get("role", "viewer"), ("#8492A6", "#8492A615"))
        name   = user.get("full_name") or user.get("email", "User")
        avatar = name[0].upper()

        st.markdown(f"""
        <div style="padding:1.1rem 1rem 0.9rem;border-bottom:1px solid #1A2E1A;margin-bottom:0.5rem">
            <div style="display:flex;align-items:center;gap:10px">
                <div style="width:38px;height:38px;border-radius:50%;flex-shrink:0;
                            background:linear-gradient(135deg,#2D5C29,#5DB85A);
                            display:flex;align-items:center;justify-content:center;
                            color:#FFF;font-weight:700;font-size:0.9rem;
                            box-shadow:0 2px 8px rgba(64,126,60,0.4)">{avatar}</div>
                <div style="min-width:0">
                    <div style="color:#E0F0E0;font-weight:600;font-size:0.86rem;
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
                        {name}</div>
                    <span style="background:{rb};color:{rc};padding:2px 8px;border-radius:20px;
                                 font-size:0.65rem;font-weight:700;display:inline-block;margin-top:2px">
                        {user.get('role','').upper()}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        def nav_section(label: str, first: bool = False):
            divider = (
                "" if first else
                '<div style="border-top:1px solid #1E3320;margin:0.35rem 0.5rem 0"></div>'
            )
            st.markdown(
                f'{divider}'
                f'<div style="display:flex;align-items:center;gap:7px;padding:0.75rem 0.75rem 0.2rem">'
                f'<div style="width:3px;height:13px;background:#407E3C;border-radius:2px;flex-shrink:0"></div>'
                f'<span style="color:#7EC87E;font-size:0.68rem;font-weight:700;letter-spacing:0.1em">{label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        role = user.get("role", "")

        if role == "admin":
            if st.button("🔧  Admin Panel", use_container_width=True, key="nav_admin"):
                st.switch_page("pages/10_Admin.py")
            st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

        nav_section("MONITORING", first=True)
        st.page_link("pages/01_Dashboard.py",         label="Overview",          icon="📊")
        st.page_link("pages/04_Devices.py",           label="Devices",           icon="💻")
        st.page_link("pages/05_Alerts.py",            label="Alerts",            icon="🔔")

        nav_section("MANAGEMENT")
        st.page_link("pages/02_Tickets.py",           label="Tickets",           icon="🎫")
        st.page_link("pages/03_Customers.py",         label="Customers",         icon="🏢")
        st.page_link("pages/11_Automation.py",        label="Automation",        icon="⚙️")

        nav_section("PATCHING")
        st.page_link("pages/12_OS_Patches.py",        label="OS Patches",        icon="🔧")
        st.page_link("pages/13_Software_Patches.py",  label="Software Patches",  icon="📦")

        nav_section("TOOLS")
        st.page_link("pages/16_Scripts.py",           label="Scripts",           icon="📝")
        st.page_link("pages/14_Disk_Management.py",   label="Disk Management",   icon="💾")
        st.page_link("pages/15_Maintenance.py",       label="Maintenance",       icon="🔨")
        st.page_link("pages/07_Network_Discovery.py", label="Network Discovery", icon="🌐")

        if role in ("admin", "technician"):
            nav_section("BUSINESS")
            st.page_link("pages/08_Reports.py",       label="Reports",           icon="📈")
            st.page_link("pages/09_Billing.py",       label="Billing",           icon="💰")

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("⎋  Sign Out", use_container_width=True, key="home_signout"):
            logout()

    # Main
    st.markdown("""
    <h1 style="margin:0">RMM Dashboard</h1>
    <p style="color:#6B7B6B;margin:2px 0 0;font-size:0.88rem">System overview — live data</p>
    """, unsafe_allow_html=True)
    st.divider()

    data, err = client.get_summary()
    if err:
        st.error(f"Could not load summary: {err}")
        return

    if not data:
        st.info("No data yet. Start the agent to register devices.")
        return

    d = data["devices"]
    a = data["alerts"]
    t = data["tickets"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(stat_card("Total Devices", d["total"], icon="💻"), unsafe_allow_html=True)
    with c2:
        offline = d.get("offline", 0)
        st.markdown(stat_card("Online", d["online"],
                               f"{offline} offline" if offline else "all online",
                               BRAND["success"], "🟢"), unsafe_allow_html=True)
    with c3:
        crit = d.get("critical", 0)
        st.markdown(stat_card("Critical", crit,
                               "needs attention" if crit else "all clear",
                               BRAND["danger"] if crit else BRAND["success"],
                               "🔴" if crit else "✅"), unsafe_allow_html=True)
    with c4:
        open_a = a["open"]
        st.markdown(stat_card("Open Alerts", open_a,
                               f"{a.get('critical',0)} critical" if open_a else "none active",
                               BRAND["warning"] if open_a else BRAND["success"],
                               "🔔"), unsafe_allow_html=True)
    with c5:
        st.markdown(stat_card("Open Tickets", t["open"], icon="🎫"), unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:1.5rem;padding:0.9rem 1.1rem;background:#F0F7F0;
                border-radius:10px;border:1px solid #DDE8DD;color:#2D5C29;font-size:0.87rem">
        📌 Use the sidebar to navigate. Go to <b>Overview</b> for live charts and device health.
    </div>
    """, unsafe_allow_html=True)


# ── Route ─────────────────────────────────────────────────────────────────────
if "access_token" not in st.session_state:
    show_login()
else:
    show_dashboard_home()
