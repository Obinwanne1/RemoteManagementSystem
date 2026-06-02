"""App Center — Installed software inventory across all devices."""
import streamlit as st

from utils.auth import require_auth
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="App Center — RMM", layout="wide")
inject_css()

client = require_auth()

st.markdown('<h1 style="margin:0">App Center</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Installed software across all devices</p>', unsafe_allow_html=True)

# ── Load devices ──────────────────────────────────────────────────────────────
data, err = client.list_devices(per_page=200)
if err:
    st.error(f"API error: {err}")
    st.stop()

devices = data.get("items", [])

if not devices:
    st.markdown('<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;border:1px solid #DDE8DD;color:#6B7B6B"><div style="font-size:2.5rem;margin-bottom:0.75rem">📦</div><div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No devices registered</div><div style="font-size:0.85rem">Deploy the agent to register endpoints.</div></div>', unsafe_allow_html=True)
    st.stop()

# ── Toolbar ───────────────────────────────────────────────────────────────────
device_map = {d["hostname"]: d for d in devices}
device_names = list(device_map.keys())

col_sel, col_search, col_stat = st.columns([2, 2, 1])
with col_sel:
    chosen_hostname = st.selectbox("Select Device", device_names)
with col_search:
    search_q = st.text_input("Search software", placeholder="Filter by name or publisher...")

selected_device = device_map.get(chosen_hostname)

# ── Load software ─────────────────────────────────────────────────────────────
if selected_device:
    sw_data, sw_err = client.get_device_software(selected_device["id"], q=search_q or "")

    if sw_err:
        st.warning(f"Could not load software list: {sw_err}")
        sw_list = []
    else:
        sw_list = sw_data if isinstance(sw_data, list) else []

    # Client-side filter fallback
    if search_q and sw_list:
        q_lower = search_q.lower()
        sw_list = [
            s for s in sw_list
            if q_lower in (s.get("name") or "").lower()
            or q_lower in (s.get("publisher") or "").lower()
        ]

    with col_stat:
        st.metric("Installed Packages", len(sw_list))

    # ── Empty state ───────────────────────────────────────────────────────────
    if not sw_list:
        st.markdown(
            '<div style="text-align:center;padding:2.5rem;background:#FFFFFF;border-radius:12px;'
            'border:1px solid #DDE8DD;color:#6B7B6B;margin-top:0.75rem">'
            '<div style="font-size:2rem;margin-bottom:0.5rem">🔍</div>'
            '<div style="font-size:0.95rem;font-weight:600;color:#1A2B1A;margin-bottom:0.3rem">No software found</div>'
            '<div style="font-size:0.82rem">Try a different search term or select another device.</div>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        # ── Table header ──────────────────────────────────────────────────────
        st.markdown(
            '<div style="display:grid;grid-template-columns:2.5fr 1.2fr 1.8fr 1fr 1.2fr;gap:8px;'
            'padding:0.45rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
            'border:1px solid #DDE8DD;border-bottom:none;'
            'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
            '<div>Name</div><div>Version</div><div>Publisher</div><div>Source</div><div>Last Seen</div></div>',
            unsafe_allow_html=True
        )

        SOURCE_COLORS = {
            "winget":      BRAND["primary"],
            "choco":       "#F59E0B",
            "chocolatey":  "#F59E0B",
            "msi":         "#3B82F6",
            "registry":    "#8B5CF6",
            "manual":      BRAND["muted"],
        }

        # ── Table rows ────────────────────────────────────────────────────────
        rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden">'
        for i, sw in enumerate(sw_list):
            bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
            src_raw = sw.get("source") or "unknown"
            src_color = SOURCE_COLORS.get(src_raw.lower(), BRAND["muted"])
            src_badge = badge(src_raw, src_color)
            last_seen = fmt_datetime(sw.get("last_seen") or "")
            name = sw.get("name") or "—"
            version = sw.get("version") or "—"
            publisher = sw.get("publisher") or "—"
            rows_html += (
                f'<div style="display:grid;grid-template-columns:2.5fr 1.2fr 1.8fr 1fr 1.2fr;gap:8px;'
                f'padding:0.5rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
                f'font-size:0.83rem;align-items:center">'
                f'<div style="font-weight:500;color:#1A1A1A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{name}</div>'
                f'<div style="color:#6B7B6B;font-family:monospace;font-size:0.79rem">{version}</div>'
                f'<div style="color:#4A5A4A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{publisher}</div>'
                f'<div>{src_badge}</div>'
                f'<div style="color:#6B7B6B;font-size:0.78rem">{last_seen}</div>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-size:0.78rem;color:#6B7B6B;margin-top:0.5rem;padding:0 0.25rem">'
            f'Showing {len(sw_list)} package{"s" if len(sw_list) != 1 else ""} on <b>{chosen_hostname}</b>'
            f'</div>',
            unsafe_allow_html=True
        )
