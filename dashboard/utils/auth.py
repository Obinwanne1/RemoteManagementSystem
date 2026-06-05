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
    """Restore access + refresh tokens from URL params, then remove them from URL."""
    tok = st.query_params.get("tok", "")
    rtok = st.query_params.get("rtok", "")
    restored = False
    if tok:
        st.session_state["access_token"] = tok
        restored = True
    if rtok:
        st.session_state["refresh_token"] = rtok
        restored = True
    if restored:
        # Remove tokens from URL so they don't persist in browser history or server logs.
        # Session state carries the tokens from this point forward.
        st.query_params.pop("tok", None)
        st.query_params.pop("rtok", None)


def _redirect_to_login() -> None:
    """Force browser redirect to login page and stop execution."""
    st.markdown(
        '<meta http-equiv="refresh" content="0; url=/">',
        unsafe_allow_html=True,
    )
    st.stop()


def require_auth() -> RMMClient:
    """Halt page if not authenticated. Redirects to login. Returns client.

    Tokens are restored from URL params on every load (F5-safe). The URL
    params are the only cross-reload persistence in Streamlit — they must
    be kept in sync with session state so that browser reload never logs
    the user out.
    """
    _restore_from_query_params()
    client = get_client()
    if not client:
        _redirect_to_login()
    # Restore user profile if missing (e.g. after page refresh)
    if not st.session_state.get("user"):
        data, err = client.get_me()
        if err or not data:
            # Token is invalid/expired — clear and redirect
            st.session_state.pop("access_token", None)
            _redirect_to_login()
        st.session_state["user"] = data.get("user", data)
    # Re-stamp tokens to URL so F5 / browser reload restores the session.
    # Streamlit wipes session state on every full reload — URL params are
    # the only way to survive it.
    tok = st.session_state.get("access_token", "")
    rtok = st.session_state.get("refresh_token", "")
    if tok:
        st.query_params["tok"] = tok
    if rtok:
        st.query_params["rtok"] = rtok
    return client


def login(email: str, password: str) -> str:
    """Attempt login. Returns 'ok', 'mfa_required', or 'error'.

    On success tokens are stored in session state and written to URL once for
    F5 handoff. On MFA required, mfa_pending_token is stored in session state.
    require_auth() strips URL tokens after the first successful restore."""
    data, err = RMMClient.login(email, password)
    if err:
        st.error(f"Login failed: {err}")
        return "error"
    if data.get("status") == "mfa_required":
        st.session_state["mfa_pending_token"] = data["mfa_token"]
        return "mfa_required"
    st.session_state["access_token"] = data["access_token"]
    st.session_state["refresh_token"] = data.get("refresh_token", "")
    st.session_state["user"] = data["user"]
    # Write once to URL for the initial page-reload handoff only.
    # require_auth() will clear these params after the first successful restore.
    st.query_params["tok"] = data["access_token"]
    if data.get("refresh_token"):
        st.query_params["rtok"] = data["refresh_token"]
    return "ok"


def logout():
    for key in ["access_token", "refresh_token", "user"]:
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()


def current_user() -> dict | None:
    return st.session_state.get("user")
