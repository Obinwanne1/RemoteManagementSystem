"""
Cached wrappers for frequently-called read endpoints.
Uses st.cache_data so repeated Streamlit reruns hit in-memory cache, not the API.

Usage:
    from utils.cached_calls import cached_summary, cached_list_devices
    summary, err = cached_summary(st.session_state.get("access_token", ""))

The leading underscore on _token tells Streamlit not to hash the value itself;
the string is used as the cache discriminator (different tokens → different entries).

Call st.cache_data.clear() after any mutating operation that should invalidate cache.
"""
import streamlit as st
from utils.auth import get_client


@st.cache_data(ttl=30, show_spinner=False)
def cached_summary(_token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_summary()


@st.cache_data(ttl=30, show_spinner=False)
def cached_health_map(_token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_health_map()


@st.cache_data(ttl=20, show_spinner=False)
def cached_recent_alerts(_token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_recent_alerts()


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_devices(_token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_devices(**params)


@st.cache_data(ttl=60, show_spinner=False)
def cached_list_customers(_token: str, **params):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_customers(**params)


@st.cache_data(ttl=20, show_spinner=False)
def cached_list_alerts(_token: str, **filters):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_alerts(**filters)


@st.cache_data(ttl=120, show_spinner=False)
def cached_list_scripts(_token: str, **filters):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.list_scripts(**filters)


@st.cache_data(ttl=60, show_spinner=False)
def cached_patch_summary(_token: str):
    client = get_client()
    if not client:
        return None, "Not authenticated"
    return client.get_patch_summary()
