"""
Automation Profiles page — matches the reference screenshot layout:
4 columns: OS Patch Management | Software Patch Management | Disk Management | Maintenance
Plus: schedule config, scripts, email notifications.
"""
import streamlit as st
from utils.auth import require_auth
from utils.nav import render_sidebar
from utils.formatters import fmt_datetime
from utils.styles import inject_css, badge, BRAND, stat_card

st.set_page_config(page_title="Automation — RMM", layout="wide")
inject_css()

st.markdown('<h1 style="margin:0">Automation Profiles</h1><p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Schedule and manage automated maintenance tasks across devices</p>', unsafe_allow_html=True)

client = require_auth()
render_sidebar()

CARD = "background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem"

tab1, tab2 = st.tabs(["Profile List", "Create / Edit Profile"])

with tab1:
    data, err = client.list_profiles()
    if err:
        st.error(f"API error: {err}")
    else:
        if not data:
            st.info("No automation profiles. Create one to get started.")
        for profile in data:
            is_active = profile.get("is_active", False)
            status_dot = f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{"#22C55E" if is_active else "#8492A6"};margin-right:6px;vertical-align:middle"></span>'
            status_label = "Active" if is_active else "Inactive"
            status_color = "#22C55E" if is_active else "#8492A6"
            sched = profile.get("schedule_type", "—").capitalize()
            last_run = fmt_datetime(profile.get("last_run_at"))
            name_html = (
                f'<div style="{CARD}">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">'
                f'<div style="display:flex;align-items:center;gap:0.6rem">'
                f'{status_dot}'
                f'<span style="font-weight:700;font-size:1rem;color:#1A1A1A">{profile["name"]}</span>'
                f'<span style="background:{status_color}1A;color:{status_color};padding:2px 9px;border-radius:20px;font-size:0.72rem;font-weight:700;border:1px solid {status_color}33">{status_label.upper()}</span>'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:1.5rem">'
                f'<span style="font-size:0.82rem;color:#6B7B6B">Schedule: <b style="color:#1A1A1A">{sched}</b></span>'
                f'<span style="font-size:0.82rem;color:#6B7B6B">Last run: <b style="color:#1A1A1A">{last_run}</b></span>'
                f'</div>'
                f'</div></div>'
            )
            col_card, col_btn = st.columns([6, 1])
            with col_card:
                st.markdown(name_html, unsafe_allow_html=True)
            with col_btn:
                st.markdown('<div style="margin-top:0.6rem"></div>', unsafe_allow_html=True)
                if st.button("▶ Run Now", key=f"run_{profile['id']}"):
                    result, run_err = client.run_profile_now(profile["id"])
                    if run_err:
                        st.error(run_err)
                    else:
                        msg = result.get("message", "")
                        if "skipping duplicate" in msg:
                            st.warning("Run already queued — ignoring duplicate click.")
                        else:
                            st.success(f"Profile queued successfully.")
                        st.rerun()


