"""
Cached wrappers for frequently-called read endpoints.
Uses st.cache_data so repeated Streamlit reruns hit in-memory cache, not the API.

Usage:
    from utils.cached_calls import cached_summary, cached_list_devices
    summary, err = cached_summary(st.session_state.get("access_token", ""))

The token parameter is deliberately NOT underscore-prefixed: Streamlit's
st.cache_data excludes underscore-prefixed parameters from the cache key
entirely (that convention exists for passing unhashable objects, like DB
connections, that Streamlit's hasher can't handle) — it does not "use the
value as a discriminator while skipping the hash" the way an earlier version
of this module's docstring claimed. A leading underscore here caused every
call to collapse onto one shared cache entry regardless of the token's
value, so within each function's TTL, whichever user's request populated
the cache first had their data served back to every other user/session
process-wide — a real cross-tenant/cross-session data leak (found while
writing dashboard/tests/test_dashboard_overview_page.py, confirmed with a
standalone repro before this fix: audits/testing_audit.md). A plain access-
token string is trivially hashable, so dropping the underscore is sufficient.

Call st.cache_data.clear() after any mutating operation that should invalidate cache.
"""
import streamlit as st
from utils.auth import get_client


@st.cache_data(ttl=60, show_spinner=False)
def cached_summary(token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_summary()


@st.cache_data(ttl=30, show_spinner=False)
def cached_health_map(token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_health_map()


@st.cache_data(ttl=30, show_spinner=False)
def cached_recent_alerts(token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_recent_alerts()


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_devices(token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_devices(**params)


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_customers(token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_customers(**params)


@st.cache_data(ttl=20, show_spinner=False)
def cached_list_alerts(token: str, **filters):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_alerts(**filters)


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_scripts(token: str, **filters):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_scripts(**filters)


@st.cache_data(ttl=60, show_spinner=False)
def cached_patch_summary(token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_patch_summary()


@st.cache_data(ttl=30, show_spinner=False)
def cached_activity_feed(token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_activity_feed()


@st.cache_data(ttl=30, show_spinner=False)
def cached_recent_events(token: str, limit: int = 20):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_recent_events(limit=limit)


@st.cache_data(ttl=45, show_spinner=False)
def cached_usage_summary(token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_usage_summary(**params)


@st.cache_data(ttl=45, show_spinner=False)
def cached_usage_timeseries(token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_usage_timeseries(**params)


@st.cache_data(ttl=45, show_spinner=False)
def cached_usage_by_feature(token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_usage_by_feature(**params)
