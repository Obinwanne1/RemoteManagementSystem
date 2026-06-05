"""Alerts — Active alerts and notification rules."""
import streamlit as st

from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.styles import inject_css, badge, BRAND, STATUS_COLORS, section_header
from utils.formatters import fmt_datetime, PRIORITY_COLORS, SEVERITY_COLORS

st.set_page_config(page_title="Alerts — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(
    '<h1 style="margin:0">Alerts</h1>'
    '<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Active alerts and notification rules</p>',
    unsafe_allow_html=True,
)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_alerts, tab_rules = st.tabs(["Active Alerts", "Alert Rules"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Active Alerts
# ═══════════════════════════════════════════════════════════════════════════════
with tab_alerts:

    # Load all open alerts
    with st.spinner("Loading alerts..."):
        data, err = client.list_alerts(status="open", per_page=100)
    if err:
        st.warning(f"Could not load alerts — {err}")
        data = None

    all_alerts = data.get("items", []) if data else []

    # ── Summary stat row ──────────────────────────────────────────────────────
    open_count   = len(all_alerts)
    crit_count   = sum(1 for a in all_alerts if a.get("severity") == "critical")
    ack_count    = sum(1 for a in all_alerts if a.get("status") == "acknowledged")

    sm1, sm2, sm3, sm4 = st.columns(4)
    with sm1:
        st.metric("Open Alerts", open_count)
    with sm2:
        st.metric("Critical", crit_count, delta=None)
    with sm3:
        st.metric("Acknowledged", ack_count)
    with sm4:
        st.metric("Warning", sum(1 for a in all_alerts if a.get("severity") == "warning"))

    st.markdown('<div style="margin-bottom:0.5rem"></div>', unsafe_allow_html=True)

    # ── Severity filter ───────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:#FFF;border-radius:10px;padding:0.9rem 1.1rem;'
        'border:1px solid #DDE8DD;margin-bottom:1rem">',
        unsafe_allow_html=True,
    )
    ff1, ff2 = st.columns([2, 4])
    with ff1:
        sev_filter = st.selectbox(
            "Filter by severity",
            ["All", "critical", "warning", "info"],
            label_visibility="collapsed",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # Apply filter
    filtered_alerts = all_alerts if sev_filter == "All" else [
        a for a in all_alerts if a.get("severity") == sev_filter
    ]

    cap_col, exp_col = st.columns([6, 1])
    with cap_col:
        st.caption(f"Showing {len(filtered_alerts)} alert{'s' if len(filtered_alerts) != 1 else ''}")
    with exp_col:
        if filtered_alerts:
            import pandas as pd
            _df = pd.DataFrame([{
                "ID": a.get("id", ""), "Severity": a.get("severity", ""),
                "Status": a.get("status", ""), "Device": a.get("device_hostname", ""),
                "Message": a.get("message", ""), "Triggered": a.get("triggered_at", ""),
            } for a in filtered_alerts])
            st.download_button(
                "Export CSV", data=_df.to_csv(index=False).encode("utf-8"),
                file_name="alerts.csv", mime="text/csv", use_container_width=True,
            )

    # ── Alert list ────────────────────────────────────────────────────────────
    if not filtered_alerts:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:12px;padding:2.5rem 1.5rem;'
            'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);'
            'margin-bottom:1rem;text-align:center">'
            '<div style="font-size:2.5rem;margin-bottom:0.5rem">✅</div>'
            '<div style="font-size:1rem;font-weight:600;color:#1A1A1A;margin-bottom:0.25rem">No alerts</div>'
            '<div style="font-size:0.85rem;color:#6B7B6B">All clear — no open alerts match your filter.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        for alert in filtered_alerts:
            sev      = alert.get("severity", "info")
            sev_color = SEVERITY_COLORS.get(sev, "#8492A6")
            status_val = alert.get("status", "open")
            hostname  = alert.get("device_hostname") or alert.get("device_id", "—")
            triggered = fmt_datetime(alert.get("triggered_at", ""))
            msg       = alert.get("message", "—")

            with st.expander(f'{msg[:90]}{"…" if len(msg) > 90 else ""}', expanded=False):
                # Severity color bar + meta row
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.75rem">'
                    + f'<div style="width:4px;height:36px;border-radius:3px;background:{sev_color};flex-shrink:0"></div>'
                    + badge(sev, sev_color)
                    + badge(status_val, BRAND["warning"] if status_val == "acknowledged" else BRAND["danger"] if status_val == "open" else BRAND["success"])
                    + f'<span style="color:#6B7B6B;font-size:0.82rem">Device: <b style="color:#1A1A1A">{hostname}</b></span>'
                    + f'<span style="color:#6B7B6B;font-size:0.82rem">Triggered: {triggered}</span>'
                    + '</div>',
                    unsafe_allow_html=True,
                )

                # Full message
                st.markdown(
                    '<div style="background:#F4F6F4;border-radius:8px;padding:0.75rem 1rem;'
                    'border:1px solid #DDE8DD;margin-bottom:0.75rem;font-size:0.88rem;color:#1A1A1A">'
                    + msg
                    + '</div>',
                    unsafe_allow_html=True,
                )

                # Action buttons
                btn_col1, btn_col2, _ = st.columns([1, 1, 4])
                with btn_col1:
                    if st.button("Acknowledge", key=f"ack_{alert['id']}", use_container_width=True):
                        _, aerr = client.acknowledge_alert(alert["id"])
                        if aerr:
                            st.error(f"Failed: {aerr}")
                        else:
                            st.success("Alert acknowledged.")
                            st.rerun()
                with btn_col2:
                    if st.button("Resolve", key=f"res_{alert['id']}", use_container_width=True):
                        _, rerr = client.resolve_alert(alert["id"])
                        if rerr:
                            st.error(f"Failed: {rerr}")
                        else:
                            st.success("Alert resolved.")
                            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Alert Rules
# ═══════════════════════════════════════════════════════════════════════════════
with tab_rules:

    rules_data, rules_err = client.list_alert_rules()
    rules = rules_data if isinstance(rules_data, list) else []

    if rules_err:
        st.error(f"API error loading rules: {rules_err}")
    elif not rules:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:12px;padding:1.5rem;'
            'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);'
            'margin-bottom:1rem;text-align:center">'
            '<div style="font-size:0.9rem;color:#6B7B6B">No alert rules configured yet. Create one below.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(section_header("Configured Rules", f"{len(rules)} rule{'s' if len(rules) != 1 else ''}"), unsafe_allow_html=True)
        for rule in rules:
            r_sev   = rule.get("severity", "info")
            r_color = SEVERITY_COLORS.get(r_sev, "#8492A6")
            is_active = rule.get("is_active", True)
            metric    = rule.get("metric", "—")
            operator  = rule.get("operator", "—")
            threshold = rule.get("threshold", "—")
            cooldown  = rule.get("cooldown_minutes", "—")

            with st.expander(rule.get("name", "Unnamed Rule"), expanded=False):
                st.markdown(
                    '<div style="background:#FFFFFF;border-radius:12px;padding:1rem 1.2rem;'
                    'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:0.75rem">'
                    '<div style="display:flex;flex-wrap:wrap;gap:1.5rem;align-items:center">'
                    + f'<span style="font-size:0.82rem;color:#6B7B6B">Metric: <b style="color:#1A1A1A">{metric}</b></span>'
                    + f'<span style="font-size:0.82rem;color:#6B7B6B">Condition: <b style="color:#1A1A1A">{operator} {threshold}</b></span>'
                    + f'<span style="font-size:0.82rem;color:#6B7B6B">Cooldown: <b style="color:#1A1A1A">{cooldown} min</b></span>'
                    + badge(r_sev, r_color)
                    + badge("active" if is_active else "inactive", BRAND["success"] if is_active else BRAND["muted"])
                    + '</div></div>',
                    unsafe_allow_html=True,
                )

                act_col1, act_col2, _ = st.columns([1, 1, 4])
                with act_col1:
                    toggle_label = "Deactivate" if is_active else "Activate"
                    if st.button(toggle_label, key=f"toggle_{rule['id']}", use_container_width=True):
                        _, uerr = client.update_alert_rule(rule["id"], {"is_active": not is_active})
                        if uerr:
                            st.error(f"Failed: {uerr}")
                        else:
                            st.success(f"Rule {'deactivated' if is_active else 'activated'}.")
                            st.rerun()
                with act_col2:
                    if st.button("Delete", key=f"del_{rule['id']}", use_container_width=True):
                        _, derr = client.delete_alert_rule(rule["id"])
                        if derr:
                            st.error(f"Failed: {derr}")
                        else:
                            st.success("Rule deleted.")
                            st.rerun()

    # ── Create Rule form ──────────────────────────────────────────────────────
    st.markdown('<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)
    st.markdown(section_header("Create Alert Rule", "Define a new monitoring threshold"), unsafe_allow_html=True)

    st.markdown(
        '<div style="background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;'
        'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem">',
        unsafe_allow_html=True,
    )
    with st.form("create_alert_rule_form", clear_on_submit=True):
        rc1, rc2 = st.columns([2, 1])
        with rc1:
            rule_name = st.text_input("Rule Name *", placeholder="e.g. High CPU Warning")
        with rc2:
            rule_severity = st.selectbox("Severity", ["warning", "critical", "info"])

        rc3, rc4, rc5, rc6 = st.columns([1.5, 1, 1.5, 1])
        with rc3:
            rule_metric = st.selectbox("Metric", ["cpu", "ram", "disk", "battery", "offline"])
        with rc4:
            rule_operator = st.selectbox("Operator", ["gt", "gte", "lt", "lte"])
        with rc5:
            rule_threshold = st.number_input("Threshold (%)", min_value=0.0, max_value=100.0, value=90.0, step=1.0)
        with rc6:
            rule_cooldown = st.number_input("Cooldown (min)", min_value=1, max_value=1440, value=15)

        rule_auto_ticket = st.checkbox("Auto-create ticket on trigger")
        rule_submitted = st.form_submit_button("Create Rule", use_container_width=False)

    st.markdown('</div>', unsafe_allow_html=True)

    if rule_submitted:
        if not rule_name.strip():
            st.error("Rule name is required.")
        else:
            _, cerr = client.create_alert_rule({
                "name": rule_name.strip(),
                "metric": rule_metric,
                "operator": rule_operator,
                "threshold": rule_threshold,
                "severity": rule_severity,
                "cooldown_minutes": rule_cooldown,
                "auto_create_ticket": rule_auto_ticket,
            })
            if cerr:
                st.error(f"Failed to create rule: {cerr}")
            else:
                st.success("Alert rule created!")
                st.rerun()
