"""Reports — Generate and download system reports."""
import streamlit as st
from datetime import date, timedelta

from utils.auth import require_auth
from utils.styles import inject_css, badge, BRAND, stat_card
from utils.formatters import fmt_datetime, fmt_bytes

st.set_page_config(page_title="Reports — RMM", layout="wide")
inject_css()

client = require_auth()

st.markdown('<h1 style="margin:0">Reports</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Generate and download system reports</p>', unsafe_allow_html=True)

# ── Load customers for selector ───────────────────────────────────────────────
cust_data, cust_err = client.list_customers(per_page=100)
customers = cust_data.get("items", []) if cust_data else []
cust_map = {c["name"]: c["id"] for c in customers}
cust_names = ["All Customers"] + list(cust_map.keys())

TEMPLATE_TYPES = {
    "Device Health Summary":  "device_health",
    "Patch Compliance":       "patch_compliance",
    "Alert Summary":          "alert_summary",
    "Software Inventory":     "software_inventory",
}

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_gen, tab_hist = st.tabs(["Generate Report", "Report History"])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Generate
# ══════════════════════════════════════════════════════════════════════════════
with tab_gen:
    st.markdown('<div style="height:0.25rem"></div>', unsafe_allow_html=True)

    form_col, info_col = st.columns([2, 1])

    with form_col:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;'
            'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem">',
            unsafe_allow_html=True
        )

        with st.form("generate_report_form"):
            st.markdown('<div style="font-size:0.9rem;font-weight:700;color:#1A2B1A;margin-bottom:0.75rem">Report Parameters</div>', unsafe_allow_html=True)

            template_label = st.selectbox("Report Type", list(TEMPLATE_TYPES.keys()))
            customer_label = st.selectbox("Customer", cust_names)

            dr_col1, dr_col2 = st.columns(2)
            with dr_col1:
                date_start = st.date_input("From", value=date.today() - timedelta(days=30))
            with dr_col2:
                date_end = st.date_input("To", value=date.today())

            submitted = st.form_submit_button("Generate Report", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if submitted:
            if date_end < date_start:
                st.error("End date must be after start date.")
            else:
                payload = {
                    "template_type":    TEMPLATE_TYPES[template_label],
                    "customer_id":      cust_map.get(customer_label) if customer_label != "All Customers" else None,
                    "date_range_start": date_start.isoformat(),
                    "date_range_end":   date_end.isoformat(),
                }
                with st.spinner("Generating report..."):
                    result, err = client.generate_report(payload)
                if err:
                    st.error(f"Report generation failed: {err}")
                else:
                    st.success(
                        f"Report generated successfully. "
                        f"Navigate to **Report History** to download it."
                    )

    with info_col:
        st.markdown(
            '<div style="background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;'
            'border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05)">'
            '<div style="font-size:0.85rem;font-weight:700;color:#1A2B1A;margin-bottom:0.6rem">Available Report Types</div>'
            '<div style="font-size:0.82rem;color:#4A5A4A;line-height:1.8">'
            '<b>Device Health Summary</b> — CPU, RAM, disk usage per device<br>'
            '<b>Patch Compliance</b> — Pending and applied patches per device<br>'
            '<b>Alert Summary</b> — Triggered alerts by severity and status<br>'
            '<b>Software Inventory</b> — All installed software across fleet'
            '</div></div>',
            unsafe_allow_html=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — History
# ══════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.markdown('<div style="height:0.25rem"></div>', unsafe_allow_html=True)

    reports_data, reports_err = client.list_reports()
    if reports_err:
        st.error(f"Could not load report history: {reports_err}")
        st.stop()

    reports = reports_data if isinstance(reports_data, list) else []

    if not reports:
        st.markdown(
            '<div style="text-align:center;padding:3rem;background:#FFFFFF;border-radius:12px;'
            'border:1px solid #DDE8DD;color:#6B7B6B">'
            '<div style="font-size:2.5rem;margin-bottom:0.75rem">📄</div>'
            '<div style="font-size:1rem;font-weight:600;color:#1A2B1A;margin-bottom:0.4rem">No reports yet</div>'
            '<div style="font-size:0.85rem">Generate your first report from the Generate tab.</div>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(f'<div style="font-size:0.78rem;color:#6B7B6B;margin-bottom:0.6rem">{len(reports)} report{"s" if len(reports) != 1 else ""} in history</div>', unsafe_allow_html=True)

        # Reverse so newest first
        for rpt in reversed(reports):
            r_name     = rpt.get("name") or "Unnamed Report"
            r_type     = (rpt.get("template_type") or "—").replace("_", " ").title()
            r_cust_id  = rpt.get("customer_id") or ""
            r_gen_at   = fmt_datetime(rpt.get("generated_at") or "")
            r_file     = rpt.get("file_path") or ""

            # Resolve customer name
            cust_name = next((c["name"] for c in customers if str(c["id"]) == str(r_cust_id)), r_cust_id or "All")

            row_l, row_r = st.columns([4, 1])
            with row_l:
                st.markdown(
                    f'<div style="background:#FFFFFF;border-radius:10px;padding:0.9rem 1.2rem;'
                    f'border:1px solid #DDE8DD;box-shadow:0 1px 4px rgba(0,0,0,0.04)">'
                    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">'
                    f'<span style="font-weight:600;color:#1A1A1A;font-size:0.9rem">{r_name}</span>'
                    f'{badge(r_type, BRAND["primary"])}'
                    f'</div>'
                    f'<div style="font-size:0.78rem;color:#6B7B6B">'
                    f'Customer: <b style="color:#4A5A4A">{cust_name}</b>'
                    f' &nbsp;·&nbsp; Generated: <b style="color:#4A5A4A">{r_gen_at}</b>'
                    f'</div></div>',
                    unsafe_allow_html=True
                )
            with row_r:
                if r_file:
                    try:
                        with open(r_file, "rb") as fh:
                            file_bytes = fh.read()
                        fname = r_file.split("/")[-1].split("\\")[-1]
                        st.download_button(
                            label="⬇ Download",
                            data=file_bytes,
                            file_name=fname,
                            mime="application/octet-stream",
                            key=f"dl_{rpt.get('id', r_name)}",
                            use_container_width=True,
                        )
                    except Exception:
                        st.button("⬇ Download", disabled=True, key=f"dl_dis_{rpt.get('id', r_name)}", use_container_width=True)
                else:
                    st.button("⬇ Download", disabled=True, key=f"dl_none_{rpt.get('id', r_name)}", use_container_width=True)
