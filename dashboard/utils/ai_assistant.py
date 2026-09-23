"""AI Assistant sidebar widget — call render_ai_assistant() on any page.

Phase 3 refactor: history now hydrates from the server-side conversation store
(GET /api/assistant/conversation) instead of living only in st.session_state, so it
survives a page refresh; mutating tool calls surface as an approve/deny confirmation
card instead of executing silently; real error reasons (disabled/rate-limited/expired
session) are shown instead of one flattened message.
"""
import streamlit as st
from datetime import datetime
from utils.api_client import RMMClient

_ONBOARD_MSG = (
    "**Welcome to Remote Management System.**\n\n"
    "I'm your navigation assistant — I can help you find features, "
    "walk through workflows, and explain what you're seeing on any page.\n\n"
    "**Note:** Always verify my suggestions before taking action.\n\n"
    "Try: *How do I add a new device?* or *What does a critical alert mean?*"
)

_CHAT_CSS = """
<style>
[data-testid="stSidebar"] [data-testid="stChatMessage"] {
    background: rgba(20, 35, 20, 0.55);
    border-radius: 8px;
    margin-bottom: 2px;
    border: 1px solid rgba(64,126,60,0.15);
}
[data-testid="stSidebar"] [data-testid="stChatMessageContent"] p {
    font-size: 0.78rem;
    line-height: 1.5;
    margin-bottom: 0.35rem;
}
[data-testid="stSidebar"] [data-testid="stChatMessageContent"] ol,
[data-testid="stSidebar"] [data-testid="stChatMessageContent"] ul {
    font-size: 0.78rem;
    padding-left: 1.1rem;
}
</style>
"""


def render_ai_assistant(page_name: str = "Overview", context: dict = None) -> None:
    """Render the AI assistant panel at the bottom of the sidebar."""
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
    if "_ai_pending" not in st.session_state:
        st.session_state["_ai_pending"] = None
    if "_ai_history_loaded" not in st.session_state:
        st.session_state["_ai_history_loaded"] = False

    _hydrate_history(client)

    # ── First-login onboarding (auto-open on Overview) ────────────────────────
    if not st.session_state["_ai_seen_onboard"] and page_name == "Overview":
        st.session_state["_ai_open"] = True
        st.session_state["_ai_seen_onboard"] = True
        if not st.session_state["_ai_history"]:
            st.session_state["_ai_history"] = [
                {"role": "assistant", "content": _ONBOARD_MSG, "ts": _ts()}
            ]

    page_key = page_name.lower().replace(" ", "_").replace("/", "_")

    with st.sidebar:
        st.markdown(
            '<div style="border-top:1px solid #1A2E1A;margin:0.4rem 0 0.35rem"></div>',
            unsafe_allow_html=True,
        )

        # ── Toggle button ──────────────────────────────────────────────────────
        if st.session_state["_ai_open"]:
            if st.button(
                "Close Assistant",
                icon=":material/close:",
                width="stretch",
                key=f"ai_toggle_{page_key}",
            ):
                st.session_state["_ai_open"] = False
                st.rerun()
        else:
            if st.button(
                "AI Assistant",
                icon=":material/auto_awesome:",
                width="stretch",
                key=f"ai_toggle_{page_key}",
            ):
                st.session_state["_ai_open"] = True
                st.rerun()

        if not st.session_state["_ai_open"]:
            return

        # ── Inject chat styling ────────────────────────────────────────────────
        st.markdown(_CHAT_CSS, unsafe_allow_html=True)

        # ── Persistent disclaimer ──────────────────────────────────────────────
        st.markdown(
            '<div style="font-size:0.65rem;color:#8a9a8a;text-align:center;'
            'padding:0.1rem 0 0.25rem;line-height:1.3;letter-spacing:0.01em">'
            'AI may make mistakes — verify before acting</div>',
            unsafe_allow_html=True,
        )

        # ── Chat history ───────────────────────────────────────────────────────
        history = st.session_state["_ai_history"]
        if history:
            with st.container(height=280, border=False):
                for msg in history[-16:]:
                    with st.chat_message(msg["role"]):
                        if msg.get("warning"):
                            st.warning(
                                "Potentially destructive operation — verify before executing.",
                                icon="⚠️",
                            )
                        st.markdown(msg["content"])
                        if msg.get("ts"):
                            st.markdown(
                                f'<div style="font-size:0.6rem;color:#556655;'
                                f'margin-top:2px">{msg["ts"]}</div>',
                                unsafe_allow_html=True,
                            )
        else:
            st.markdown(
                '<div style="color:#5a7a5a;font-size:0.75rem;text-align:center;'
                'padding:0.8rem 0 0.5rem;border:1px dashed #1a3a1a;border-radius:8px;'
                'margin:0.25rem 0">Ask me anything about this page</div>',
                unsafe_allow_html=True,
            )

        # ── Pending action confirmation card ────────────────────────────────────
        pending = st.session_state.get("_ai_pending")
        if pending:
            with st.container(border=True):
                if pending.get("contains_warning"):
                    st.warning("Potentially destructive operation — review carefully before approving.", icon="⚠️")
                st.markdown(f"**Confirm action:** {pending.get('summary', pending.get('tool_name'))}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Approve", key=f"ai_approve_{page_key}", width="stretch", type="primary"):
                        _confirm_pending(client, pending["id"])
                with c2:
                    if st.button("Deny", key=f"ai_deny_{page_key}", width="stretch"):
                        _deny_pending(client, pending["id"])

        # ── Input form ─────────────────────────────────────────────────────────
        with st.form(key=f"ai_form_{page_key}", clear_on_submit=True):
            user_input = st.text_input(
                "Message",
                label_visibility="collapsed",
                placeholder="Ask anything about this page…",
                key=f"ai_text_{page_key}",
                max_chars=800,
            )
            submitted = st.form_submit_button(
                "Send",
                icon=":material/send:",
                width="stretch",
                type="primary",
            )

        if submitted and user_input.strip():
            _send_message(client, user_input.strip(), page_name, context)

        # ── Suggested quick actions ────────────────────────────────────────────
        suggested = st.session_state.get("_ai_suggested", [])
        if suggested:
            st.markdown(
                '<div style="font-size:0.63rem;color:#5a8a5a;padding:0.15rem 0 0.08rem;'
                'font-weight:700;letter-spacing:0.06em;text-transform:uppercase">Suggestions</div>',
                unsafe_allow_html=True,
            )
            for i, action in enumerate(suggested[:3]):
                if st.button(
                    action,
                    key=f"ai_sugg_{page_key}_{i}",
                    width="stretch",
                ):
                    st.session_state["_ai_suggested"] = []
                    _send_message(client, f"How do I: {action}?", page_name, context)

        # ── Clear button ───────────────────────────────────────────────────────
        if history:
            if st.button(
                "Clear",
                icon=":material/delete_outline:",
                key=f"ai_clear_{page_key}",
                width="content",
            ):
                client.assistant_clear_conversation()
                st.session_state["_ai_history"] = []
                st.session_state["_ai_suggested"] = []
                st.session_state["_ai_pending"] = None
                st.session_state["_ai_history_loaded"] = False
                st.rerun()


