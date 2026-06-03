"""Network Discovery — Scan and discover network devices."""
import streamlit as st

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Network Discovery — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

st.markdown('<h1 style="margin:0">Network Discovery</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Scan and discover network devices</p>', unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "nd_results" not in st.session_state:
    st.session_state["nd_results"] = None
if "nd_error" not in st.session_state:
    st.session_state["nd_error"] = None
if "nd_scanned_at" not in st.session_state:
    st.session_state["nd_scanned_at"] = None

# ── Scan button ───────────────────────────────────────────────────────────────
top_l, top_r = st.columns([3, 1])
with top_l:
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.5rem;border:1px solid #DDE8DD;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem">'
        '<div style="font-size:0.85rem;color:#4A5A4A;line-height:1.6">'
        'Discovers all reachable hosts on the local network segment. Requires at least one agent to be online. '
        'Results include IP, hostname, MAC address, vendor, and open ports.'
        '</div></div>',
        unsafe_allow_html=True
    )
with top_r:
    run_scan = st.button("🔍 Run Network Scan", use_container_width=True)

if run_scan:
    with st.spinner("Scanning network — this may take 10–30 seconds..."):
        result, err = client._get("/api/network/scan")
    if err:
        st.session_state["nd_error"] = err
        st.session_state["nd_results"] = None
    else:
        st.session_state["nd_results"] = result
        st.session_state["nd_error"] = None
        from datetime import datetime
        st.session_state["nd_scanned_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Error state ───────────────────────────────────────────────────────────────
if st.session_state["nd_error"]:
    st.info("Network discovery requires an agent to be online and reachable. Start the RMM agent on at least one endpoint and retry.")
    st.caption(f"Detail: {st.session_state['nd_error']}")

# ── Results ───────────────────────────────────────────────────────────────────
results = st.session_state["nd_results"]

if results is not None:
    hosts = results.get("hosts", []) if isinstance(results, dict) else []

    if st.session_state["nd_scanned_at"]:
        st.markdown(
            f'<div style="font-size:0.78rem;color:#6B7B6B;margin-bottom:0.75rem">'
            f'Last scan: <b>{st.session_state["nd_scanned_at"]}</b> — {len(hosts)} host{"s" if len(hosts) != 1 else ""} discovered'
            f'</div>',
            unsafe_allow_html=True
        )

    if not hosts:
        st.markdown(
            '<div style="text-align:center;padding:2.5rem;background:#FFFFFF;border-radius:12px;'
            'border:1px solid #DDE8DD;color:#6B7B6B">'
            '<div style="font-size:2rem;margin-bottom:0.5rem">📡</div>'
            '<div style="font-size:0.95rem;font-weight:600;color:#1A2B1A;margin-bottom:0.3rem">No hosts discovered</div>'
            '<div style="font-size:0.82rem">No reachable devices found on the network segment.</div>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        # ── Summary metrics ───────────────────────────────────────────────────
        online_count = sum(1 for h in hosts if (h.get("status") or "").lower() == "up")
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Hosts Found", len(hosts))
        mc2.metric("Online", online_count)
        mc3.metric("Offline / Unknown", len(hosts) - online_count)

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # ── Table header ──────────────────────────────────────────────────────
        st.markdown(
            '<div style="display:grid;grid-template-columns:1.3fr 1.8fr 1.5fr 1.5fr 2fr 0.8fr;gap:8px;'
            'padding:0.45rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
            'border:1px solid #DDE8DD;border-bottom:none;'
            'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
            '<div>IP Address</div><div>Hostname</div><div>MAC Address</div>'
            '<div>Vendor</div><div>Open Ports</div><div>Status</div></div>',
            unsafe_allow_html=True
        )

        rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden">'
        for i, host in enumerate(hosts):
            bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
            status_raw = (host.get("status") or "unknown").lower()
            status_color = BRAND["success"] if status_raw == "up" else (BRAND["danger"] if status_raw == "down" else BRAND["muted"])
            status_b = badge(status_raw, status_color)
            ports = host.get("open_ports") or []
            if isinstance(ports, list):
                ports_str = ", ".join(str(p) for p in ports[:8])
                if len(ports) > 8:
                    ports_str += f" +{len(ports)-8} more"
            else:
                ports_str = str(ports)
            ip = host.get("ip") or "—"
            hostname = host.get("hostname") or "—"
            mac = host.get("mac") or "—"
            vendor = host.get("vendor") or "—"
            rows_html += (
                f'<div style="display:grid;grid-template-columns:1.3fr 1.8fr 1.5fr 1.5fr 2fr 0.8fr;gap:8px;'
                f'padding:0.5rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
                f'font-size:0.83rem;align-items:center">'
                f'<div style="font-weight:600;color:#1A1A1A;font-family:monospace;font-size:0.8rem">{ip}</div>'
                f'<div style="color:#1A1A1A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{hostname}</div>'
                f'<div style="color:#6B7B6B;font-family:monospace;font-size:0.78rem">{mac}</div>'
                f'<div style="color:#4A5A4A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{vendor}</div>'
                f'<div style="color:#6B7B6B;font-size:0.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{ports_str or "—"}</div>'
                f'<div>{status_b}</div>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)

elif not run_scan:
    # No scan yet — idle state
    st.markdown(
        '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
        'border:1px solid #DDE8DD;color:#6B7B6B;margin-top:0.5rem">'
        '<div style="font-size:2.5rem;margin-bottom:0.75rem">📡</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No scan results yet</div>'
        '<div style="font-size:0.85rem">Click <b>Run Network Scan</b> above to discover devices on the network.</div>'
        '</div>',
        unsafe_allow_html=True
    )
