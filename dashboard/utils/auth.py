"""Streamlit session state auth helpers."""
import streamlit as st
from utils.api_client import RMMClient


def get_client() -> RMMClient | None:
    """Return RMMClient if logged in, else None."""
    token = st.session_state.get("access_token")
    if not token:
        return None
    return RMMClient(token)


def require_auth():
    """Redirect to login if not authenticated. Returns client."""
    client = get_client()
    if not client:
        st.error("Not logged in. Please return to the main page.")
        st.stop()
    return client


def login(email: str, password: str) -> bool:
    """Attempt login, store token in session state. Returns success."""
    data, err = RMMClient.login(email, password)
    if err:
        st.error(f"Login failed: {err}")
        return False
    st.session_state["access_token"] = data["access_token"]
    st.session_state["refresh_token"] = data.get("refresh_token")
    st.session_state["user"] = data["user"]
    return True


def logout():
    for key in ["access_token", "refresh_token", "user"]:
        st.session_state.pop(key, None)
    st.rerun()


def current_user() -> dict | None:
    return st.session_state.get("user")
