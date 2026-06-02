"""Maintenance — Device maintenance and remote actions."""
import streamlit as st

from utils.auth import require_auth
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Maintenance — RMM", layout="wide")
inject_css()

client = require_auth()

st.markdown('<h1 style="margin:0">Maintenance</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Device maintenance and remote actions</p>', unsafe_allow_html=True)

# ── Load online devices ───────────────────────────────────────────────────────
data, err = client.list_devices(per_page=200)
if err:
    st.error(f"API error: {err}")
    st.stop()

all_devices = data.get("items", [])
online_devices = [d for d in all_devices if d.get("is_online")]

if not online_devices:
    st.markdown(
        '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
        'border:1px solid #DDE8DD;color:#6B7B6B">'
        '<div style="font-size:2.5rem;margin-bottom:0.75rem">🔧</div>'
        '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No online devices</div>'
        '<div style="font-size:0.85rem">At least one device must be online to perform maintenance actions.</div>'
        '</div>',
        unsafe_allow_html=True
    )
    st.stop()

# ── Device selector ───────────────────────────────────────────────────────────
def _device_label(d):
    return f"{d['hostname']}  ({d.get('ip_address', '—')})"

device_options = {_device_label(d): d for d in online_devices}
sel_col, _ = st.columns([2.5, 3.5])
with sel_col:
    chosen_label = st.selectbox("Select Device", list(device_options.keys()))

selected = device_options[chosen_label]

# ── Device info card ──────────────────────────────────────────────────────────
metrics = selected.get("latest_metrics") or {}
uptime_sec = metrics.get("uptime_seconds")

def _fmt_uptime(seconds):
    if not seconds:
        return "—"
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    return " ".join(parts) or "< 1m"

os_str = f"{selected.get('os_name') or '—'} {selected.get('os_version') or ''}".strip()

st.markdown(
    f'<div style="background:#FFFFFF;border-radius:12px;padding:1.1rem 1.5rem;'
    f'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1.25rem">'
    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.6rem">'
    f'<div style="width:10px;height:10px;border-radius:50%;background:#22C55E;box-shadow:0 0 6px #22C55E88;flex-shrink:0"></div>'
    f'<span style="font-size:1rem;font-weight:700;color:#1A1A1A">{selected.get("hostname","—")}</span>'
    f'<span style="font-size:0.8rem;color:#6B7B6B">{selected.get("ip_address","—")}</span>'
    f'</div>'
    f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;font-size:0.82rem">'
    f'<div><span style="color:#6B7B6B">OS</span><br><b style="color:#1A1A1A">{os_str or "—"}</b></div>'
    f'<div><span style="color:#6B7B6B">Platform</span><br><b style="color:#1A1A1A">{selected.get("platform","—")}</b></div>'
    f'<div><span style="color:#6B7B6B">Last Seen</span><br><b style="color:#1A1A1A">{fmt_datetime(selected.get("last_seen",""))}</b></div>'
    f'<div><span style="color:#6B7B6B">Uptime</span><br><b style="color:#1A1A1A">{_fmt_uptime(uptime_sec)}</b></div>'
    f'</div></div>',
    unsafe_allow_html=True
)

# ── Action grid ───────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
    'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.6rem">Actions</div>',
    unsafe_allow_html=True
)

# Confirmation gate for destructive actions
confirm_key = f"maint_confirm_{selected['id']}"
if confirm_key not in st.session_state:
    st.session_state[confirm_key] = False

confirm_checked = st.checkbox(
    "I confirm this action on the selected device",
    key=confirm_key
)

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# Row 1
r1c1, r1c2, r1c3 = st.columns(3)
with r1c1:
    reboot_btn = st.button("🔄 Reboot", use_container_width=True, key=f"reboot_{selected['id']}")
with r1c2:
    shutdown_btn = st.button("⏹ Shutdown", use_container_width=True, key=f"shut_{selected['id']}")
with r1c3:
    restore_btn = st.button("📸 Create Restore Point", use_container_width=True, key=f"restore_{selected['id']}")

# Row 2
r2c1, r2c2, r2c3 = st.columns(3)
with r2c1:
    temp_btn = st.button("🗑️ Delete Temp Files", use_container_width=True, key=f"temp_{selected['id']}")
with r2c2:
    browser_btn = st.button("🌐 Clear Browser History", use_container_width=True, key=f"browser_{selected['id']}")
with r2c3:
    chkdsk_btn = st.button("🔍 Check Disk", use_container_width=True, key=f"chkdsk_{selected['id']}")

