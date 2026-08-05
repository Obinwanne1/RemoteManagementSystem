"""Network Discovery — Scan WiFi/LAN and discover agentless devices."""
import time
import streamlit as st

from utils.auth import require_auth, current_user
from utils.nav import render_sidebar
from utils.ai_assistant import render_ai_assistant
from utils.styles import inject_css, badge, BRAND
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Network Discovery — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()
_role = (current_user() or {}).get("role", "viewer")
_can_scan = _role in ("admin", "superadmin", "technician")

st.markdown(
    '<h1 style="margin:0">Network Discovery</h1>'
    '<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">'
    'Ping-sweep your WiFi/LAN subnet and save discovered devices</p>',
    unsafe_allow_html=True,
)

CARD = (
    "background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;"
    "border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem"
)

PLATFORM_ICON = {
    "ios":     '<i class="fa-brands fa-apple"></i>',
    "android": '<i class="fa-brands fa-android"></i>',
    "windows": '<i class="fa-brands fa-windows"></i>',
    "mac":     '<i class="fa-brands fa-apple"></i>',
    "linux":   '<i class="fa-brands fa-linux"></i>',
    "unknown": '<i class="fa-solid fa-question"></i>',
}

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("nd_scan_id", None),
    ("nd_scan_result", None),
    ("nd_polling", False),
    ("nd_error", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Scan controls ─────────────────────────────────────────────────────────────
st.markdown(f'<div style="{CARD}">', unsafe_allow_html=True)

if _can_scan:
    ctrl1, ctrl2, ctrl3 = st.columns([2.5, 1.5, 1])

    with ctrl1:
        # Auto-detect server's current subnet as default
        if "nd_detected_subnet" not in st.session_state:
            _ip_data, _ = client._get("/api/admin/server_ips")
            _ips = (_ip_data or {}).get("lan_ips", [])
            if _ips:
                import ipaddress as _ipmod
                try:
                    _net = _ipmod.ip_network(f"{_ips[0]}/24", strict=False)
                    st.session_state["nd_detected_subnet"] = str(_net)
                except Exception:
                    st.session_state["nd_detected_subnet"] = "192.168.1.0/24"
            else:
                st.session_state["nd_detected_subnet"] = "192.168.1.0/24"

        scan_range = st.text_input(
            "Subnet (CIDR)",
            value=st.session_state["nd_detected_subnet"],
            placeholder="e.g. 192.168.0.0/24",
            help="Supports /24 or smaller ranges (max 254 hosts).",
            label_visibility="visible",
        )

    # Load customers for selector
    from utils.cached_calls import cached_list_customers
    cust_data, _ = cached_list_customers(st.session_state.get("access_token", ""), per_page=200)
    customers = (cust_data or {}).get("items", [])
    cust_map = {c["name"]: c["id"] for c in customers}

    with ctrl2:
        cust_name = st.selectbox(
            "Assign discovered devices to",
            ["— None —"] + list(cust_map.keys()),
            label_visibility="visible",
        )
        selected_cust_id = cust_map.get(cust_name) if cust_name != "— None —" else None

    with ctrl3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        run_scan = st.button("Scan Network", icon=":material/wifi_find:", width='stretch', type="primary")
else:
    st.info("You have view-only access. Contact an admin or technician to run a network scan.")
    run_scan = False

st.markdown("</div>", unsafe_allow_html=True)

# ── Clear stale agentless devices ─────────────────────────────────────────────
if _can_scan:
    with st.expander("Clear stale devices from old networks"):
        import ipaddress as _ipmod2
        _current_subnet = st.session_state.get("nd_detected_subnet", "")
        st.caption(f"Current detected subnet: **{_current_subnet}**")

        _dev_data, _dev_err = client._get("/api/devices?per_page=500")
        _all_devices = (_dev_data or {}).get("items", []) if not _dev_err else []
        _agentless = [d for d in _all_devices if d.get("is_agentless")]

        # Find devices whose IP doesn't belong to current subnet
        _stale = []
        if _current_subnet and _agentless:
            try:
                _net_obj = _ipmod2.ip_network(_current_subnet, strict=False)
                for _d in _agentless:
                    _ip = _d.get("ip_address") or ""
                    try:
                        if _ip and _ipmod2.ip_address(_ip) not in _net_obj:
                            _stale.append(_d)
                    except Exception:
                        _stale.append(_d)
            except Exception:
                _stale = []

        if not _stale:
            st.success(f"No stale devices — all {len(_agentless)} agentless device(s) are on the current subnet.")
        else:
            st.warning(f"Found **{len(_stale)}** agentless device(s) from other subnets:")
            for _d in _stale:
                st.markdown(
                    f"- `{_d.get('ip_address','?')}` — {_d.get('hostname') or _d.get('name','unknown')} "
                    f"({_d.get('platform','?')})",
                    unsafe_allow_html=False,
                )
            if st.button(f"Delete {len(_stale)} stale device(s)", type="primary", key="clear_stale_btn"):
                _deleted = 0
                for _d in _stale:
                    _, _err = client.delete_device(_d["id"])
                    if not _err:
                        _deleted += 1
                st.success(f"Deleted {_deleted} stale device(s). Refresh page to confirm.")
                st.session_state.pop("nd_detected_subnet", None)
                st.rerun()

# ── Trigger scan ──────────────────────────────────────────────────────────────
if run_scan:
    if not scan_range or not scan_range.strip():
        st.error("Enter a valid CIDR range before scanning.")
    else:
        result, err = client.trigger_network_scan(
            customer_id=selected_cust_id or "",
            scan_range=scan_range.strip(),
        )
        if err:
            st.session_state["nd_error"] = err
            st.session_state["nd_scan_id"] = None
            st.session_state["nd_polling"] = False
        else:
            st.session_state["nd_scan_id"] = result.get("scan_id")
            st.session_state["nd_polling"] = True
            st.session_state["nd_scan_result"] = None
            st.session_state["nd_error"] = None
            st.rerun()

# ── Poll until complete ───────────────────────────────────────────────────────
if st.session_state["nd_polling"] and st.session_state["nd_scan_id"]:
    scan_id = st.session_state["nd_scan_id"]
    with st.spinner("Scanning network — pinging all hosts, this takes 15–30 seconds..."):
        for _ in range(40):          # max ~2 minutes (40 × 3s)
            time.sleep(3)
            data, err = client._get(f"/api/network/scans/{scan_id}")
            if err:
                st.session_state["nd_error"] = err
                st.session_state["nd_polling"] = False
                break
            status = (data or {}).get("status", "running")
            if status in ("completed", "failed"):
                st.session_state["nd_scan_result"] = data
                st.session_state["nd_polling"] = False
                st.session_state["nd_error"] = None
                break
        else:
            st.session_state["nd_error"] = "Scan timed out. Try a smaller subnet."
            st.session_state["nd_polling"] = False
    st.rerun()

# ── Error ─────────────────────────────────────────────────────────────────────
if st.session_state["nd_error"]:
    st.error(f"Scan error: {st.session_state['nd_error']}")

# ── Results ───────────────────────────────────────────────────────────────────
scan_result = st.session_state["nd_scan_result"]

if scan_result:
    hosts = scan_result.get("discovered_hosts") or []

    # Check for error payload from task
    if hosts and isinstance(hosts[0], dict) and "error" in hosts[0]:
        st.error(hosts[0]["error"])
        st.stop()

    # Summary metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Hosts Found", len(hosts))
    mc2.metric("Mobile", sum(1 for h in hosts if h.get("device_type") == "mobile"))
    mc3.metric("New Devices Saved", scan_result.get("new_devices_count", 0))
    mc4.metric("Scan Status", scan_result.get("status", "—").title())

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if not hosts:
        st.info("No hosts responded. Check that your subnet is correct and devices are online.")
    else:
        # Save All button
        save_col, _ = st.columns([2, 5])
        with save_col:
            if st.button("Save All to Devices", icon=":material/save:", type="primary", width='stretch'):
                result, err = client.upsert_agentless_devices(
                    hosts=hosts,
                    customer_id=selected_cust_id,
                )
                if err:
                    st.error(f"Failed: {err}")
                else:
                    r = result or {}
                    st.success(
                        f"Saved — {r.get('created', 0)} created, "
                        f"{r.get('updated', 0)} updated, "
                        f"{r.get('skipped', 0)} skipped."
                    )

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # Table header
        st.markdown(
            '<div style="display:grid;grid-template-columns:0.5fr 1.4fr 1.5fr 1.8fr 1.2fr 0.9fr 0.8fr;'
            'gap:8px;padding:0.45rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
            'border:1px solid #DDE8DD;border-bottom:none;'
            'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
            '<div>Type</div><div>IP Address</div><div>MAC Address</div>'
            '<div>Vendor</div><div>Platform</div><div>Status</div><div>Save</div></div>',
            unsafe_allow_html=True,
        )

        rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden">'
        for i, host in enumerate(hosts):
            bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
            platform = host.get("platform", "unknown")
            icon = PLATFORM_ICON.get(platform, "—")
            status_raw = host.get("status", "up")
            status_color = BRAND["success"] if status_raw == "up" else BRAND["danger"]
            status_b = badge(status_raw, status_color)
            plat_b = badge(platform, "#407E3C")
            rows_html += (
                f'<div style="display:grid;grid-template-columns:0.5fr 1.4fr 1.5fr 1.8fr 1.2fr 0.9fr 0.8fr;'
                f'gap:8px;padding:0.5rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
                f'font-size:0.83rem;align-items:center">'
                f'<div style="font-size:1.2rem;text-align:center">{icon}</div>'
                f'<div style="font-weight:600;color:#1A1A1A;font-family:monospace;font-size:0.8rem">{host.get("ip","—")}</div>'
                f'<div style="color:#6B7B6B;font-family:monospace;font-size:0.78rem">{host.get("mac") or "—"}</div>'
                f'<div style="color:#4A5A4A;font-size:0.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{host.get("vendor","Unknown")}</div>'
                f'<div>{plat_b}</div>'
                f'<div>{status_b}</div>'
                f'<div style="font-size:0.75rem;color:#407E3C">auto-saved</div>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown(
            '<div style="font-size:0.78rem;color:#6B7B6B;margin-top:0.5rem">'
            'Devices are auto-saved during the scan. Use <b>Save All</b> to re-sync or reassign to a customer.'
            '</div>',
            unsafe_allow_html=True,
        )

elif not st.session_state["nd_polling"]:
    # Idle state — show past scans
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    scans_data, scans_err = client._get("/api/network/scans")
    scans = (scans_data or []) if not scans_err else []

    if scans:
        st.markdown(
            f'<div style="font-size:0.85rem;color:#6B7B6B;margin-bottom:0.6rem">'
            f'Previous scans ({len(scans)})</div>',
            unsafe_allow_html=True,
        )
        for s in scans[:5]:
            status = s.get("status", "—")
            color = "#22C55E" if status == "completed" else ("#EF4444" if status == "failed" else "#F59E0B")
            hosts_count = len(s.get("discovered_hosts") or [])
            st.markdown(
                f'<div style="background:#FFF;border:1px solid #DDE8DD;border-radius:8px;'
                f'padding:0.6rem 1rem;margin-bottom:0.4rem;display:flex;align-items:center;gap:1rem;'
                f'font-size:0.82rem;color:#1A1A1A">'
                f'<span style="color:{color};font-weight:700">{status.upper()}</span>'
                f'<span>{s.get("scan_range","—")}</span>'
                f'<span style="color:#6B7B6B">{fmt_datetime(s.get("started_at",""))}</span>'
                f'<span style="margin-left:auto;color:#6B7B6B">{hosts_count} host{"s" if hosts_count != 1 else ""} · {s.get("new_devices_count",0)} new</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
            'border:1px solid #DDE8DD;color:#6B7B6B;margin-top:0.5rem">'
            '<div style="font-size:2rem;margin-bottom:0.75rem"><i class="fa-solid fa-satellite-dish" style="color:#6B7B6B"></i></div>'
            '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No scans yet</div>'
            '<div style="font-size:0.85rem">Enter your subnet above and click <b>Scan Network</b>.<br>'
            'Works on any WiFi or LAN subnet — phones, laptops, IoT devices all appear.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

render_ai_assistant("Network Discovery", {"context": "navigation_only"})
