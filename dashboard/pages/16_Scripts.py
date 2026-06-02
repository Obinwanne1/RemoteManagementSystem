import streamlit as st
from utils.auth import require_auth
from utils.formatters import fmt_datetime

st.set_page_config(page_title="Scripts — RMM", layout="wide")
st.title("📝 Scripts")

client = require_auth()

tab1, tab2, tab3 = st.tabs(["Script Library", "Upload Script", "Run History"])

with tab1:
    data, err = client.list_scripts()
    if err:
        st.error(f"API error: {err}")
    else:
        scripts = data or []
        st.caption(f"{len(scripts)} scripts")

        # Load devices for run modal
        dev_data, _ = client.list_devices(per_page=200)
        devices = dev_data.get("items", []) if dev_data else []
        device_options = {d["display_name"]: d["id"] for d in devices if d["is_online"]}

        for script in scripts:
            tag = "📌 Built-in" if script["is_builtin"] else "📝 Custom"
            with st.expander(f'{tag} **{script["name"]}** [{script["file_type"].upper()}]'):
                st.markdown(f"**Description:** {script.get('description') or '—'}")
                st.markdown(f"**OS:** {script['os_target']} | **Created:** {fmt_datetime(script['created_at'])}")

                st.markdown("**Run on devices:**")
                selected_devs = st.multiselect(
                    "Select online devices",
                    list(device_options.keys()),
                    key=f"devs_{script['id']}"
                )
                timeout = st.number_input("Timeout (seconds)", 10, 900, 300, key=f"to_{script['id']}")

                if st.button("▶ Run Script", key=f"run_{script['id']}"):
                    if not selected_devs:
                        st.warning("Select at least one device")
                    else:
                        device_ids = [device_options[d] for d in selected_devs]
                        result, err = client.run_script(script["id"], device_ids, timeout)
                        if err:
                            st.error(f"Failed: {err}")
                        else:
                            st.success(f"Queued on {result.get('queued',0)} device(s)")

with tab2:
    st.subheader("Upload New Script")
    with st.form("upload_script"):
        s_name = st.text_input("Script Name *")
        s_desc = st.text_area("Description")
        s_type = st.selectbox("Type", ["ps1", "bat", "py"])
        s_content = st.text_area("Script Content *", height=300,
                                  placeholder="Write your script here...")
        submitted = st.form_submit_button("Upload Script")

    if submitted:
        if not s_name or not s_content:
            st.error("Name and content required")
        else:
            _, err = client.create_script({
                "name": s_name,
                "description": s_desc,
                "file_type": s_type,
                "content": s_content,
            })
            if err:
                st.error(f"Failed: {err}")
            else:
                st.success("Script uploaded!")
                st.rerun()

with tab3:
    st.subheader("Script Run History")
    runs_data, err = client.list_script_runs(per_page=50)
    if err:
        st.error(f"API error: {err}")
    else:
        runs = runs_data.get("items", []) if runs_data else []
        if not runs:
            st.info("No script runs yet.")
        for run in runs:
            status_icon = {"success": "✅", "failed": "❌", "queued": "⏳",
                           "running": "🔄", "timeout": "⏰"}.get(run["status"], "❓")
            with st.expander(
                f'{status_icon} Script `{run["script_id"][:8]}...` on device `{run["device_id"][:8]}...` '
                f'— {run["status"]} — {fmt_datetime(run["triggered_at"])}'
            ):
                if run.get("stdout"):
                    st.markdown("**stdout:**")
                    st.code(run["stdout"], language="text")
                if run.get("stderr"):
                    st.markdown("**stderr:**")
                    st.code(run["stderr"], language="text")
                st.caption(f"Exit code: {run.get('exit_code','—')} | "
                           f"Duration: started {fmt_datetime(run.get('started_at'))} "
                           f"→ completed {fmt_datetime(run.get('completed_at'))}")
