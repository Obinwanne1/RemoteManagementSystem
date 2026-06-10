"""White-label branding loader — fetches from public API, cached in session_state."""
import os
import time
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:5000")
_CACHE_TTL = 300  # 5 min

_DEFAULTS = {
    "app_name":      "RMM System",
    "tagline":       "Remote Monitoring & Management",
    "primary_color": "#407E3C",
    "logo_data":     None,
}


def _fetch_raw() -> dict:
    """Hit the public branding endpoint. Returns defaults on any failure."""
    try:
        resp = requests.get(f"{API_BASE}/api/admin/public/branding", timeout=3)
        if resp.ok:
            data = resp.json()
            merged = dict(_DEFAULTS)
            for k, v in data.items():
                if v:
                    merged[k] = v
            return merged
    except Exception:
        pass
    return dict(_DEFAULTS)


def load_branding() -> dict:
    """Return branding dict. Cached in st.session_state for TTL seconds."""
    now = time.time()
    cached = st.session_state.get("_branding")
    cache_ts = st.session_state.get("_branding_ts", 0)
    if cached and (now - cache_ts) < _CACHE_TTL:
        return cached
    brand = _fetch_raw()
    st.session_state["_branding"] = brand
    st.session_state["_branding_ts"] = now
    return brand


def fetch_branding_early() -> dict:
    """Fetch branding WITHOUT session_state (safe to call before set_page_config)."""
    return _fetch_raw()
