"""Client Ticket Portal — clients submit and track their own tickets (list view)."""
import io
import streamlit as st
from utils.auth import require_auth, logout
from utils.ai_assistant import render_ai_assistant
from utils.styles import inject_css, badge, BRAND
from utils.formatters import fmt_datetime, PRIORITY_COLORS
from utils.sanitize import esc

_MDM_CONSENT_TEXT = (
    "By enrolling your phone, a lightweight management profile from Google (a \"Work Profile\") "
    "is added to your device — no separate app is installed by us. We will be able to see: the "
    "work profile's apps and compliance status. We will be able to act on: locking the device, "
    "putting it in Lost Mode, and — only as a last resort, with your knowledge — wiping the work "
    "profile if the device is lost or you leave. We cannot see or touch anything outside the work "
    "profile: your personal messages, photos, browsing, or other apps. You can remove the work "
    "profile at any time from your phone's Settings, or ask us to revoke it — either way your "
    "personal data on the phone is never affected."
)

_TABLE_CSS = """
<style>
.bp{display:inline-block;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;white-space:nowrap;line-height:1.7}
.bp-critical{background:#FEE2E2;color:#DC2626}
.bp-high{background:#FEF3C7;color:#D97706}
.bp-medium{background:#DBEAFE;color:#2563EB}
.bp-low{background:#F3F4F6;color:#6B7B6B}
.bs{display:inline-block;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;white-space:nowrap;line-height:1.7}
.bs-open{background:#FEE2E2;color:#DC2626}
.bs-in_progress{background:#FEF3C7;color:#D97706}
.bs-resolved{background:#DCFCE7;color:#16A34A}
.bs-closed{background:#F3F4F6;color:#6B7B6B}
.tbl-sep{border:none;border-top:2px solid #407E3C;margin:4px 0 6px}
.tbl-row-sep{border:none;border-top:1px solid #EEF2EE;margin:2px 0}
</style>
"""

# Column widths for client table (simpler — no Source/Assignee/SLA)
_COL_W   = [0.55, 2.8, 1.0, 1.0, 1.1, 0.45]
_COL_HDR = ["#", "Subject", "Priority", "Status", "Submitted", ""]

st.set_page_config(page_title="My Tickets — Support Portal", layout="wide")
inject_css()
st.markdown(_TABLE_CSS, unsafe_allow_html=True)

api = require_auth()
me = st.session_state.get("user", {})
role = me.get("role", "")
my_name = me.get("full_name") or me.get("email", "Client")

# Staff land here by mistake → redirect
if role not in ("client",):
    st.switch_page("pages/02_Tickets.py")

# ── Minimal header ────────────────────────────────────────────────────────────
hdr_c, signout_c = st.columns([8, 1])
with hdr_c:
    st.markdown(
        '<div style="display:flex;align-items:baseline;gap:0.75rem;'
        'border-bottom:2px solid #407E3C;padding-bottom:0.6rem;margin-bottom:1.25rem">'
        '<span style="font-size:1.4rem;font-weight:800;color:#407E3C">Support Portal</span>'
        '<span style="font-size:0.8rem;color:#6B7B6B">Submit and track your tickets</span>'
        f'<span style="font-size:0.8rem;color:#9CA3AF;margin-left:auto">'
        f'Logged in as <b style="color:#1A1A1A">{esc(my_name)}</b></span>'
        "</div>",
        unsafe_allow_html=True,
    )
with signout_c:
    if st.button("Sign Out", key="client_signout"):
        logout()

# ── New Ticket form ───────────────────────────────────────────────────────────
with st.expander("+ Submit New Ticket", expanded=False):
    with st.form("client_new_ticket", clear_on_submit=True):
        nt_title    = st.text_input("Subject *", placeholder="Brief description of your issue")
        nt_priority = st.selectbox("Priority", ["low", "medium", "high", "critical"])
        nt_desc     = st.text_area("Details", placeholder="Please describe your issue in full…", height=120)
        nt_submit   = st.form_submit_button("Submit Ticket", width='stretch')
    if nt_submit:
        if not nt_title.strip():
            st.error("Subject is required.")
        else:
            _, terr = api.create_ticket({
                "title": nt_title.strip(),
                "description": nt_desc.strip() or None,
                "priority": nt_priority,
            })
            if terr:
                st.error(f"Could not submit ticket: {terr}")
            else:
                st.success("Ticket submitted. Our team will review it shortly.")
                st.rerun()

