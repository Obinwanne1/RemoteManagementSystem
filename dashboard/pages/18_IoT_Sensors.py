"""IoT Sensors — live sensor readings from IoT devices, Raspberry Pi, MQTT, and SNMP sources."""
import streamlit as st
from datetime import datetime, timezone

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.ai_assistant import render_ai_assistant
from utils.styles import inject_css, BRAND

st.set_page_config(page_title="IoT Sensors — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()
me = st.session_state.get("user", {})
role = me.get("role", "")

st.markdown(
    '<h1 style="margin:0">IoT Sensors</h1>'
    '<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">'
    'Live readings from environmental sensors, UPS, network devices, and Raspberry Pi agents</p>',
    unsafe_allow_html=True,
)

SENSOR_LABELS = {
    "temperature": ("Temperature", "°C", ":material/thermostat:"),
    "humidity":    ("Humidity",    "%",  ":material/water_drop:"),
    "co2":         ("CO₂",         "ppm",":material/air:"),
    "pm25":        ("PM2.5",       "μg/m³",":material/grain:"),
    "voc":         ("VOC",         "ppb",":material/science:"),
    "motion":      ("Motion",      "",   ":material/directions_run:"),
    "door":        ("Door",        "",   ":material/door_open:"),
    "power_watts": ("Power",       "W",  ":material/bolt:"),
    "ups_battery": ("UPS Battery", "%",  ":material/battery_charging_full:"),
    "ups_load":    ("UPS Load",    "%",  ":material/electrical_services:"),
}

SENSOR_TABS = [
    ("Temperature / Humidity", ["temperature", "humidity"]),
    ("Air Quality",            ["co2", "pm25", "voc"]),
    ("Power / UPS",            ["power_watts", "ups_battery", "ups_load"]),
    ("Motion / Door",          ["motion", "door"]),
    ("All",                    list(SENSOR_LABELS.keys())),
]

# ── Load devices ──────────────────────────────────────────────────────────────
with st.spinner("Loading devices…"):
    devices_data, err = client.list_devices(per_page=500)

if err:
    st.error(f"Could not load devices: {err}")
    st.stop()

all_devices = devices_data.get("items", []) if devices_data else []

# Customer filter (admin/technician) — client sees only their own
if role in ("admin", "technician", "superadmin"):
    customers_data, _ = client.list_customers(per_page=200)
    customers = customers_data.get("items", []) if customers_data else []
    customer_opts = {"All Customers": None}
    customer_opts.update({c["name"]: c["id"] for c in customers})
    selected_cust_name = st.selectbox("Customer", list(customer_opts.keys()), key="iot_customer")
    selected_cust_id = customer_opts[selected_cust_name]
    if selected_cust_id:
        all_devices = [d for d in all_devices if d.get("customer_id") == selected_cust_id]
else:
    selected_cust_id = me.get("customer_id")
    all_devices = [d for d in all_devices if d.get("customer_id") == selected_cust_id]

if not all_devices:
    st.info("No devices found for this customer.")
    render_ai_assistant("IoT Sensors page — no devices found")
    st.stop()

# ── Device selector ───────────────────────────────────────────────────────────
device_map = {d.get("display_name") or d.get("hostname"): d["id"] for d in all_devices}
selected_device_name = st.selectbox("Device", list(device_map.keys()), key="iot_device")
selected_device_id = device_map[selected_device_name]

hours_opt = st.select_slider("History window", options=[1, 6, 12, 24, 48, 168], value=24,
                              format_func=lambda h: f"{h}h" if h < 168 else "7 days")

st.markdown("---")

# ── Fetch all sensor data for selected device ─────────────────────────────────
with st.spinner("Loading sensor data…"):
    raw, err = client.get_sensor_data(selected_device_id, hours=hours_opt, limit=5000)

if err:
    st.warning(f"Could not load sensor data: {err}")
    raw = []

readings = raw if isinstance(raw, list) else []

if not readings:
    st.info(
        "No sensor readings for this device in the selected window. "
        "Make sure the IoT agent is running or the device is publishing to MQTT."
    )
    render_ai_assistant("IoT Sensors page — no readings")
    st.stop()

# Group by sensor_type
import pandas as pd
from collections import defaultdict

by_type: dict = defaultdict(list)
for r in readings:
    by_type[r["sensor_type"]].append(r)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_objects = st.tabs([t[0] for t in SENSOR_TABS])

for tab_obj, (tab_name, sensor_types) in zip(tab_objects, SENSOR_TABS):
    with tab_obj:
        visible = {st: by_type[st] for st in sensor_types if by_type.get(st)}

        if not visible:
            st.caption("No readings in this category for the selected window.")
            continue

        # Metric summary row
        cols = st.columns(min(len(visible), 4))
        for col, (stype, sreadings) in zip(cols, visible.items()):
            label, unit, icon = SENSOR_LABELS.get(stype, (stype, "", ""))
            vals = [r["value"] for r in sreadings]
            latest_val = vals[-1]
            avg_val = sum(vals) / len(vals)
            delta = round(latest_val - avg_val, 2)
            with col:
                st.metric(
                    label=f"{icon} {label}",
                    value=f"{latest_val:.1f} {unit}".strip(),
                    delta=f"{delta:+.1f} vs avg" if unit not in ("", "bool") else None,
                )

        # Charts
        for stype, sreadings in visible.items():
            label, unit, icon = SENSOR_LABELS.get(stype, (stype, "", ""))
            df = pd.DataFrame([
                {
                    "time": datetime.fromisoformat(r["collected_at"].replace("Z", "+00:00")),
                    "value": r["value"],
                    "channel": r.get("channel") or "sensor",
                }
                for r in sreadings
            ])
            df = df.sort_values("time")

            st.markdown(
                f'<div style="font-size:0.82rem;font-weight:600;color:#407E3C;margin:0.8rem 0 0.2rem">'
                f'{icon} {label} {f"({unit})" if unit else ""}</div>',
                unsafe_allow_html=True,
            )

            chart_df = df.pivot_table(index="time", columns="channel", values="value", aggfunc="mean")
            st.line_chart(chart_df, height=200, width="stretch")

            # Min / Max / Avg stats strip
            vals = df["value"].tolist()
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Latest", f"{vals[-1]:.1f} {unit}".strip())
            s2.metric("Min", f"{min(vals):.1f} {unit}".strip())
            s3.metric("Max", f"{max(vals):.1f} {unit}".strip())
            s4.metric("Avg", f"{sum(vals)/len(vals):.1f} {unit}".strip())

            # Source breakdown
            sources = {r.get("source", "unknown") for r in sreadings}
            st.caption(f"Source: {', '.join(sorted(sources))} · {len(sreadings)} readings")
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

render_ai_assistant(
    f"IoT Sensors page — device: {selected_device_name}, "
    f"sensor types: {list(by_type.keys())}, "
    f"window: {hours_opt}h"
)
