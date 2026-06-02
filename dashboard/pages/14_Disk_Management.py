"""Disk Management — Disk health, usage and maintenance."""
import streamlit as st
import plotly.graph_objects as go

from utils.auth import require_auth
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Disk Management — RMM", layout="wide")
inject_css()

client = require_auth()

st.markdown('<h1 style="margin:0">Disk Management</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Disk health, usage and maintenance</p>', unsafe_allow_html=True)

# ── Load devices ──────────────────────────────────────────────────────────────
data, err = client.list_devices(per_page=200)
if err:
    st.error(f"API error: {err}")
    st.stop()

devices = data.get("items", [])
if not devices:
    st.markdown(
        '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
        'border:1px solid #DDE8DD;color:#6B7B6B">'
        '<div style="font-size:2.5rem;margin-bottom:0.75rem">💾</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No devices registered</div>'
        '<div style="font-size:0.85rem">Deploy the agent to register endpoints.</div>'
        '</div>',
        unsafe_allow_html=True
    )
    st.stop()

# ── Device selector ───────────────────────────────────────────────────────────
device_map = {d["hostname"]: d for d in devices}
sel_col, _ = st.columns([2, 4])
with sel_col:
    chosen_hostname = st.selectbox("Select Device", list(device_map.keys()))

selected_device = device_map[chosen_hostname]
metrics = selected_device.get("latest_metrics") or {}
disks = metrics.get("disks") or []

# ── No disk data ──────────────────────────────────────────────────────────────
if not disks:
    st.markdown(
        '<div style="text-align:center;padding:2.5rem;background:#FFFFFF;border-radius:12px;'
        'border:1px solid #DDE8DD;color:#6B7B6B;margin-top:0.5rem">'
        '<div style="font-size:2rem;margin-bottom:0.5rem">💾</div>'
        '<div style="font-size:0.95rem;font-weight:600;color:#1A2B1A;margin-bottom:0.3rem">No disk metrics available for this device</div>'
        '<div style="font-size:0.82rem">Disk data will appear once the agent reports metrics.</div>'
        '</div>',
        unsafe_allow_html=True
    )
else:
    # ── Gauges ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.5rem">Disk Usage</div>',
        unsafe_allow_html=True
    )

    gauge_cols = st.columns(min(len(disks), 4))
    for idx, disk in enumerate(disks[:4]):
        pct = float(disk.get("percent") or 0)
        mountpoint = disk.get("mountpoint") or disk.get("device") or f"Disk {idx+1}"
        total_gb = float(disk.get("total_gb") or 0)
        used_gb = float(disk.get("used_gb") or 0)
        free_gb = float(disk.get("free_gb") or 0)

        gauge_color = BRAND["success"] if pct < 75 else (BRAND["warning"] if pct < 90 else BRAND["danger"])

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pct,
            number={"suffix": "%", "font": {"size": 22, "color": "#1A1A1A"}},
            title={"text": mountpoint, "font": {"size": 13, "color": "#1A2B1A"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#DDE8DD", "tickfont": {"size": 9}},
                "bar":  {"color": gauge_color, "thickness": 0.28},
                "bgcolor": "#F4F6F4",
                "borderwidth": 0,
                "steps": [
                    {"range": [0,  75], "color": "#F4F6F4"},
                    {"range": [75, 90], "color": "#FEF3C7"},
                    {"range": [90, 100], "color": "#FEE2E2"},
                ],
                "threshold": {
                    "line": {"color": gauge_color, "width": 3},
                    "thickness": 0.85,
                    "value": pct,
                },
            },
        ))
        fig.update_layout(
            height=200,
            margin=dict(t=32, b=8, l=16, r=16),
            paper_bgcolor="#FFFFFF",
        )

        with gauge_cols[idx]:
            st.markdown(
                '<div style="background:#FFFFFF;border-radius:12px;border:1px solid #DDE8DD;'
                'box-shadow:0 2px 8px rgba(0,0,0,0.05);padding:0.5rem 0.5rem 0">',
                unsafe_allow_html=True
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.markdown(
                f'<div style="padding:0 0.75rem 0.75rem;font-size:0.78rem;color:#6B7B6B;line-height:1.7">'
                f'<div style="display:flex;justify-content:space-between"><span>Used</span><b style="color:#1A1A1A">{used_gb:.1f} GB</b></div>'
                f'<div style="display:flex;justify-content:space-between"><span>Free</span><b style="color:#22C55E">{free_gb:.1f} GB</b></div>'
                f'<div style="display:flex;justify-content:space-between"><span>Total</span><b style="color:#1A1A1A">{total_gb:.1f} GB</b></div>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.markdown('</div>', unsafe_allow_html=True)

    # ── Summary table ─────────────────────────────────────────────────────────
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.5rem">Disk Summary</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div style="display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr 1fr 1fr;gap:8px;'
        'padding:0.4rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
        'border:1px solid #DDE8DD;border-bottom:none;'
        'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
        '<div>Mount / Device</div><div style="text-align:right">Total</div>'
        '<div style="text-align:right">Used</div><div style="text-align:right">Free</div>'
        '<div style="text-align:right">Used %</div><div>Health</div></div>',
        unsafe_allow_html=True
    )

    rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden">'
    for i, disk in enumerate(disks):
        bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
        pct = float(disk.get("percent") or 0)
        mountpoint = disk.get("mountpoint") or disk.get("device") or f"Disk {i+1}"
        total_gb = float(disk.get("total_gb") or 0)
        used_gb = float(disk.get("used_gb") or 0)
        free_gb = float(disk.get("free_gb") or 0)
        health_label = "Healthy" if pct < 75 else ("Warning" if pct < 90 else "Critical")
        health_color = BRAND["success"] if pct < 75 else (BRAND["warning"] if pct < 90 else BRAND["danger"])
        health_b = badge(health_label, health_color)
        pct_color = health_color
        rows_html += (
            f'<div style="display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr 1fr 1fr;gap:8px;'
            f'padding:0.5rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
            f'font-size:0.83rem;align-items:center">'
            f'<div style="font-weight:600;color:#1A1A1A">{mountpoint}</div>'
            f'<div style="color:#4A5A4A;text-align:right">{total_gb:.1f} GB</div>'
            f'<div style="color:#4A5A4A;text-align:right">{used_gb:.1f} GB</div>'
            f'<div style="color:#22C55E;text-align:right;font-weight:500">{free_gb:.1f} GB</div>'
            f'<div style="text-align:right;font-weight:600;color:{pct_color}">{pct:.1f}%</div>'
            f'<div>{health_b}</div>'
            f'</div>'
        )
    rows_html += '</div>'
    st.markdown(rows_html, unsafe_allow_html=True)

    # ── Action buttons ────────────────────────────────────────────────────────
    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.5rem">Maintenance Actions</div>',
        unsafe_allow_html=True
    )

    act1, act2, act3 = st.columns(3)
    with act1:
        if st.button("🔧 Defragment", use_container_width=True):
            st.info("Defragment queued — will execute via agent in Phase 5.")
    with act2:
        if st.button("🩺 Check Disk", use_container_width=True):
            st.info("Check Disk (chkdsk) queued — will execute via agent in Phase 5.")
    with act3:
        if st.button("🗑️ Clean Temp Files", use_container_width=True):
            st.info("Temp file cleanup queued — will execute via agent in Phase 5.")