# ── Action handlers ───────────────────────────────────────────────────────────
if reboot_btn:
    if not confirm_checked:
        st.warning("Check the confirmation box above before rebooting.")
    else:
        with st.spinner(f"Sending reboot command to {selected['hostname']}..."):
            _, action_err = client.reboot_device(selected["id"])
        if action_err:
            st.error(f"Reboot failed: {action_err}")
        else:
            st.success(f"Reboot command sent to {selected['hostname']}.")
            st.session_state[confirm_key] = False

if shutdown_btn:
    if not confirm_checked:
        st.warning("Check the confirmation box above before shutting down.")
    else:
        with st.spinner(f"Sending shutdown command to {selected['hostname']}..."):
            _, action_err = client.shutdown_device(selected["id"])
        if action_err:
            st.error(f"Shutdown failed: {action_err}")
        else:
            st.success(f"Shutdown command sent to {selected['hostname']}.")
            st.session_state[confirm_key] = False

if restore_btn:
    st.info("Create Restore Point — queued via agent. Will be available in Phase 5.")

if temp_btn:
    st.info("Delete Temp Files — queued via agent. Will be available in Phase 5.")

if browser_btn:
    st.info("Clear Browser History — queued via agent. Will be available in Phase 5.")

if chkdsk_btn:
    st.info("Check Disk (chkdsk) — queued via agent. Will be available in Phase 5.")

# ── Maintenance log ───────────────────────────────────────────────────────────
st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
    'letter-spacing:0.07em;color:#6B7B6B;margin-bottom:0.6rem">Recent Maintenance Runs</div>',
    unsafe_allow_html=True
)

runs_data, runs_err = client._get("/api/automation/runs")
if runs_err or not runs_data:
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:10px;padding:1rem 1.25rem;'
        'border:1px solid #DDE8DD;font-size:0.83rem;color:#6B7B6B">'
        'No maintenance run history available. Scheduled task runs will appear here once automation profiles are configured.'
        '</div>',
        unsafe_allow_html=True
    )
else:
    runs = runs_data if isinstance(runs_data, list) else runs_data.get("items", [])
    if not runs:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:10px;padding:1rem 1.25rem;'
            'border:1px solid #DDE8DD;font-size:0.83rem;color:#6B7B6B">'
            'No maintenance runs recorded yet.'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        STATUS_COLORS_RUN = {
            "success":  BRAND["success"],
            "failed":   BRAND["danger"],
            "running":  BRAND["warning"],
            "pending":  BRAND["muted"],
        }

        st.markdown(
            '<div style="display:grid;grid-template-columns:2fr 2fr 1.5fr 1.5fr 1fr;gap:8px;'
            'padding:0.4rem 1rem;background:#F4F6F4;border-radius:8px 8px 0 0;'
            'border:1px solid #DDE8DD;border-bottom:none;'
            'font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B6B">'
            '<div>Profile</div><div>Device</div><div>Started</div><div>Finished</div><div>Status</div></div>',
            unsafe_allow_html=True
        )

        rows_html = '<div style="border:1px solid #DDE8DD;border-radius:0 0 8px 8px;overflow:hidden">'
        for i, run in enumerate(runs[:20]):
            bg = "#FFFFFF" if i % 2 == 0 else "#FAFCFA"
            status_raw = (run.get("status") or "unknown").lower()
            run_color = STATUS_COLORS_RUN.get(status_raw, BRAND["muted"])
            run_b = badge(status_raw, run_color)
            profile_name = run.get("profile_name") or run.get("profile_id") or "—"
            device_name  = run.get("device_hostname") or run.get("device_id") or "—"
            started  = fmt_datetime(run.get("started_at") or "")
            finished = fmt_datetime(run.get("finished_at") or "")
            rows_html += (
                f'<div style="display:grid;grid-template-columns:2fr 2fr 1.5fr 1.5fr 1fr;gap:8px;'
                f'padding:0.5rem 1rem;background:{bg};border-bottom:1px solid #EEF2EE;'
                f'font-size:0.83rem;align-items:center">'
                f'<div style="font-weight:500;color:#1A1A1A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{profile_name}</div>'
                f'<div style="color:#4A5A4A;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{device_name}</div>'
                f'<div style="color:#6B7B6B;font-size:0.78rem">{started}</div>'
                f'<div style="color:#6B7B6B;font-size:0.78rem">{finished}</div>'
                f'<div>{run_b}</div>'
                f'</div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)
