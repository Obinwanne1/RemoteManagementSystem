"""Client Portal — entry point. Redirects client users to their ticket page."""
import streamlit as st
from utils.auth import require_auth

st.set_page_config(page_title="Client Portal — RMM", layout="centered")

client = require_auth()
me = st.session_state.get("user", {})
role = me.get("role", "")

# Staff landing here by accident — send them to the main dashboard
if role not in ("client",):
    st.switch_page("pages/21_Client_Tickets.py")

st.switch_page("pages/21_Client_Tickets.py")
