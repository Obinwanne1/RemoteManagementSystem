"""AI Assistant sidebar widget — call render_ai_assistant() on any page."""
import streamlit as st
from utils.api_client import RMMClient

_ONBOARD_MSG = (
    "👋 **Welcome to Remote Management System!**\n\n"
    "I'm your AI navigation guide. I can help you find features and walk through steps on any page.\n\n"
    "**Important:** Always verify my suggestions before taking action — I can make mistakes.\n\n"
    "Try: *How do I add a new device?* or *What does a critical alert mean?*"
)


def render_ai_assistant(page_name: str = "Overview", context: dict = None) -> None:
    """Render the AI assistant panel at the bottom of the sidebar.

    Args:
        page_name: Human-readable name of the current page (must match keys in assistant.py).
        context:   Dict of live page data (device counts, alert counts, etc.) sent to the AI.
    """
    if context is None:
        context = {}

    token = st.session_state.get("access_token")
    if not token:
        return
    client = RMMClient(
        access_token=token,
        refresh_token=st.session_state.get("refresh_token", ""),
    )

    # ── Initialise session state ───────────────────────────────────────────────
    if "_ai_history" not in st.session_state:
        st.session_state["_ai_history"] = []
    if "_ai_open" not in st.session_state:
        st.session_state["_ai_open"] = False
    if "_ai_seen_onboard" not in st.session_state:
        st.session_state["_ai_seen_onboard"] = False
    if "_ai_suggested" not in st.session_state:
        st.session_state["_ai_suggested"] = []

    # ── First-login onboarding (auto-open on Overview) ────────────────────────
    if not st.session_state["_ai_seen_onboard"] and page_name == "Overview":
        st.session_state["_ai_open"] = True
        st.session_state["_ai_seen_onboard"] = True
        if not st.session_state["_ai_history"]:
            st.session_state["_ai_history"] = [{"role": "assistant", "content": _ONBOARD_MSG}]

    page_key = page_name.lower().replace(" ", "_").replace("/", "_")

    with st.sidebar:
        st.markdown(
            '<div style="border-top:1px solid #1A2E1A;margin:0.4rem 0 0.35rem"></div>',
            unsafe_allow_html=True,
        )

        # ── Toggle button ──────────────────────────────────────────────────────
        if st.session_state["_ai_open"]:
            toggle_label = "🤖 Hide AI Assistant"
        else:
            toggle_label = "🤖 AI Assistant"
        if st.button(toggle_label, use_container_width=True, key=f"ai_toggle_{page_key}"):
            st.session_state["_ai_open"] = not st.session_state["_ai_open"]
            st.rerun()

        if not st.session_state["_ai_open"]:
            return

        # ── Persistent disclaimer ──────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:0.68rem;color:#b0b0b0;text-align:center;'
            'padding:0.15rem 0 0.3rem;line-height:1.3">'
            '⚠️ AI may make mistakes. Verify before acting.</div>',
            unsafe_allow_html=True,
        )

        # ── Chat history ───────────────────────────────────────────────────────
        history = st.session_state["_ai_history"]
        if history:
            with st.container(height=260, border=False):
                for msg in history[-14:]:
                    with st.chat_message(msg["role"]):
                        if msg.get("warning"):
                            st.warning("Potentially destructive operation mentioned above — verify before executing.", icon="⚠️")
                        st.markdown(msg["content"])
        else:
            st.markdown(
                '<div style="color:#7EC87E;font-size:0.78rem;text-align:center;'
                'padding:0.6rem 0 0.4rem">Ask me anything about this page!</div>',
                unsafe_allow_html=True,
            )

        # ── Input form ─────────────────────────────────────────────────────────
        with st.form(key=f"ai_form_{page_key}", clear_on_submit=True):
            user_input = st.text_input(
                "AI input",
                label_visibility="collapsed",
                placeholder="Ask anything…",
                key=f"ai_text_{page_key}",
            )
            submitted = st.form_submit_button("Send →", use_container_width=True)

        if submitted and user_input.strip():
            _send_message(client, user_input.strip(), page_name, context)

        # ── Suggested quick actions ────────────────────────────────────────────
        suggested = st.session_state.get("_ai_suggested", [])
        if suggested:
            st.markdown(
                '<div style="font-size:0.68rem;color:#7EC87E;padding:0.1rem 0 0.05rem;'
                'font-weight:600;letter-spacing:0.05em">QUICK ACTIONS</div>',
                unsafe_allow_html=True,
            )
            for i, action in enumerate(suggested[:3]):
                if st.button(
                    action,
                    key=f"ai_sugg_{page_key}_{i}",
                    use_container_width=True,
                ):
                    st.session_state["_ai_suggested"] = []
                    _send_message(client, f"How do I: {action}?", page_name, context)

        # ── Clear button ───────────────────────────────────────────────────────
        if st.session_state["_ai_history"]:
            if st.button("Clear chat", key=f"ai_clear_{page_key}", use_container_width=False):
                st.session_state["_ai_history"] = []
                st.session_state["_ai_suggested"] = []
                st.rerun()


def _send_message(client, message: str, page_name: str, context: dict) -> None:
    """Send a message to the AI API, append result to history, rerun."""
    st.session_state["_ai_history"].append({"role": "user", "content": message})

    payload = {
        "message": message,
        "page": page_name,
        "context": context,
        "history": st.session_state["_ai_history"][:-1],
    }

    with st.spinner("Thinking…"):
        data, err = client._request("POST", "/api/assistant/chat", json=payload)

    if err or not data:
        reply = "⚠️ AI assistant is temporarily unavailable. Please try again."
        suggested = []
        contains_warning = False
    else:
        reply = data.get("reply") or "No response received."
        suggested = data.get("suggested_actions") or []
        contains_warning = bool(data.get("contains_warning"))

    st.session_state["_ai_history"].append({"role": "assistant", "content": reply, "warning": contains_warning})
    st.session_state["_ai_suggested"] = suggested
    st.rerun()
