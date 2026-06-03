"""Software Patches — Installed software and update management."""
import streamlit as st

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Software Patches — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

st.markdown('<h1 style="margin:0">Software Patches</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Installed software and update management</p>', unsafe_allow_html=True)

# ── Load devices (online only) ────────────────────────────────────────────────
with st.spinner("Loading devices..."):
    data, err = client.list_devices(per_page=200)
if err:
    st.warning(f"Could not load devices — {err}")
    st.stop()

all_devices = data.get("items", [])
online_devices = [d for d in all_devices if d.get("is_online")]

if not online_devices:
    st.markdown(
        '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
        'border:1px solid #DDE8DD;color:#6B7B6B">'
        '<div style="font-size:2.5rem;margin-bottom:0.75rem">💻</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No online devices</div>'
        '<div style="font-size:0.85rem">At least one device must be online to view software.</div>'
        '</div>',
        unsafe_allow_html=True
    )
    st.stop()

# ── Two-column layout ─────────────────────────────────────────────────────────
left_col, right_col = st.columns([1, 2.5])

with left_col:
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.2rem;'
        'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">',
        unsafe_allow_html=True
    )
    st.markdown('<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.5rem">Online Devices</div>', unsafe_allow_html=True)

    device_map = {d["hostname"]: d for d in online_devices}
    chosen_hostname = st.selectbox("Device", list(device_map.keys()), label_visibility="collapsed")
    selected_device = device_map.get(chosen_hostname)

    if selected_device:
        ip = selected_device.get("ip_address") or "—"
        os_name = selected_device.get("os_name") or "—"
        st.markdown(
            f'<div style="margin-top:0.75rem;font-size:0.8rem;color:#6B7B6B;line-height:1.7">'
            f'<div><span style="color:#6B7B6B">IP: </span><b style="color:#1A1A1A">{ip}</b></div>'
            f'<div><span style="color:#6B7B6B">OS: </span><b style="color:#1A1A1A">{os_name}</b></div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

    if st.button("🔄 Check for Updates", use_container_width=True):
        st.info("Winget / Chocolatey integration — Phase 6. Update checking will be available once the patch engine is deployed.")

with right_col:
    if selected_device:
        sw_data, sw_err = client.get_device_software(selected_device["id"])
        if sw_err:
            st.warning(f"Could not load software: {sw_err}")
            sw_list = []
        else:
            sw_list = sw_data if isinstance(sw_data, list) else []

        # ── Search bar + stat ─────────────────────────────────────────────────
        search_col, stat_col = st.columns([3, 1])
        with search_col:
            search_q = st.text_input("Search", placeholder="Filter by name or publisher...", label_visibility="collapsed")
        with stat_col:
            st.metric("Installed", len(sw_list))

        if search_q:
            q_lower = search_q.lower()
            sw_list = [s for s in sw_list if q_lower in (s.get("name") or "").lower() or q_lower in (s.get("publisher") or "").lower()]

        # ── Software list ─────────────────────────────────────────────────────
        if not sw_list:
            st.markdown(
                '<div style="text-align:center;padding:2rem;background:#FFFFFF;border-radius:12px;'
                'border:1px solid #DDE8DD;color:#6B7B6B">'
                '<div style="font-size:1.75rem;margin-bottom:0.5rem">🔍</div>'
                '<div style="font-size:0.9rem;font-weight:600;color:#1A2B1A;margin-bottom:0.3rem">No packages found</div>'
                '<div style="font-size:0.8rem">No software data available for this device.</div>'
                '</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="display:grid;grid-template-columns:2.5fr 1.3fr 2fr;gap:8px;'
                'padding:0.4rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
                'border:1px solid #DDE8DD;border-bottom:none;'
                'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
                '<div>Name</div><div>Version</div><div>Publisher</div></div>',
                unsafe_allow_html=True
            )

            rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden;max-height:520px;overflow-y:auto">'
            for i, sw in enumerate(sw_list):
                bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
                name = sw.get("name") or "—"
                version = sw.get("version") or "—"
                publisher = sw.get("publisher") or "—"
                rows_html += (
                    f'<div style="display:grid;grid-template-columns:2.5fr 1.3fr 2fr;gap:8px;'
                    f'padding:0.45rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
                    f'font-size:0.83rem;align-items:center">'
                    f'<div style="font-weight:500;color:#1A1A1A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{name}</div>'
                    f'<div style="color:#6B7B6B;font-family:monospace;font-size:0.79rem">{version}</div>'
                    f'<div style="color:#4A5A4A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{publisher}</div>'
                    f'</div>'
                )
            rows_html += '</div>'
            st.markdown(rows_html, unsafe_allow_html=True)
