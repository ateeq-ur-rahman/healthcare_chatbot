"""Streamlit chat frontend for the Aarogya healthcare chatbot backend.

Run with:
    streamlit run frontend/streamlit_app.py

Talks to the FastAPI backend over plain HTTP (see BACKEND_API_URL), so
frontend and backend can be deployed and scaled independently - this file
has no direct dependency on anything in app/.
"""

from __future__ import annotations

import html
import os
import time
from datetime import datetime
from typing import Any, TypedDict

import requests
import streamlit as st

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
REQUEST_TIMEOUT_SECONDS = 45
HEALTH_CHECK_TIMEOUT_SECONDS = 5

SUGGESTED_QUESTIONS = [
    "What are some tips for a balanced diet?",
    "How much water should I drink daily?",
    "What's the difference between a cold and the flu?",
    "How can I improve my sleep quality?",
    "What's basic first aid for a minor burn?",
    "How can I manage stress in a healthy way?",
]

LIGHT_THEME = {
    "bg": "#f6f8fb", "panel": "#ffffff", "text": "#16202e", "subtext": "#5b6579",
    "bubble_user": "#2b5bd7", "bubble_bot": "#eef2fb", "accent": "#2b5bd7", "border": "#e4e9f2",
    "disclaimer_bg": "#fff8e6", "disclaimer_border": "#f0d998", "disclaimer_text": "#8a6d1f",
    "source_chip_bg": "#eef2fb",
    "emergency_bg": "#fdecec", "emergency_border": "#f3b8b8", "emergency_text": "#9c2a2a",
}
DARK_THEME = {
    "bg": "#0f1420", "panel": "#161d2e", "text": "#eef1f8", "subtext": "#9aa4b8",
    "bubble_user": "#2b5bd7", "bubble_bot": "#1c2740", "accent": "#4f8cff", "border": "#26304a",
    "disclaimer_bg": "#2a2113", "disclaimer_border": "#5a4a1f", "disclaimer_text": "#e8d38a",
    "source_chip_bg": "#1c2740",
    "emergency_bg": "#3a1414", "emergency_border": "#7a2b2b", "emergency_text": "#ffb4b4",
}


class DisplayMessage(TypedDict, total=False):
    """Shape of an entry in `st.session_state.messages` used for rendering."""

    role: str
    content: str
    sources: list[dict[str, Any]]
    disclaimer: str
    is_emergency: bool
    feedback_key: str


