"""Streamlit session state auth helpers."""
import streamlit as st
from utils.api_client import RMMClient

_QP_KEY = "tok"


def _restore_from_query_params():
    """If session_state has no token but URL has ?tok=..., restore session via /api/auth/me."""
    if st.session_state.get("access_token"):
        return
    tok = st.query_params.get(_QP_KEY, "")
    if not tok:
        return
    client = RMMClient(tok)
    user, err = client.get_me()
    if err or not user:
        # Token invalid/expired — clear query param and force login
        st.query_params.clear()
        return
    st.session_state["access_token"] = tok
    st.session_state["user"] = user


def get_client() -> RMMClient | None:
    """Return RMMClient if logged in, else None."""
    _restore_from_query_params()
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
    """Attempt login, store token in session state and URL query params. Returns success."""
    data, err = RMMClient.login(email, password)
    if err:
        st.error(f"Login failed: {err}")
        return False
    st.session_state["access_token"] = data["access_token"]
    st.session_state["refresh_token"] = data.get("refresh_token")
    st.session_state["user"] = data["user"]
    # Persist token in URL so browser refresh restores session
    st.query_params[_QP_KEY] = data["access_token"]
    return True


def logout():
    for key in ["access_token", "refresh_token", "user"]:
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()


def current_user() -> dict | None:
    return st.session_state.get("user")