with tab2:
    st.subheader("Edit Automation Profile")

    # Profile selector
    profiles_data, _ = client.list_profiles()
    profiles = profiles_data or []
    profile_names = ["— New Profile —"] + [p["name"] for p in profiles]
    selected = st.selectbox("Select profile to edit (or create new)", profile_names)

    existing = None
    if selected != "— New Profile —":
        existing = next((p for p in profiles if p["name"] == selected), None)

    # --- Profile Header ---
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("Profile Name *", value=existing["name"] if existing else "")
    with col2:
        is_active = st.checkbox("Active", value=existing["is_active"] if existing else True)
    with col3:
        run_on_new = st.checkbox(
            "Run on newly installed agents",
            value=existing.get("run_on_new_agents", False) if existing else False
        )

    # --- Schedule ---
    st.subheader("Schedule Automation")
    col1, col2, col3 = st.columns(3)
    with col1:
        sched_type = st.selectbox(
            "Run profile",
            ["weekly", "daily", "monthly", "once"],
            index=["weekly", "daily", "monthly", "once"].index(
                existing["schedule_type"] if existing else "weekly"
            )
        )
    with col2:
        sched_day = st.selectbox("Day", ["monday", "tuesday", "wednesday", "thursday",
                                          "friday", "saturday", "sunday"])
    with col3:
        sched_time = st.time_input("Time", value=None)

    email_input = st.text_input(
        "Send email to (comma-separated)",
        value=", ".join(existing.get("notification_emails", [])) if existing else ""
    )

    # --- Task Configuration (4-column layout) ---
    st.subheader("Task")
    st.divider()

    os_cfg = existing.get("os_patch_config", {}) if existing else {}
    sw_cfg = existing.get("software_patch_config", {}) if existing else {}
    disk_cfg = existing.get("disk_config", {}) if existing else {}
    maint_cfg = existing.get("maintenance_config", {}) if existing else {}

    col_os, col_sw, col_disk, col_maint = st.columns(4)

    # NinjaOne-style dark header per column
    col_header_style = "background:#1A2B1A;color:#FFFFFF;border-radius:8px 8px 0 0;padding:0.55rem 0.9rem;font-size:0.82rem;font-weight:700;letter-spacing:0.04em;margin-bottom:0.75rem"

    with col_os:
        st.markdown(f'<div style="{col_header_style}">OS PATCH MANAGEMENT</div>', unsafe_allow_html=True)
        os_enabled = st.checkbox("Install all Windows patch updates",
                                 value=os_cfg.get("enabled", False), key="os_enabled")
        if os_enabled:
            st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">CRITICAL UPDATES</span>', unsafe_allow_html=True)
            os_critical = st.checkbox("Critical updates", value=os_cfg.get("critical", True), key="os_crit")
            st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">SECURITY UPDATES</span>', unsafe_allow_html=True)
            os_security = st.checkbox("Security updates", value=os_cfg.get("security", True), key="os_sec")
            os_def = st.checkbox("Definition updates", value=os_cfg.get("definitions", True), key="os_def")
            os_roll = st.checkbox("Update rollups", value=os_cfg.get("rollups", False), key="os_roll")
            st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">SERVICE PACKS</span>', unsafe_allow_html=True)
            os_sp = st.checkbox("Service pack updates", value=os_cfg.get("service_packs", False), key="os_sp")
            os_feat = st.checkbox("Feature packs", value=os_cfg.get("feature_packs", False), key="os_feat")
            os_upd = st.checkbox("Updates", value=os_cfg.get("updates", True), key="os_upd")
            st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">DRIVERS & TOOLS</span>', unsafe_allow_html=True)
            os_hw = st.checkbox("Hardware driver updates", value=os_cfg.get("drivers", False), key="os_hw")
            os_off = st.checkbox("Office updates", value=os_cfg.get("office", False), key="os_off")
            os_tool = st.checkbox("Tool updates", value=os_cfg.get("tools", False), key="os_tool")
        else:
            os_critical = os_security = os_def = os_roll = False
            os_sp = os_feat = os_upd = os_hw = os_off = os_tool = False

    with col_sw:
        st.markdown(f'<div style="{col_header_style}">SOFTWARE PATCH MANAGEMENT</div>', unsafe_allow_html=True)
        sw_update_all = st.checkbox("Update All", value=sw_cfg.get("update_all", False), key="sw_all")
        st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">EXCLUDED SOFTWARE PATCHES</span>', unsafe_allow_html=True)
        excluded_raw = st.text_area(
            "One per line",
            value="\n".join(sw_cfg.get("excluded", [])),
            height=80, key="sw_excl",
            label_visibility="collapsed"
        )
        st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">SOFTWARE BUNDLE</span>', unsafe_allow_html=True)
        bundle_raw = st.text_input("Bundle name", value=", ".join(sw_cfg.get("bundles", [])), key="sw_bundle")
        st.markdown('<span style="font-size:0.78rem;color:#6B7B6B;font-weight:600">UPGRADES</span>', unsafe_allow_html=True)
        sw_upgrade_os = st.checkbox("Upgrade Windows 10 (latest build)",
                                    value=sw_cfg.get("upgrade_os", False), key="sw_upgrade")

    with col_disk:
        st.markdown(f'<div style="{col_header_style}">DISK MANAGEMENT</div>', unsafe_allow_html=True)
        disk_defrag = st.checkbox("Defragment (All disks)",
                                  value=disk_cfg.get("defrag", False), key="disk_defrag")
        disk_check = st.checkbox("Run Checkdisk (All disks)",
                                 value=disk_cfg.get("checkdisk", False), key="disk_check")

    with col_maint:
        st.markdown(f'<div style="{col_header_style}">MAINTENANCE</div>', unsafe_allow_html=True)
        maint_restore = st.checkbox("Create System Restore Point",
                                    value=maint_cfg.get("restore_point", False), key="m_restore")
        maint_temp = st.checkbox("Delete Temp Files",
                                 value=maint_cfg.get("delete_temp", False), key="m_temp")
        maint_hist = st.checkbox("Delete Internet History",
                                 value=maint_cfg.get("clear_history", False), key="m_hist")
        maint_reboot = st.checkbox("Reboot", value=maint_cfg.get("reboot", False), key="m_reboot")
        maint_shutdown = st.checkbox("Shutdown", value=maint_cfg.get("shutdown", False), key="m_shutdown")
        st.markdown(f'<div style="{col_header_style};margin-top:0.75rem">SCRIPTS</div>', unsafe_allow_html=True)
        # Script selector (Phase 4+)
        scripts_data, _ = client.list_scripts()
        scripts = scripts_data or []
        script_options = {s["name"]: s["id"] for s in scripts}
        selected_scripts = st.multiselect(
            "Attach scripts",
            list(script_options.keys()),
            default=[s["name"] for s in scripts
                     if s["id"] in (existing.get("scripts", []) if existing else [])]
        )

    st.divider()

    # --- Save / Delete buttons ---
    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
    with btn_col1:
        save = st.button("💾 Save Profile", type="primary")
    with btn_col2:
        if existing:
            disable_btn = st.button("Disable" if existing["is_active"] else "Enable")
        else:
            disable_btn = False
    with btn_col3:
        if existing:
            delete_btn = st.button("🗑️ Delete", type="secondary")
        else:
            delete_btn = False

    if save:
        if not name:
            st.error("Profile name required")
        else:
            emails = [e.strip() for e in email_input.split(",") if e.strip()]
            payload = {
                "name": name,
                "is_active": is_active,
                "run_on_new_agents": run_on_new,
                "schedule_type": sched_type,
                "schedule_config": {"day": sched_day, "time": str(sched_time) if sched_time else "01:00"},
                "notification_emails": emails,
                "os_patch_config": {
                    "enabled": os_enabled, "critical": os_critical,
                    "security": os_security, "definitions": os_def,
                    "rollups": os_roll, "service_packs": os_sp,
                    "feature_packs": os_feat, "updates": os_upd,
                    "drivers": os_hw, "office": os_off, "tools": os_tool,
                },
                "software_patch_config": {
                    "update_all": sw_update_all,
                    "excluded": [e.strip() for e in excluded_raw.splitlines() if e.strip()],
                    "bundles": [b.strip() for b in bundle_raw.split(",") if b.strip()],
                    "upgrade_os": sw_upgrade_os,
                },
                "disk_config": {"defrag": disk_defrag, "checkdisk": disk_check},
                "maintenance_config": {
                    "restore_point": maint_restore, "delete_temp": maint_temp,
                    "clear_history": maint_hist, "reboot": maint_reboot, "shutdown": maint_shutdown,
                },
                "scripts": [script_options[s] for s in selected_scripts],
            }
            if existing:
                _, err = client.update_profile(existing["id"], payload)
            else:
                _, err = client.create_profile(payload)

            if err:
                st.error(f"Failed: {err}")
            else:
                st.success("Profile saved!")
                st.rerun()