# ── Enroll My Phone (BYOD, consent-gated) ──────────────────────────────────────
with st.expander("+ Enroll My Phone", expanded=False):
    available, _aerr = api.list_available_mdm_integrations()
    available = available or []
    if not available:
        st.info("Your provider hasn't set up mobile device management yet.")
    else:
        st.markdown(
            f"<div style='background:#F8FAF8;border:1px solid #DDE8DD;border-radius:8px;"
            f"padding:0.75rem 1rem;font-size:0.82rem;color:#3A4A3A;margin-bottom:0.75rem'>"
            f"{_MDM_CONSENT_TEXT}</div>",
            unsafe_allow_html=True,
        )
        int_ids = [i["id"] for i in available]
        int_labels = [i["name"] for i in available]
        chosen = st.selectbox("Provider integration", range(len(int_ids)), format_func=lambda x: int_labels[x])
        consent = st.checkbox("I understand and consent to enrolling my phone as described above.")

        if st.button("Generate enrollment QR", icon=":material/qr_code:", disabled=not consent):
            result, e = api.create_mdm_enrollment(
                int_ids[chosen], ownership_type="byod", consent_acknowledged=True,
            )
            if e:
                st.error(f"Could not start enrollment: {e}")
            else:
                st.session_state["_mdm_client_enrollment"] = result

        pending = st.session_state.get("_mdm_client_enrollment")
        if pending:
            st.success("Scan this on your phone's setup screen, or tap the link below if you're viewing this on the phone.")
            try:
                import qrcode
                qr = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(pending["qr_code_json"])
                qr.make(fit=True)
                img = qr.make_image(fill_color="#0F1B10", back_color="#FFFFFF")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                st.image(buf, width=220)
            except Exception:
                pass
            st.link_button("Open enrollment link on this phone", pending.get("enrollment_link", ""))

# ── Filter bar ────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="background:#FFF;border-radius:10px;padding:0.9rem 1.1rem;'
    'border:1px solid #DDE8DD;margin-bottom:1rem">',
    unsafe_allow_html=True,
)
ff1, ff2 = st.columns([3, 1.5])
with ff1:
    search_q = st.text_input("Search", placeholder="Search tickets…", label_visibility="collapsed")
with ff2:
    status_f = st.selectbox(
        "Status", ["All", "open", "in_progress", "resolved", "closed"],
        label_visibility="collapsed",
    )
st.markdown("</div>", unsafe_allow_html=True)

# ── Load tickets ──────────────────────────────────────────────────────────────
with st.spinner("Loading your tickets…"):
    data, err = api.list_tickets()

if err:
    st.warning(f"Could not load tickets — {err}")
    st.stop()

tickets = data.get("items", []) if data else []

if search_q:
    q = search_q.lower()
    tickets = [t for t in tickets if q in t.get("title", "").lower()
               or q in (t.get("description") or "").lower()]
if status_f != "All":
    tickets = [t for t in tickets if t.get("status") == status_f]

st.caption(f"{len(tickets)} ticket{'s' if len(tickets) != 1 else ''}")

if not tickets:
    st.markdown(
        '<div style="background:#FFFFFF;border-radius:12px;padding:2.5rem 1.5rem;'
        'border:1px solid #DDE8DD;text-align:center;margin-top:1rem">'
        '<div style="font-size:0.95rem;font-weight:600;color:#6B7B6B">No tickets yet</div>'
        '<div style="font-size:0.82rem;color:#9CA3AF;margin-top:0.25rem">'
        'Use "Submit New Ticket" above to report an issue.</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Table header ──────────────────────────────────────────────────────────────
hcols = st.columns(_COL_W)
for i, lbl in enumerate(_COL_HDR):
    with hcols[i]:
        if lbl:
            st.markdown(
                f'<span style="font-size:0.72rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:0.05em;color:#4B6349">{lbl}</span>',
                unsafe_allow_html=True,
            )

st.markdown('<hr class="tbl-sep">', unsafe_allow_html=True)

# ── Ticket rows ───────────────────────────────────────────────────────────────
for t in tickets:
    tid          = t["id"]
    priority_val = t.get("priority", "medium")
    status_val   = t.get("status", "open")
    created_fmt  = fmt_datetime(t.get("created_at", ""))
    status_disp  = status_val.replace("_", " ").upper()

    rcols = st.columns(_COL_W)
    with rcols[0]:
        st.markdown(
            f'<span style="font-size:0.8rem;color:#6B7B6B;font-weight:600">#{str(tid)[:8]}</span>',
            unsafe_allow_html=True,
        )
    with rcols[1]:
        st.markdown(
            f'<span style="font-size:0.84rem;color:#1A1A1A;font-weight:500">'
            f'{esc(t.get("title", "Untitled"))}</span>',
            unsafe_allow_html=True,
        )
    with rcols[2]:
        st.markdown(
            f'<span class="bp bp-{priority_val}">{priority_val.upper()}</span>',
            unsafe_allow_html=True,
        )
    with rcols[3]:
        st.markdown(
            f'<span class="bs bs-{status_val}">{status_disp}</span>',
            unsafe_allow_html=True,
        )
    with rcols[4]:
        st.markdown(
            f'<span style="font-size:0.78rem;color:#9CA3AF">{created_fmt}</span>',
            unsafe_allow_html=True,
        )
    with rcols[5]:
        if st.button("→", key=f"view_client_{tid}", width='stretch'):
            st.session_state["_nav_ticket_id"] = tid
            st.switch_page("pages/_client_ticket_detail.py")

    st.markdown('<hr class="tbl-row-sep">', unsafe_allow_html=True)

render_ai_assistant("Client Tickets", {"context": "navigation_only"})
