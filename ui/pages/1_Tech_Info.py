from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.branding import get_branding  # noqa: E402

BRAND = get_branding()

st.set_page_config(
    page_title=f"Tech Info – {BRAND.app_name}",
    page_icon=str(BRAND.icon_path),
    layout="wide",
)

st.markdown(
    """
    <style>
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDeployButton"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { display: none !important; }
    footer { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚙️ Technical Overview")
st.caption(f"Architecture, tools, and design decisions behind {BRAND.app_name}.")

# ── Architecture ─────────────────────────────────────────────────────────────
st.header("Architecture")
st.markdown("""
The chatbot is a **local-first Retrieval-Augmented Generation (RAG)** system.
All inference happens on-device — no data leaves the machine.

```
User question
     │
     ▼
Streamlit UI  ──(HTTP POST)──►  FastAPI Runtime
                                      │
                              ┌───────┴────────┐
                              ▼                │  (inactive by default)
                       Scope Guardrail         │
                       (LLM classifier)        │
                              │                │
                   ┌──────────┤                │
                 REJECT      ALLOW ────────────┘
                   │              │
                   │    ┌─────────┴──────────┐
                   │    ▼                    ▼
                   │  FAISS Vector Index  Ollama LLM
                   │  (pre-indexed KB)   (local model)
                   │         │                │
                   │  Retrieve top-k chunks   │
                   │         │                │
                   │         └──── Prompt ────┘
                   │                   │
                   │                   ▼
                   │            Clean answer
                   │            + Citations
                   ▼
           Rejection message
           (no RAG call made)
```
""")

# ── Scope Guardrail ──────────────────────────────────────────────────────────
st.header("Scope Guardrail")

guardrail_status = """
<span style='background:#f0fdf4;color:#166534;padding:3px 10px;
border-radius:4px;font-weight:600;font-size:0.85em;'>⏸ INACTIVE (demo mode)</span>
&nbsp; Enable with <code>GUARDRAIL_ENABLED=true</code>
"""
st.markdown(guardrail_status, unsafe_allow_html=True)
st.markdown("")

col_g1, col_g2 = st.columns(2)
with col_g1:
    st.subheader("Purpose")
    st.markdown("""
A lightweight pre-processing layer that classifies every user message
**before** it reaches the RAG pipeline. Its job is to prevent the chatbot
being used for purposes outside its scope — saving model compute and keeping
the UX on-topic.

When **inactive** (default) it is a pure pass-through with zero latency cost.
When **active** it adds a single fast LLM call that returns a single-token verdict.
    """)
with col_g2:
    st.subheader("Classification model")
    st.markdown("""
| Parameter | Value |
|---|---|
| Model | `gemma4:latest` (override via `GUARDRAIL_MODEL`) |
| Temperature | 0 (greedy / deterministic) |
| `num_predict` | 10 (forces a near-single-token response) |
| `top_k` | 1 (fastest decoding) |
| Timeout | 15 s (allows through on timeout) |
| Env toggle | `GUARDRAIL_ENABLED=true/false` |
    """)

st.subheader("Rejection categories")
col_r1, col_r2 = st.columns(2)
with col_r1:
    st.markdown("""
| Label | Triggers on |
|---|---|
| `out_of_scope` | Sports, food, travel, finance, medicine… |
| `code_generation` | "Write me code / a script / implement…" |
    """)
with col_r2:
    st.markdown("""
| Label | Triggers on |
|---|---|
| `media_generation` | "Generate an image / video / PDF…" |
| `general_chat` | Jokes, small talk, greetings, homework |
    """)

st.subheader("Safety behaviour")
st.markdown("""
- On **classifier timeout or any error** the question is **allowed through** — the guardrail never silently drops a legitimate question.
- Rejected questions receive a friendly, category-specific message; the RAG pipeline is never called.
- The API response includes `guardrail_blocked: bool` and `guardrail_category` fields for observability.
""")

st.markdown("---")

# ── Data Pipeline ────────────────────────────────────────────────────────────
st.header("Data Pipeline")

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("1 · Discover")
    st.markdown("""
- Crawls the configured `KB_ROOT_URL`
- Follows internal links recursively
- Deduplicates and validates URLs
- Outputs `artifacts/discovered_urls.txt`
    """)
with col2:
    st.subheader("2 · Extract")
    st.markdown("""
- Downloads each KB page (raw HTML)
- Strips navigation, ads, boilerplate
- Uses **trafilatura** + BeautifulSoup
- Outputs clean article text + metadata
    """)
with col3:
    st.subheader("3 · Index")
    st.markdown("""
- Splits articles into overlapping chunks
- Embeds with **SentenceTransformers**
- Builds a **FAISS** flat inner-product index
- Saves `data/index/faiss.index` + `chunks.jsonl`
    """)

st.markdown("---")
st.markdown("Sync on demand: `bash scripts/sync_kb.sh`  |  Schedule via `cron` for periodic refresh.")

# ── Runtime ──────────────────────────────────────────────────────────────────
st.header("Runtime – RAG Service")

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Retrieval")
    st.markdown("""
| Parameter | Value |
|---|---|
| Embedding model | `all-MiniLM-L6-v2` (SentenceTransformers) |
| Index type | FAISS flat inner-product (cosine via normalised vectors) |
| Top-K chunks | 4 |
| Similarity threshold | 0.32 |
| Min distinct sources | 2 |
    """)
with col_b:
    st.subheader("Generation")
    st.markdown("""
| Parameter | Value |
|---|---|
| LLM runtime | Ollama (local) |
| Default model | `gemma4:latest` |
| Temperature | 0.1 |
| Top-p | 0.9 |
| Ollama call timeout | 300 s |
| UI request timeout | 360 s |
| Auto-retry attempts | 4 (delays: 2 s, 4 s, 8 s, 12 s) |
    """)

st.subheader("KB-First Fallback Strategy")
st.markdown("""
1. Retrieve the top-k chunks from the FAISS index.
2. If **good hits** (score ≥ threshold) exist → build a grounded prompt from those chunks.
3. If **no good hits** → build a general-knowledge prompt and let the model answer from its own training data.
4. Either way the model is instructed **not to embed citations** in the answer text — citations are returned separately and shown as collapsible *References*.
""")

st.subheader("Response Cache")
st.markdown("""
- In-memory LRU cache keyed on: `format_version | model | embedding_model | top_k | threshold | question`
- TTL: **900 s** (15 min)
- Max entries: **128**
- Cache key includes a format-version string so any prompt change auto-invalidates stale entries.
""")

# ── Tech Stack ────────────────────────────────────────────────────────────────
st.header("Tech Stack")

stack = {
    "FastAPI": "REST API runtime (`runtime/app.py`)",
    "Uvicorn": "ASGI server hosting FastAPI",
    "Streamlit 1.48": "Chat UI (`ui/chat_app.py`)",
    "FAISS (faiss-cpu)": "Approximate nearest-neighbour vector search",
    "SentenceTransformers": "Text embedding (`all-MiniLM-L6-v2`)",
    "Ollama": "Local LLM inference server",
    "trafilatura": "Web article extraction from raw HTML",
    "BeautifulSoup4": "HTML parsing fallback",
    "requests": "HTTP client for Ollama and KB crawl",
    "Python 3.9": "Runtime environment",
}

cols = st.columns(2)
items = list(stack.items())
half = (len(items) + 1) // 2
for i, (tool, desc) in enumerate(items):
    col = cols[0] if i < half else cols[1]
    col.markdown(f"**{tool}** — {desc}")

# ── File Structure ─────────────────────────────────────────────────────────────
st.header("Project Structure")
st.code("""
kb-rag-assistant/
├── assets/
│   ├── kb-icon.png              # Browser-tab favicon (avatar)
│   ├── kb-logo.png
│   └── kb-logo.svg
├── data/
│   └── index/
│       ├── faiss.index          # FAISS vector index
│       └── chunks.jsonl         # Article chunks + metadata
├── ingest/
│   ├── discover_urls.py         # KB URL discovery crawler
│   ├── crawl_kb.py              # Page downloader
│   ├── extract_articles.py      # HTML → clean text
│   └── build_index.py           # Embedding + FAISS indexing
├── runtime/
│   ├── app.py                   # FastAPI endpoints
│   ├── guardrail.py             # Scope guardrail (inactive by default)
│   └── rag_service.py           # RAG core (retrieve, prompt, answer)
├── scripts/
│   ├── sync_kb.sh               # Full pipeline (discover→index)
│   └── run_pipeline.sh          # Backwards-compat wrapper
├── ui/
│   ├── chat_app.py              # Main Streamlit chat page
│   └── pages/
│       └── 1_Tech_Info.py       # This page
├── logs/
│   ├── api.log
│   └── ui.log
├── start.sh                     # Start both services via nohup
└── .env.example
""", language="")

st.markdown("---")
st.caption("All processing is local. No API keys required. No data sent to external services.")