def _ts() -> str:
    return datetime.now().strftime("%H:%M")


def _fmt_server_ts(iso_ts) -> str:
    if not iso_ts:
        return ""
    try:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except Exception:
        return ""


def _hydrate_history(client) -> None:
    """Load persisted conversation history from the server once per Streamlit session.
    The server (not st.session_state) is the source of truth — this survives refresh/logout."""
    if st.session_state.get("_ai_history_loaded"):
        return
    st.session_state["_ai_history_loaded"] = True
    data, err = client.assistant_get_conversation()
    if err or not data:
        return
    messages = data.get("messages") or []
    st.session_state["_ai_history"] = [
        {
            "role": m["role"],
            "content": m["content"],
            "warning": bool(m.get("contains_warning")),
            "ts": _fmt_server_ts(m.get("created_at")),
        }
        for m in messages
        if m.get("role") in ("user", "assistant")
    ]


def _error_reason(err: str) -> str:
    """Surface the real reason for a failed request instead of one flattened message."""
    if not err:
        return "Assistant temporarily unavailable. Please try again."
    if err == "SESSION_EXPIRED":
        return "Your session expired — please refresh the page and sign in again."
    if err.startswith("HTTP 503"):
        return "The AI assistant is currently disabled or not configured. Contact your administrator."
    if err.startswith("HTTP 429"):
        return "The assistant is busy right now — please wait a moment and try again."
    if err.startswith("HTTP 403"):
        return "You don't have permission to use the assistant on this page."
    if err.startswith("HTTP 409"):
        return "That action already happened or has expired."
    return "Assistant temporarily unavailable. Please try again."


def _send_message(client, message: str, page_name: str, context: dict) -> None:
    st.session_state["_ai_history"].append(
        {"role": "user", "content": message, "ts": _ts()}
    )

    with st.spinner(""):
        data, err = client.assistant_chat(message, page_name, context)

    if err or not data:
        reply = _error_reason(err)
        suggested = []
        contains_warning = False
        pending = None
    else:
        reply = data.get("reply") or "No response received."
        suggested = data.get("suggested_actions") or []
        contains_warning = bool(data.get("contains_warning"))
        pending = data.get("pending_action")

    st.session_state["_ai_history"].append(
        {"role": "assistant", "content": reply, "warning": contains_warning, "ts": _ts()}
    )
    st.session_state["_ai_suggested"] = suggested
    st.session_state["_ai_pending"] = pending
    st.rerun()


def _confirm_pending(client, action_id: str) -> None:
    with st.spinner(""):
        data, err = client.assistant_confirm_action(action_id)
    if err:
        msg = _error_reason(err)
    else:
        msg = "Done — the action was completed."
    st.session_state["_ai_history"].append({"role": "assistant", "content": msg, "ts": _ts()})
    st.session_state["_ai_pending"] = None
    st.rerun()


def _deny_pending(client, action_id: str) -> None:
    client.assistant_deny_action(action_id)
    st.session_state["_ai_history"].append(
        {"role": "assistant", "content": "Okay, I won't do that.", "ts": _ts()}
    )
    st.session_state["_ai_pending"] = None
    st.rerun()
