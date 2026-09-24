"""Streamlit session state auth helpers."""
import streamlit as st
from utils.api_client import RMMClient
from utils.session_store import create_session, get_session, delete_session


def get_client() -> RMMClient | None:
    """Return this session's RMMClient (reused across reruns so its
    requests.Session/connection pool isn't rebuilt on every Streamlit rerun),
    or None if not logged in.

    Reuse is only valid while the cached client's access token still matches
    session_state's — RMMClient._try_refresh() keeps both in lockstep on a
    401 auto-refresh, so this comparison also catches token rotation without
    ever serving a stale client.
    """
    token = st.session_state.get("access_token")
    if not token:
        return None
    cached: RMMClient | None = st.session_state.get("_rmm_client")
    if cached is not None and cached._token == token:
        return cached
    client = RMMClient(
        access_token=token,
        refresh_token=st.session_state.get("refresh_token", ""),
    )
    st.session_state["_rmm_client"] = client
    return client


def establish_session(access_token: str, refresh_token: str = "") -> None:
    """Store tokens in session_state and the server-side session store, then
    stamp only an opaque session id — never the raw tokens — into the URL.

    Call this everywhere a login flow (password, MFA) obtains fresh tokens.
    """
    st.session_state["access_token"] = access_token
    st.session_state["refresh_token"] = refresh_token
    sid = create_session(access_token, refresh_token)
    if sid:
        st.session_state["_dash_session_id"] = sid
        st.query_params["sid"] = sid
        st.query_params.pop("tok", None)
        st.query_params.pop("rtok", None)
    else:
        # Redis unavailable — fall back to the old, less-safe URL scheme
        # rather than breaking login entirely.
        st.query_params["tok"] = access_token
        if refresh_token:
            st.query_params["rtok"] = refresh_token


def _restore_from_query_params() -> None:
    """Restore access + refresh tokens for this browser tab after a reload.

    Prefers the opaque ?sid= session-store lookup (real tokens never touch
    the URL). Falls back to legacy raw ?tok=/&rtok= params — for tabs opened
    before this change, or if Redis was unavailable when the session was
    created — and clears them from the URL once restored into session_state.
    """
    if "access_token" in st.session_state:
        return
    sid = st.query_params.get("sid", "")
    if sid:
        access_token, refresh_token = get_session(sid)
        if access_token:
            st.session_state["access_token"] = access_token
            st.session_state["refresh_token"] = refresh_token
            st.session_state["_dash_session_id"] = sid
            return
    tok = st.query_params.get("tok", "")
    rtok = st.query_params.get("rtok", "")
    if tok:
        st.session_state["access_token"] = tok
        st.session_state["refresh_token"] = rtok
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

    Session is restored from an opaque ?sid= URL param on every load
    (F5-safe) — the real tokens live server-side (utils/session_store.py),
    never in the URL. The session id is the only cross-reload persistence
    Streamlit has, so it's kept in sync with session state on every call.
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
    # Load org settings once per session (currency, timezone, branding)
    if not st.session_state.get("_org_settings"):
        _org, _ = client.get_org_settings()
        if _org:
            st.session_state["_org_settings"] = _org
    # Keep the URL's session pointer in sync so F5 / browser reload survives.
    # Prefer the opaque ?sid= (the id itself is stable — no need to rewrite
    # it every render, but it's idempotent and cheap to ensure). Only fall
    # back to raw tokens in the URL if this session was established without
    # a working session store (Redis was down at establish_session() time).
    sid = st.session_state.get("_dash_session_id", "")
    if sid:
        st.query_params["sid"] = sid
        st.query_params.pop("tok", None)
        st.query_params.pop("rtok", None)
    else:
        tok = st.session_state.get("access_token", "")
        rtok = st.session_state.get("refresh_token", "")
        if tok:
            st.query_params["tok"] = tok
        if rtok:
            st.query_params["rtok"] = rtok
    return client


def login(email: str, password: str) -> str:
    """Attempt login. Returns 'ok', 'mfa_required', 'locked', or 'error'.

    On success, establish_session() stores tokens server-side and stamps an
    opaque session id into the URL. On MFA required, mfa_pending_token is
    stored in session state. On account locked, login_locked_until is stored
    in session state."""
    data, err = RMMClient.login(email, password)
    if err:
        return "error"
    if data.get("error") == "account_locked":
        st.session_state["login_locked_until"] = data.get("locked_until", "")
        return "locked"
    if data.get("status") == "mfa_required":
        st.session_state["mfa_pending_token"] = data["mfa_token"]
        st.session_state.pop("login_locked_until", None)
        return "mfa_required"
    st.session_state.pop("login_locked_until", None)
    establish_session(data["access_token"], data.get("refresh_token", ""))
    st.session_state["user"] = data["user"]
    return "ok"


def logout():
    sid = st.session_state.get("_dash_session_id", "")
    if sid:
        delete_session(sid)
    for key in ["access_token", "refresh_token", "user", "_dash_session_id", "_rmm_client"]:
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()


def current_user() -> dict | None:
    return st.session_state.get("user")
