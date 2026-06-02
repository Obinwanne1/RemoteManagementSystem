"""Streamlit session state auth helpers."""
import streamlit as st
from utils.api_client import RMMClient


def get_client() -> RMMClient | None:
    """Return a cached RMMClient if logged in, else None."""
    token = st.session_state.get("access_token")
    if not token:
        return None
    # Reuse existing client if token unchanged (preserves TCP connection pool)
    existing: RMMClient | None = st.session_state.get("_rmm_client")
    if existing and existing._token == token:
        return existing
    client = RMMClient(
        access_token=token,
        refresh_token=st.session_state.get("refresh_token", ""),
    )
    st.session_state["_rmm_client"] = client
    return client


def _restore_from_query_params() -> None:
    """Restore access token from ?tok= URL param then immediately clear it."""
    tok = st.query_params.get("tok", "")
    if tok and "access_token" not in st.session_state:
        st.session_state["access_token"] = tok
        st.query_params.clear()


def require_auth() -> RMMClient:
    """Halt page if not authenticated. Redirects to login. Returns client."""
    _restore_from_query_params()
    client = get_client()
    if not client:
        st.switch_page("app.py")
    return client


def login(email: str, password: str) -> bool:
    """Attempt login, store tokens in session state only. Returns success."""
    data, err = RMMClient.login(email, password)
    if err:
        st.error(f"Login failed: {err}")
        return False
    st.session_state["access_token"] = data["access_token"]
    st.session_state["refresh_token"] = data.get("refresh_token", "")
    st.session_state["user"] = data["user"]
    # Invalidate any cached client so it's rebuilt with the new token
    st.session_state.pop("_rmm_client", None)
    return True


def logout():
    for key in ["access_token", "refresh_token", "user", "_rmm_client"]:
        st.session_state.pop(key, None)
    st.rerun()


def current_user() -> dict | None:
    return st.session_state.get("user")
