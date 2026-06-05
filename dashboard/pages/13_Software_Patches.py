"""Software Patches — Installed software and update management."""
import html as html_mod
import streamlit as st


def _clean(text: str) -> str:
    """Strip non-printable and block/box-drawing Unicode before rendering."""
    if not text:
        return "—"
    cleaned = "".join(
        c for c in text
        if c.isprintable() and not (0x2500 <= ord(c) <= 0x259F)
    ).strip()
    return cleaned or "—"

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
online_devices = [d for d in all_devices if d.get("is_online") and not d.get("is_agentless")]

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
    st.markdown(
        '<div style="font-size:0.78rem;color:#6B7B6B;background:#F5F8F5;border-left:3px solid #407E3C;'
        'border-radius:4px;padding:0.5rem 0.75rem;margin-bottom:0.75rem">'
        '⚠️ Only agent-managed devices appear here. Mobile, agentless, and network-discovered devices '
        '(Android, iOS, etc.) cannot report installed software — they have no local agent to query.'
        '</div>',
        unsafe_allow_html=True
    )

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
            rows = ""
            for i, sw in enumerate(sw_list):
                bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
                name      = html_mod.escape(_clean(sw.get("name")      or ""))
                version   = html_mod.escape(_clean(sw.get("version")   or ""))
                publisher = html_mod.escape(_clean(sw.get("publisher") or ""))
                rows += (
                    f'<tr style="background:{bg}">'
                    f'<td style="padding:6px 12px;font-size:13px;color:#1A1A1A;border-bottom:1px solid #EEF2EE">{name}</td>'
                    f'<td style="padding:6px 12px;font-size:12px;color:#6B7B6B;font-family:monospace;border-bottom:1px solid #EEF2EE">{version}</td>'
                    f'<td style="padding:6px 12px;font-size:13px;color:#4A5A4A;border-bottom:1px solid #EEF2EE">{publisher}</td>'
                    f'</tr>'
                )
            table_html = (
                '<table style="width:100%;border-collapse:collapse">'
                '<thead><tr style="background:#F4F6F4">'
                '<th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;border-bottom:2px solid #DDE8DD">Name</th>'
                '<th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;border-bottom:2px solid #DDE8DD">Version</th>'
                '<th style="padding:8px 12px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B;border-bottom:2px solid #DDE8DD">Publisher</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>'
            )
            st.markdown(table_html, unsafe_allow_html=True)
