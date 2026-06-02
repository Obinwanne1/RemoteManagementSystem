import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="OS Patches — RMM", layout="wide")
st.title("🔧 OS Patch Management")

client = require_auth()

tab1, tab2, tab3 = st.tabs(["Pending Patches", "Patch History", "Policies"])

with tab1:
    summary, _ = client.get_patch_summary()
    if summary:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Pending", summary["pending"])
        col2.metric("Approved", summary["approved"])
        col3.metric("Deployed", summary["deployed"])
        col4.metric("Compliance", f"{summary['compliance_pct']}%")

    pending, err = client.get_pending_patches()
    if err:
        st.error(f"API error: {err}")
    elif not pending:
        st.success("No pending patches.")
    else:
        st.caption(f"{len(pending)} pending patches")
        selected_ids = []
        for patch in pending:
            checked = st.checkbox(
                f"**{patch['patch_name']}** [{patch.get('patch_type','?')}]"
                f" — KB{patch.get('kb_id','?')} — Device: `{patch['device_id'][:8]}`",
                key=f"patch_{patch['id']}"
            )
            if checked:
                selected_ids.append(patch["id"])

        if st.button(f"✅ Approve Selected ({len(selected_ids)})", type="primary"):
            if selected_ids:
                _, err = client.approve_patches(selected_ids)
                if err:
                    st.error(err)
                else:
                    st.success(f"Approved {len(selected_ids)} patches")
                    st.rerun()

with tab2:
    data, err = client.list_patches(per_page=100)
    if err:
        st.error(f"API error: {err}")
    else:
        patches = data.get("items", []) if data else []
        for p in patches:
            st.markdown(
                f"**{p['patch_name']}** | {p['status']} | {p.get('patch_type','?')} | "
                f"{fmt_datetime(p.get('deployed_at') or p['created_at'])}"
            )

with tab3:
    st.info("Patch policies — Phase 6 full implementation")
    policies, _ = client.list_patches()
