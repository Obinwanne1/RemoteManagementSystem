"""
RMM Dashboard — Streamlit entrypoint / login page.
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

# Brand CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #2C3E2D;
    }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
    }
    .stButton > button {
        background-color: #407E3C;
        color: white;
        border: none;
        border-radius: 4px;
    }
    .stButton > button:hover {
        background-color: #5a9e56;
        color: white;
    }
    .metric-card {
        background: #f8f9fa;
        border-left: 4px solid #407E3C;
        padding: 1rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
    }
    .metric-card.critical { border-left-color: #DC3545; }
    .metric-card.warning { border-left-color: #FFC107; }
    .metric-card.offline { border-left-color: #6C757D; }
</style>
""", unsafe_allow_html=True)


def show_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 2rem 0 1rem">
            <h1 style="color:#407E3C; font-size:2.5rem">🖥️ RMM System</h1>
            <p style="color:#666">Remote Monitoring & Management</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email", placeholder="admin@company.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            from utils.auth import login
            if login(email, password):
                st.success("Logged in!")
                st.rerun()


def show_dashboard_home():
    from utils.auth import current_user, logout, require_auth
    from utils.formatters import fmt_datetime

    client = require_auth()
    user = current_user()

    # Sidebar
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:1rem 0; border-bottom:1px solid #4a6741; margin-bottom:1rem">
            <div style="color:#A8D5A2; font-size:0.8em">SIGNED IN AS</div>
            <div style="color:white; font-weight:bold">{user.get('full_name', user.get('email'))}</div>
            <div style="color:#A8D5A2; font-size:0.8em">{user.get('role', '').upper()}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Navigation**")
        st.page_link("app.py", label="📊 Dashboard", icon=None)
        st.page_link("pages/01_Dashboard.py", label="📊 Overview")
        st.page_link("pages/02_Tickets.py", label="🎫 Tickets")
        st.page_link("pages/03_Customers.py", label="🏢 Customers")
        st.page_link("pages/04_Devices.py", label="💻 Devices")
        st.page_link("pages/05_Alerts.py", label="🔔 Alerts")
        st.page_link("pages/11_Automation.py", label="⚙️ Automation")
        st.page_link("pages/12_OS_Patches.py", label="🔧 OS Patches")
        st.page_link("pages/13_Software_Patches.py", label="📦 Software Patches")
        st.page_link("pages/14_Disk_Management.py", label="💾 Disk Management")
        st.page_link("pages/15_Maintenance.py", label="🔨 Maintenance")
        st.page_link("pages/16_Scripts.py", label="📝 Scripts")
        st.page_link("pages/07_Network_Discovery.py", label="🌐 Network Discovery")
        st.page_link("pages/08_Reports.py", label="📈 Reports")
        st.page_link("pages/09_Billing.py", label="💰 Billing")
        st.page_link("pages/10_Admin.py", label="👤 Admin")

        st.markdown("---")
        if st.button("Sign Out", use_container_width=True):
            logout()

    # Main content: redirect to overview
    st.title("RMM System")
    st.info("Use the sidebar or navigate to Overview to see your dashboard.")

    # Quick summary tiles
    data, err = client.get_summary()
    if err:
        st.error(f"Could not load summary: {err}")
        return

    if data:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Devices", data["devices"]["total"])
        with col2:
            st.metric("Online", data["devices"]["online"],
                      delta=f"-{data['devices']['offline']} offline")
        with col3:
            st.metric("Open Alerts", data["alerts"]["open"])
        with col4:
            st.metric("Open Tickets", data["tickets"]["open"])


# Route based on auth state
if "access_token" not in st.session_state:
    show_login()
else:
    show_dashboard_home()
