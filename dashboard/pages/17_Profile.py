"""User Profile — avatar, password change + MFA setup/disable."""
import io
import streamlit as st
from utils.styles import inject_css, BRAND
from utils.auth import require_auth, current_user
from utils.nav import render_sidebar

st.set_page_config(page_title="Profile — RMM", layout="wide")
inject_css()

client = require_auth()
render_sidebar()
user = current_user() or {}

st.markdown(
    '<h1 style="margin:0">My Profile</h1>'
    '<p style="color:#6B7B6B;margin:2px 0 1rem;font-size:0.88rem">Account settings and security</p>',
    unsafe_allow_html=True,
)

CARD = (
    "background:#FFFFFF;border-radius:12px;padding:1.2rem 1.5rem;"
    "border:1px solid #DDE8DD;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:1rem"
)

col_left, col_right = st.columns([1, 1], gap="large")

# ═══════════════════════════════════════════════════════════════════════════════
# LEFT — Avatar + Account info + change password
# ═══════════════════════════════════════════════════════════════════════════════
with col_left:

    # ── Avatar card ─────────────────────────────────────────────────────────
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown("**Profile Picture**")

    avatar_data = user.get("avatar_data")
    full_name   = user.get("full_name") or ""
    initials    = "".join(p[0].upper() for p in full_name.split() if p)[:2] or "?"

    av_col, up_col = st.columns([1, 2], gap="medium")

    with av_col:
        _initials_html = (
            f"<div style='width:96px;height:96px;border-radius:50%;"
            f"background:{BRAND};display:flex;align-items:center;"
            f"justify-content:center;font-size:2rem;font-weight:700;"
            f"color:#FFFFFF;letter-spacing:0.05em'>{initials}</div>"
        )
        if avatar_data:
            # Strip the data URI prefix and decode for st.image
            try:
                import base64 as _b64
                b64_part = avatar_data.split(",", 1)[1]
                img_bytes = _b64.b64decode(b64_part)
                st.image(img_bytes, width=96)
            except Exception:
                st.markdown(_initials_html, unsafe_allow_html=True)
        else:
            st.markdown(_initials_html, unsafe_allow_html=True)

    with up_col:
        uploaded = st.file_uploader(
            "Upload new photo",
            type=["jpg", "jpeg", "png", "webp"],
            key="avatar_uploader",
            label_visibility="collapsed",
            help="JPEG, PNG or WebP — max 2 MB. Resized to 200×200.",
        )
        st.markdown(
            "<div style='font-size:0.78rem;color:#6B7B6B;margin-top:0.2rem'>"
            "JPEG · PNG · WebP &nbsp;·&nbsp; max 2 MB</div>",
            unsafe_allow_html=True,
        )
        if uploaded is not None:
            if st.button("Save Photo", key="avatar_save", type="primary"):
                with st.spinner("Uploading…"):
                    data, err = client.upload_avatar(uploaded.read(), uploaded.type)
                if err:
                    st.error(f"Upload failed: {err}")
                else:
                    st.session_state["user"] = data["user"]
                    st.success("Profile photo updated.")
                    st.rerun()

        if avatar_data:
            if st.button("Remove Photo", key="avatar_remove"):
                with st.spinner("Removing…"):
                    data, err = client.delete_avatar()
                if err:
                    st.error(f"Failed: {err}")
                else:
                    st.session_state["user"] = data["user"]
                    st.success("Photo removed.")
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Account info card ────────────────────────────────────────────────────
    role = user.get("role", "")
    _pill = {
        "superadmin": ("#7C3AED", "#F3F0FF"),
        "admin":      ("#EF4444", "#FEF2F2"),
        "technician": ("#F59E0B", "#FFFBEB"),
        "viewer":     ("#22C55E", "#F0FDF4"),
    }
    pc, pb = _pill.get(role, ("#8492A6", "#F8FAFC"))

    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown("**Account**")
    st.markdown(
        f"<div style='margin:0.75rem 0'>"
        f"<div style='font-size:0.82rem;color:#6B7B6B;margin-bottom:2px'>Full name</div>"
        f"<div style='font-weight:600'>{full_name or '—'}</div>"
        f"</div>"
        f"<div style='margin:0.75rem 0'>"
        f"<div style='font-size:0.82rem;color:#6B7B6B;margin-bottom:2px'>Email</div>"
        f"<div style='font-weight:600'>{user.get('email','')}</div>"
        f"</div>"
        f"<div style='margin:0.75rem 0'>"
        f"<div style='font-size:0.82rem;color:#6B7B6B;margin-bottom:2px'>Role</div>"
        f"<span style='background:{pb};color:{pc};padding:3px 10px;border-radius:20px;"
        f"font-size:0.72rem;font-weight:700'>{role.upper()}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Change password card ─────────────────────────────────────────────────
    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown("**Change Password**")
    with st.form("change_pw_form"):
        cur_pw  = st.text_input("Current password", type="password")
        new_pw  = st.text_input("New password", type="password", placeholder="Min 8 characters")
        conf_pw = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update Password", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if not cur_pw:
            st.error("Enter your current password.")
        elif len(new_pw) < 8:
            st.error("New password must be at least 8 characters.")
        elif new_pw != conf_pw:
            st.error("Passwords do not match.")
        else:
            _, err = client.change_password(cur_pw, new_pw)
            if err:
                st.error(f"Failed: {err}")
            else:
                st.success("Password updated.")

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT — MFA
# ═══════════════════════════════════════════════════════════════════════════════
with col_right:
    mfa_enabled = user.get("mfa_enabled", False)

    st.markdown(f"<div style='{CARD}'>", unsafe_allow_html=True)
    st.markdown("**Two-Factor Authentication (MFA)**")

    if mfa_enabled:
        st.markdown(
            "<span style='background:#F0FDF4;color:#16A34A;padding:3px 10px;"
            "border-radius:20px;font-size:0.75rem;font-weight:700'>● ENABLED</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#6B7B6B;font-size:0.85rem;margin:0.75rem 0'>"
            "MFA is active. Enter your password to disable it.</p>",
            unsafe_allow_html=True,
        )
        with st.form("mfa_disable_form"):
            dis_pw = st.text_input("Current password", type="password", key="mfa_dis_pw")
            dis_sub = st.form_submit_button("Disable MFA", use_container_width=True, type="primary")

        if dis_sub:
            if not dis_pw:
                st.error("Password required.")
            else:
                _, err = client.mfa_disable(dis_pw)
                if err:
                    st.error(f"Failed: {err}")
                else:
                    udata, _ = client.get_me()
                    if udata:
                        st.session_state["user"] = udata
                    st.success("MFA disabled.")
                    st.rerun()

    else:
        st.markdown(
            "<span style='background:#FEF2F2;color:#DC2626;padding:3px 10px;"
            "border-radius:20px;font-size:0.75rem;font-weight:700'>● DISABLED</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#6B7B6B;font-size:0.85rem;margin:0.75rem 0'>"
            "Protect your account with a TOTP authenticator app "
            "(Google Authenticator, Authy, 1Password, etc.).</p>",
            unsafe_allow_html=True,
        )

        step = st.session_state.get("_mfa_setup_step", 0)

        if step == 0:
            if st.button("Enable MFA", use_container_width=True, type="primary", key="mfa_start"):
                with st.spinner("Generating secret…"):
                    data, err = client.mfa_setup()
                if err:
                    st.error(f"Failed: {err}")
                else:
                    st.session_state["_mfa_setup_secret"] = data["secret"]
                    st.session_state["_mfa_setup_uri"]    = data["provisioning_uri"]
                    st.session_state["_mfa_setup_step"]   = 1
                    st.rerun()

        elif step == 1:
            uri    = st.session_state.get("_mfa_setup_uri", "")
            secret = st.session_state.get("_mfa_setup_secret", "")

            try:
                import qrcode
                qr  = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#0F1B10", back_color="#FFFFFF")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                st.image(buf, caption="Scan with your authenticator app", width=220)
            except Exception:
                st.info("Install `qrcode[pil]` to display QR code.")
                st.code(uri, language=None)

            st.markdown(
                f"<div style='background:#F8FAF8;border:1px solid #DDE8DD;border-radius:8px;"
                f"padding:0.6rem 0.9rem;margin:0.5rem 0;font-size:0.82rem'>"
                f"<span style='color:#6B7B6B'>Manual entry key:</span><br>"
                f"<code style='font-size:0.9rem;font-weight:700;letter-spacing:0.08em'>{secret}</code>"
                f"</div>",
                unsafe_allow_html=True,
            )

            with st.form("mfa_verify_form"):
                code = st.text_input("Enter 6-digit code from app", placeholder="123456", max_chars=6)
                col_a, col_b = st.columns(2)
                with col_a:
                    verify_sub = st.form_submit_button("Activate MFA", use_container_width=True, type="primary")
                with col_b:
                    cancel_sub = st.form_submit_button("Cancel", use_container_width=True)

            if cancel_sub:
                for k in ("_mfa_setup_step", "_mfa_setup_secret", "_mfa_setup_uri"):
                    st.session_state.pop(k, None)
                st.rerun()

            if verify_sub:
                if not code or len(code) != 6 or not code.isdigit():
                    st.error("Enter a valid 6-digit code.")
                else:
                    _, err = client.mfa_enable(code)
                    if err:
                        st.error(f"Invalid code: {err}")
                    else:
                        for k in ("_mfa_setup_step", "_mfa_setup_secret", "_mfa_setup_uri"):
                            st.session_state.pop(k, None)
                        udata, _ = client.get_me()
                        if udata:
                            st.session_state["user"] = udata
                        st.success("MFA enabled! You'll need your authenticator app on next login.")
                        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
