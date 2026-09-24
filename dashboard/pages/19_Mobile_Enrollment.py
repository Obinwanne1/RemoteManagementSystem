"""Mobile Enrollment — set up Android Management API integrations and enroll phones.

No custom agent is ever installed on a phone here. Android devices run Google's
own signed "Android Device Policy" app, provisioned when the phone's owner scans
a QR code or opens an enrollment link — that consent step is required by Google
and by law (BYOD monitoring without consent), it is never silent.
"""
import io
import streamlit as st

from utils.auth import require_auth, current_user
from utils.nav import render_sidebar
from utils.styles import inject_css, badge
from utils.ai_assistant import render_ai_assistant

st.set_page_config(page_title="Mobile Enrollment — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()
_role = (current_user() or {}).get("role", "viewer")

if _role not in ("admin", "superadmin", "technician"):
    st.error("You don't have permission to view this page.")
    st.stop()

st.markdown(
    '<h1 style="margin:0">Mobile Enrollment</h1>'
    '<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">'
    'Manage phones on the WiFi network without installing a custom agent — real '
    'lock/wipe/lost-mode actions via Google\'s Android Management API</p>',
    unsafe_allow_html=True,
)

CARD = (
    "background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;"
    "border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem"
)

tab_android, tab_ios = st.tabs(["Android", "iOS"])

with tab_android:
    integrations, ierr = client.list_mdm_integrations()
    integrations = [i for i in (integrations or []) if i.get("type") == "android"]

    st.markdown(f'<div style="{CARD}">', unsafe_allow_html=True)
    st.markdown("##### Integrations")
    st.markdown(
        "<p style='color:#6B7B6B;font-size:0.82rem'>Each integration is a Google Cloud project + "
        "service account bound to one Android Enterprise. Setup steps (done once, outside this "
        "dashboard): create/select a GCP project, enable the Android Management API, create a "
        "service account and download its JSON key.</p>",
        unsafe_allow_html=True,
    )

    if not integrations:
        st.info("No Android MDM integrations configured yet.")
    for integ in integrations:
        bound = integ.get("bound")
        with st.expander(f"{integ['name']}  ·  {'Bound' if bound else 'Not bound'}  ·  {integ['project_id']}"):
            st.write(f"Enterprise: `{integ.get('enterprise_id') or '—'}`")
            if integ.get("sync_error"):
                st.error(f"Last sync error: {integ['sync_error']}")

            if not bound:
                st.markdown("**Step 1 — Upload service-account credentials**")
                up = st.file_uploader("Service account JSON key", type=["json"], key=f"cred_{integ['id']}")
                if up and st.button("Upload credentials", key=f"upload_{integ['id']}"):
                    _, e = client.upload_mdm_credentials(integ["id"], up.getvalue())
                    st.error(f"Failed: {e}") if e else st.success("Credentials stored (encrypted).")
                    if not e:
                        st.rerun()

                st.markdown("**Step 2 — Bind enterprise**")
                st.caption(
                    "Requires a stable HTTPS URL reachable from your browser for Google's "
                    "callback (a tunnel like ngrok works for initial testing — localhost will "
                    "not work). You'll be redirected to Google's own hosted business-signup page."
                )
                callback_base = st.text_input(
                    "Public HTTPS base URL for this API", placeholder="https://your-tunnel.example.com",
                    key=f"cb_{integ['id']}",
                )
                if st.button("Start binding", key=f"bind_{integ['id']}", disabled=not callback_base):
                    result, e = client.start_mdm_binding(integ["id"], callback_base)
                    if e:
                        st.error(f"Failed: {e}")
                    else:
                        st.success("Open this URL to complete binding in Google's own signup flow:")
                        st.code(result.get("signup_url", ""), language=None)
            else:
                st.markdown("**Default policy**")
                st.caption(
                    "The policy JSON controls what a managed device can do — passcode "
                    "requirements, allowed apps, kiosk mode, etc. See Google's Android "
                    "Management API policy reference for the full schema."
                )
                policy_json = st.text_area(
                    "Policy JSON", value='{\n  "passwordRequirements": {"passwordMinimumLength": 6}\n}',
                    height=120, key=f"policy_{integ['id']}",
                )
                if st.button("Push policy", key=f"pushpolicy_{integ['id']}"):
                    import json
                    try:
                        policy = json.loads(policy_json)
                    except ValueError as ve:
                        st.error(f"Invalid JSON: {ve}")
                        policy = None
                    if policy is not None:
                        _, e = client.update_mdm_policy(integ["id"], "default", policy)
                        st.error(f"Failed: {e}") if e else st.success("Policy pushed.")

            if st.button("Delete integration", key=f"delint_{integ['id']}", icon=":material/delete:"):
                _, e = client.delete_mdm_integration(integ["id"])
                st.error(f"Failed: {e}") if e else st.rerun()

    st.markdown("---")
    st.markdown("**Add integration**")
    with st.form("new_integration_form"):
        c1, c2 = st.columns(2)
        with c1:
            new_name = st.text_input("Name", placeholder="e.g. Acme Corp Android Fleet")
        with c2:
            new_project = st.text_input("Google Cloud project ID")
        cust_data, cust_err = client.list_customers(per_page=200)
        if cust_err:
            st.caption(f"⚠ Could not load customers — {cust_err}")
        customers = (cust_data or {}).get("items", [])
        cust_ids = [""] + [c["id"] for c in customers]
        cust_labels = ["— Staff-wide (no customer) —"] + [c["name"] for c in customers]
        new_cust_idx = st.selectbox("Scope", range(len(cust_ids)), format_func=lambda x: cust_labels[x])
        if st.form_submit_button("Create integration", width='stretch'):
            if not new_name or not new_project:
                st.error("Name and project ID are required.")
            else:
                _, e = client.create_mdm_integration(
                    new_name, new_project, customer_id=cust_ids[new_cust_idx] or None,
                )
                st.error(f"Failed: {e}") if e else st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Enrollment ───────────────────────────────────────────────────────────
    bound_integrations = [i for i in integrations if i.get("bound")]
    st.markdown(f'<div style="{CARD}">', unsafe_allow_html=True)
    st.markdown("##### Enroll a phone")
    if not bound_integrations:
        st.info("Bind an integration above before enrolling devices.")
    else:
        int_ids = [i["id"] for i in bound_integrations]
        int_labels = [i["name"] for i in bound_integrations]
        e1, e2, e3 = st.columns([2, 1.3, 1])
        with e1:
            chosen = st.selectbox("Integration", range(len(int_ids)), format_func=lambda x: int_labels[x])
        with e2:
            ownership = st.selectbox("Ownership", ["corporate", "byod"],
                                     format_func=lambda x: "Company-owned" if x == "corporate" else "BYOD (personal)")
        with e3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            consent = st.checkbox("Consent given", value=(ownership == "corporate"),
                                  help="Required for BYOD — the phone owner must have agreed to enrollment.")

        if st.button("Generate enrollment QR", icon=":material/qr_code:"):
            result, e = client.create_mdm_enrollment(
                int_ids[chosen], ownership_type=ownership, consent_acknowledged=consent,
            )
            if e:
                st.error(f"Failed: {e}")
            else:
                st.session_state["_mdm_last_enrollment"] = result

        pending = st.session_state.get("_mdm_last_enrollment")
        if pending:
            st.success(f"Enrollment token created — expires {pending.get('expires_at', '')}")
            try:
                import qrcode
                qr = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(pending["qr_code_json"])
                qr.make(fit=True)
                img = qr.make_image(fill_color="#0F1B10", back_color="#FFFFFF")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                st.image(buf, caption="Scan at the phone's setup/welcome screen", width=220)
            except Exception:
                st.info("Install `qrcode[pil]` to display a QR image.")
            st.caption("Or open this link directly on the phone:")
            st.code(pending.get("enrollment_link", ""), language=None)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Enrolled devices ─────────────────────────────────────────────────────
    st.markdown(f'<div style="{CARD}">', unsafe_allow_html=True)
    st.markdown("##### Enrollments")
    enrollments, enrollments_err = client.list_mdm_enrollments()
    if enrollments_err:
        st.caption(f"⚠ Could not load enrollments — {enrollments_err}")
    elif not enrollments:
        st.info("No enrollments yet.")
    for en in (enrollments or []):
        status = en.get("status", "pending")
        color = {"enrolled": "#22C55E", "pending": "#F59E0B", "revoked": "#8492A6", "wiped": "#EF4444"}.get(status, "#8492A6")
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(
                f"{badge(status.upper(), color)} &nbsp; {en.get('ownership_type', '').upper()} &nbsp; "
                f"consented {en.get('consent_given_at', '—')}",
                unsafe_allow_html=True,
            )
        with c2:
            if status in ("pending", "enrolled") and st.button("Revoke", key=f"revoke_{en['id']}"):
                _, e = client.revoke_mdm_enrollment(en["id"])
                st.error(f"Failed: {e}") if e else st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with tab_ios:
    st.markdown(f'<div style="{CARD}">', unsafe_allow_html=True)
    st.markdown("##### iOS management")
    st.info(
        "Not implemented yet. Real iOS MDM requires an Apple Push (APNs) certificate, which "
        "Apple only issues to organizations enrolled in **Apple Business Manager** or to an "
        "already vendor-signed MDM server. Two paths forward, both outside what this dashboard "
        "can complete for you:\n\n"
        "1. Enroll your organization in Apple Business Manager, then request an MDM push "
        "certificate through it.\n"
        "2. Integrate with an already vendor-signed open-source MDM server (e.g. "
        "[Fleet](https://fleetdm.com) or MicroMDM/NanoMDM) instead of implementing raw "
        "APNs signing.\n\n"
        "iPhones stay on passive network discovery (see the **Agentless / iOS** tab on the "
        "Devices page) until you decide which path to take — nothing about that today is broken "
        "or half-built, it's just not real management yet."
    )
    st.markdown('</div>', unsafe_allow_html=True)

render_ai_assistant("Mobile Enrollment", {})
