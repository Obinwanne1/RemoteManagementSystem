"""Streamlit session state auth helpers."""
import streamlit as st
from utils.api_client import RMMClient


def get_client() -> RMMClient | None:
    """Return a fresh RMMClient if logged in, else None."""
    token = st.session_state.get("access_token")
    if not token:
        return None
    return RMMClient(
        access_token=token,
        refresh_token=st.session_state.get("refresh_token", ""),
    )


def _restore_from_query_params() -> None:
    """Restore access token from ?tok= URL param. Keeps param for refresh persistence."""
    tok = st.query_params.get("tok", "")
    if tok:
        st.session_state["access_token"] = tok


def _redirect_to_login() -> None:
    """Force browser redirect to login page and stop execution."""
    st.markdown(
        '<meta http-equiv="refresh" content="0; url=/">',
        unsafe_allow_html=True,
    )
    st.stop()


def require_auth() -> RMMClient:
    """Halt page if not authenticated. Redirects to login. Returns client."""
    _restore_from_query_params()
    client = get_client()
    if not client:
        _redirect_to_login()
    # Re-stamp token into URL on every authenticated page load so F5 reload
    # always has ?tok= available regardless of which page the user is on.
    token = st.session_state.get("access_token", "")
    if token and st.query_params.get("tok", "") != token:
        st.query_params["tok"] = token
    # Restore user profile if missing (e.g. after page refresh)
    if not st.session_state.get("user"):
        data, err = client.get_me()
        if err or not data:
            # Token is invalid/expired — clear and redirect
            st.session_state.pop("access_token", None)
            st.query_params.clear()
            _redirect_to_login()
        st.session_state["user"] = data.get("user", data)
    return client


def login(email: str, password: str) -> bool:
    """Attempt login, store tokens in session state and URL param. Returns success."""
    data, err = RMMClient.login(email, password)
    if err:
        st.error(f"Login failed: {err}")
        return False
    st.session_state["access_token"] = data["access_token"]
    st.session_state["refresh_token"] = data.get("refresh_token", "")
    st.session_state["user"] = data["user"]
    # Persist token in URL so page refresh restores session
    st.query_params["tok"] = data["access_token"]
    return True


def logout():
    for key in ["access_token", "refresh_token", "user"]:
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()


def current_user() -> dict | None:
    return st.session_state.get("user")
