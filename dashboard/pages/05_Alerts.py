import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime, SEVERITY_COLORS

st.set_page_config(page_title="Alerts — RMM", layout="wide")
st.title("🔔 Alerts")

client = require_auth()

tab1, tab2 = st.tabs(["Active Alerts", "Alert Rules"])

with tab1:
    data, err = client.list_alerts(status="open", per_page=100)
    if err:
        st.error(f"API error: {err}")
    else:
        alerts = data.get("items", [])
        if not alerts:
            st.success("No open alerts.")
        for alert in alerts:
            severity = alert["severity"]
            color = SEVERITY_COLORS.get(severity, "#6C757D")
            with st.expander(f'[{severity.upper()}] {alert["message"][:80]}'):
                st.markdown(f"**Triggered:** {fmt_datetime(alert['triggered_at'])}")
                st.markdown(f"**Device:** {alert['device_id']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Acknowledge", key=f"ack_{alert['id']}"):
                        _, err = client.acknowledge_alert(alert["id"])
                        if not err:
                            st.success("Acknowledged")
                            st.rerun()
                with col2:
                    if st.button("Resolve", key=f"res_{alert['id']}"):
                        _, err = client.resolve_alert(alert["id"])
                        if not err:
                            st.success("Resolved")
                            st.rerun()

with tab2:
    st.subheader("Alert Rules")
    rules, err = client.list_alert_rules()
    if err:
        st.error(f"API error: {err}")
    elif rules:
        for rule in rules:
            st.markdown(
                f"**{rule['name']}** — {rule['metric']} {rule['operator']} {rule['threshold']} → "
                f"**{rule['severity']}** | Active: {'✅' if rule['is_active'] else '❌'}"
            )
    else:
        st.info("No alert rules configured.")

    st.subheader("Create Rule")
    with st.form("create_rule"):
        name = st.text_input("Rule Name *")
        metric = st.selectbox("Metric", ["cpu", "ram", "disk", "battery", "offline"])
        operator = st.selectbox("Operator", ["gt", "gte", "lt", "lte"])
        threshold = st.number_input("Threshold (%)", 0.0, 100.0, 90.0)
        severity = st.selectbox("Severity", ["warning", "critical", "info"])
        cooldown = st.number_input("Cooldown (minutes)", 1, 1440, 15)
        auto_ticket = st.checkbox("Auto-create ticket on trigger")
        submitted = st.form_submit_button("Create Rule")

    if submitted and name:
        _, err = client.create_alert_rule({
            "name": name, "metric": metric, "operator": operator,
            "threshold": threshold, "severity": severity,
            "cooldown_minutes": cooldown, "auto_create_ticket": auto_ticket,
        })
        if err:
            st.error(f"Failed: {err}")
        else:
            st.success("Rule created!")
            st.rerun()