def inject_theme_css(dark_mode: bool) -> None:
    """Apply the light or dark theme as a single <style> block."""
    theme = DARK_THEME if dark_mode else LIGHT_THEME
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {theme["bg"]}; }}
        [data-testid="stSidebar"] {{
            background-color: {theme["panel"]};
            border-right: 1px solid {theme["border"]};
        }}
        .aarogya-header {{
            display: flex; align-items: center; gap: 0.75rem;
            padding: 0.75rem 0 1rem 0;
        }}
        .aarogya-title {{ font-size: 1.6rem; font-weight: 700; color: {theme["text"]}; margin: 0; }}
        .aarogya-subtitle {{ font-size: 0.85rem; color: {theme["subtext"]}; margin: 0; }}
        .disclaimer-banner {{
            background: {theme["disclaimer_bg"]};
            border: 1px solid {theme["disclaimer_border"]};
            color: {theme["disclaimer_text"]};
            padding: 0.65rem 1rem; border-radius: 10px; font-size: 0.82rem;
            margin-bottom: 1rem;
        }}
        .chat-bubble-user {{
            background: {theme["bubble_user"]}; color: white; padding: 0.7rem 1rem;
            border-radius: 16px 16px 4px 16px; max-width: 78%; margin-left: auto;
            margin-bottom: 0.6rem; font-size: 0.95rem; line-height: 1.45;
        }}
        .chat-bubble-bot {{
            background: {theme["bubble_bot"]}; color: {theme["text"]}; padding: 0.7rem 1rem;
            border-radius: 16px 16px 16px 4px; max-width: 78%; margin-right: auto;
            margin-bottom: 0.6rem; font-size: 0.95rem; line-height: 1.5;
            border: 1px solid {theme["border"]};
        }}
        .source-chip {{
            display: inline-block; background: {theme["source_chip_bg"]};
            color: {theme["accent"]}; border-radius: 999px; padding: 0.15rem 0.6rem;
            font-size: 0.72rem; margin: 0.15rem 0.3rem 0 0; border: 1px solid {theme["border"]};
        }}
        .emergency-banner {{
            background: {theme["emergency_bg"]};
            border: 1px solid {theme["emergency_border"]};
            color: {theme["emergency_text"]};
            padding: 0.8rem 1rem; border-radius: 10px; font-weight: 600;
            margin-bottom: 0.6rem;
        }}
        .suggested-q button {{ width: 100%; text-align: left; }}
        .stChatMessage {{ background: transparent; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    """Set up st.session_state defaults. Safe to call on every rerun."""
    st.session_state.setdefault("dark_mode", False)
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("messages", [])  # list[DisplayMessage]
    st.session_state.setdefault("question_log", [])  # sidebar "asked this session" log


def post_chat_message(message: str) -> dict[str, Any] | None:
    """Send one message to the backend. Returns the parsed response, or None on failure."""
    payload = {"message": message, "session_id": st.session_state.session_id}
    try:
        response = requests.post(f"{BACKEND_API_URL}/chat", json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"⚠️ Couldn't reach the backend at {BACKEND_API_URL}. Is it running? ({exc})")
        return None


def clear_backend_session(session_id: str) -> None:
    """Best-effort request to clear server-side history. UI clears regardless of the result."""
    try:
        requests.post(f"{BACKEND_API_URL}/clear", json={"session_id": session_id}, timeout=10)
    except requests.exceptions.RequestException:
        pass


def fetch_backend_health() -> dict[str, Any] | None:
    try:
        response = requests.get(f"{BACKEND_API_URL}/health", timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🩺 Aarogya")
        st.caption("AI Healthcare Information Assistant")

        backend_health = fetch_backend_health()
        if backend_health:
            st.success(f"Backend connected · {backend_health.get('llm_provider', '?').upper()}")
            if not backend_health.get("vectorstore_loaded"):
                st.caption("⚠️ Knowledge base index not loaded — answers won't cite sources yet.")
        else:
            st.error("Backend unreachable")

        st.toggle("🌙 Dark mode", key="dark_mode", on_change=lambda: inject_theme_css(st.session_state.dark_mode))
        st.divider()

        if st.button("🗑️ Clear Chat", use_container_width=True):
            if st.session_state.session_id:
                clear_backend_session(st.session_state.session_id)
            st.session_state.messages = []
            st.session_state.session_id = None
            st.rerun()

        st.divider()
        st.markdown("#### 💡 Suggested questions")
        for question in SUGGESTED_QUESTIONS:
            if st.button(question, key=f"suggested-{question}", use_container_width=True):
                st.session_state["pending_prompt"] = question

        st.divider()
        st.markdown("#### 🕘 This session's questions")
        if not st.session_state.question_log:
            st.caption("No questions asked yet.")
        else:
            for entry in reversed(st.session_state.question_log[-15:]):
                preview = entry["question"][:48] + ("…" if len(entry["question"]) > 48 else "")
                st.caption(f"{entry['time']} — {preview}")

        st.divider()
        st.caption(
            "Aarogya provides general health information only. It does not diagnose "
            "conditions or prescribe medication. Always consult a qualified healthcare "
            "professional for personal medical advice."
        )


def render_header() -> None:
    st.markdown(
        """
        <div class="aarogya-header">
            <div style="font-size:2.2rem;">🩺</div>
            <div>
                <p class="aarogya-title">Aarogya — Healthcare AI Chatbot</p>
                <p class="aarogya-subtitle">Ask about symptoms, nutrition, first aid, and healthy living</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="disclaimer-banner">⚕️ <b>Educational use only.</b> '
        "This assistant does not diagnose conditions or prescribe medication, and is not a "
        "substitute for professional medical advice. In an emergency, contact local emergency "
        "services immediately.</div>",
        unsafe_allow_html=True,
    )


def render_message(message: DisplayMessage) -> None:
    """Render one chat bubble, with sources/disclaimer/feedback for assistant turns.

    User and assistant text is HTML-escaped before being embedded in the
    bubble markup - the div wrapper needs `unsafe_allow_html=True` for
    styling, but the message text itself must never be treated as HTML.
    """
    safe_content = html.escape(message["content"])

    if message["role"] == "user":
        st.markdown(f'<div class="chat-bubble-user">{safe_content}</div>', unsafe_allow_html=True)
        return

    if message.get("is_emergency"):
        st.markdown('<div class="emergency-banner">🚨 Emergency guidance</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="chat-bubble-bot">{safe_content}</div>', unsafe_allow_html=True)

    if message.get("sources"):
        chips = "".join(
            f'<span class="source-chip">📄 {html.escape(source["source"])}</span>'
            for source in message["sources"]
        )
        st.markdown(chips, unsafe_allow_html=True)

    if message.get("disclaimer"):
        st.caption(f"ℹ️ {message['disclaimer']}")

    if message.get("feedback_key"):
        thumbs_up_col, thumbs_down_col, _ = st.columns([1, 1, 8])
        with thumbs_up_col:
            st.button("👍", key=f"up-{message['feedback_key']}")
        with thumbs_down_col:
            st.button("👎", key=f"down-{message['feedback_key']}")


def handle_user_input(user_input: str) -> None:
    """Send a new message and append both turns to the on-screen transcript."""
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.question_log.append({"time": datetime.now().strftime("%H:%M"), "question": user_input})

    with st.spinner("Aarogya is thinking…"):
        result = post_chat_message(user_input)

    if result:
        st.session_state.session_id = result["session_id"]
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result["response"],
                "sources": result.get("sources", []),
                "disclaimer": result.get("disclaimer"),
                "is_emergency": result.get("is_emergency", False),
                "feedback_key": str(int(time.time() * 1000)),
            }
        )
    st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Aarogya — Healthcare AI Chatbot",
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session_state()
    inject_theme_css(st.session_state.dark_mode)

    render_sidebar()
    render_header()

    with st.container():
        for message in st.session_state.messages:
            render_message(message)

    pending_prompt = st.session_state.pop("pending_prompt", None)
    user_input = st.chat_input("Ask a health question…") or pending_prompt
    if user_input:
        handle_user_input(user_input)


if __name__ == "__main__":
    main()
