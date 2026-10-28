from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.branding import get_branding  # noqa: E402

BRAND = get_branding()

# ── Config ────────────────────────────────────────────────────────────────────
_raw_url = os.getenv("RAG_API_URL", "http://localhost:8000/chat").rstrip("/")
API_BASE = _raw_url[:-5] if _raw_url.endswith("/chat") else _raw_url
CHAT_URL   = f"{API_BASE}/chat"
STREAM_URL = f"{API_BASE}/chat/stream"

ICON_PATH = BRAND.icon_path
SUGGESTED_QUESTIONS = BRAND.suggested_questions

# ── Page setup ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=BRAND.app_name,
    page_icon=str(ICON_PATH),
    layout="wide",
)
if BRAND.logo_path.exists():
    st.logo(str(BRAND.logo_path), icon_image=str(ICON_PATH))

st.markdown(
    """
    <style>
    [data-testid="stToolbar"]      { display: none !important; }
    [data-testid="stDeployButton"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { display: none !important; }
    footer    { display: none !important; }

    /* Suggested question chips */
    div[data-testid="column"] > div > div > div > div > .stButton > button {
        width: 100%;
        text-align: left;
        white-space: normal;
        font-size: 0.85em;
        padding: 0.4em 0.75em;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(BRAND.app_name)
st.caption(BRAND.tagline)

# ── Session state ─────────────────────────────────────────────────────────────
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending", False)

# ── Sidebar: clear chat ───────────────────────────────────────────────────────
with st.sidebar:
    if st.session_state.messages:
        if st.button("🗑 Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending = False
            st.rerun()

# ── Render chat history ───────────────────────────────────────────────────────
for mi, msg in enumerate(st.session_state.messages):
    avatar = str(ICON_PATH) if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("References"):
                for c in sorted(msg["citations"], key=lambda x: x.get("score", 0), reverse=True):
                    if c.get("source") == "web":
                        st.markdown(f"⛐️‍ **[{c['title']}]({c['url']})** — *Web*")
                    else:
                        score_pct = round(c.get("score", 0) * 100)
                        st.markdown(f"- [{c['title']}]({c['url']}) — **{score_pct}% match**")
        # Clarifying questions (shown when the assistant asked for clarification)
        clarify_qs = msg.get("clarification_questions", [])
        if clarify_qs and msg["role"] == "assistant":
            st.markdown("**Please clarify your question:**")
            for ci, cq in enumerate(clarify_qs):
                if st.button(cq, key=f"h_clarify_{mi}_{ci}", use_container_width=True):
                    if not st.session_state.pending:
                        st.session_state.messages.append({"role": "user", "content": cq})
                        st.session_state.pending = True
                        st.rerun()
        # Follow-up answer options
        opts = msg.get("answer_options", [])
        if opts and msg["role"] == "assistant":
            st.markdown("**You might also want to ask:**")
            opt_cols = st.columns(min(len(opts), 3))
            for oi, opt in enumerate(opts):
                if opt_cols[oi % len(opt_cols)].button(opt, key=f"h_opt_{mi}_{oi}"):
                    if not st.session_state.pending:
                        st.session_state.messages.append({"role": "user", "content": opt})
                        st.session_state.pending = True
                        st.rerun()

# ── Suggested questions (empty state only) ────────────────────────────────────
if not st.session_state.messages and not st.session_state.pending:
    st.markdown("**Try asking:**")
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTED_QUESTIONS):
        if cols[i % 2].button(q, key=f"sq_{i}"):
            if not st.session_state.pending:
                st.session_state.messages.append({"role": "user", "content": q})
                st.session_state.pending = True
                st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
prompt = st.chat_input(
    BRAND.input_placeholder,
    disabled=st.session_state.pending,
    key="main_chat_input",
)

if prompt and not st.session_state.pending:
    st.session_state.pending = True
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# ── Stream response when pending ─────────────────────────────────────────────
if (
    st.session_state.pending
    and st.session_state.messages
    and st.session_state.messages[-1]["role"] == "user"
):
    current_question = st.session_state.messages[-1]["content"]

    with st.chat_message("assistant", avatar=str(ICON_PATH)):
        status_placeholder = st.empty()
        status_placeholder.markdown(
            "<span style='color:#888;font-size:0.9em'>🔍 Searching knowledge base...</span>",
            unsafe_allow_html=True,
        )
        text_placeholder = st.empty()

        accumulated = ""
        final_answer = ""
        citations: list = []
        clarification_questions: list = []
        answer_options: list = []
        first_token = False
        last_render = 0.0

        try:
            with requests.post(
                STREAM_URL,
                json={"question": current_question},
                stream=True,
                timeout=(10, 900),
            ) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        event = json.loads(raw_line)
                    except Exception:
                        continue

                    etype = event.get("type")

                    if etype == "token":
                        if not first_token:
                            status_placeholder.empty()
                            first_token = True
                        accumulated += event.get("text", "")
                        now = time.monotonic()
                        if now - last_render > 0.15:
                            text_placeholder.markdown(accumulated + "▌")
                            last_render = now

                    elif etype == "meta":
                        final_answer = event.get("final_answer", accumulated)
                        citations = event.get("citations", [])
                        clarification_questions = event.get("clarification_questions", [])
                        answer_options = event.get("answer_options", [])

                    elif etype == "options":
                        answer_options = event.get("answer_options", [])

        except Exception:
            # Fallback to non-streaming endpoint on any error
            try:
                r = requests.post(
                    CHAT_URL,
                    json={"question": current_question},
                    timeout=900,
                )
                r.raise_for_status()
                d = r.json()
                final_answer = d.get("answer", "")
                citations = d.get("citations", [])
                clarification_questions = d.get("clarification_questions", [])
                answer_options = d.get("answer_options", [])
            except Exception:
                final_answer = (
                    "I'm having trouble reaching the knowledge base right now. "
                    "Please try again in a moment."
                )

        status_placeholder.empty()
        display = final_answer or accumulated
        text_placeholder.markdown(display)

        if citations:
            with st.expander("References"):
                for c in sorted(citations, key=lambda x: x.get("score", 0), reverse=True):
                    if c.get("source") == "web":
                        st.markdown(f"⛐️‍ **[{c['title']}]({c['url']})** — *Web*")
                    else:
                        score_pct = round(c.get("score", 0) * 100)
                        st.markdown(f"- [{c['title']}]({c['url']}) — **{score_pct}% match**")

        st.session_state.messages.append({
            "role": "assistant",
            "content": display,
            "citations": citations,
            "clarification_questions": clarification_questions,
            "answer_options": answer_options,
        })
        st.session_state.pending = False
        st.rerun()

# ── "Powered by local AI" badge ───────────────────────────────────────────────
st.markdown(
    "<div style='position:fixed;bottom:64px;right:20px;font-size:0.72em;"
    "color:#999;background:rgba(255,255,255,0.9);padding:4px 12px;"
    "border-radius:12px;border:1px solid #eee;"
    "backdrop-filter:blur(4px);pointer-events:none;'>"
    "🔒 Powered by local AI &nbsp;·&nbsp; No data leaves this machine"
    "</div>",
    unsafe_allow_html=True,
)
