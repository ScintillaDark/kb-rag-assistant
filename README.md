# KnowledgeBase Assistant

A **local-first, offline RAG chatbot** for any documentation set. It indexes your content once, retrieves the most relevant passages at question time, and generates cited answers with a local LLM through [Ollama](https://ollama.com). No document or question leaves your machine.

<p align="center"><img src="assets/kb-logo.png" alt="KnowledgeBase Assistant logo" width="120"></p>

## Features

- **Fully local**: FAISS vector search, sentence-transformers embeddings, Ollama for generation
- **Real token streaming** in the chat UI, with cited sources and suggested follow-up questions
- **Bring your own content**: crawl a documentation site or index a folder of Markdown files
- **Configurable branding**: name, tagline, logo, suggested questions and subject area all come from `.env`
- **Safety rails**: abstains on weak evidence; optional scope guardrail, clarifying questions and web-search fallback
- **Response cache** for repeated questions, plus an evaluation harness
- **Docker and Makefile** for one-command setup

## Quick start (about 5 minutes)

```bash
git clone https://github.com/ScintillaDark/kb-rag-assistant.git
cd kb-rag-assistant

make install          # creates .venv and installs dependencies
cp .env.example .env  # optional: adjust branding and settings
make sample           # builds a demo index from sample_data/docs
ollama pull gemma4:latest
make run              # starts the API (8000) and the chat UI (8501)
```

Open <http://localhost:8501>. Stop everything with `make stop`.

See [INSTALL.md](INSTALL.md) for detailed, platform-specific instructions (Linux, macOS, Docker) and troubleshooting.

## Use your own knowledge base

**A documentation website**

```bash
# in .env
KB_BASE_URL=https://docs.example.com
KB_ROOT_URL=https://docs.example.com/help
KB_ARTICLE_SEGMENT=articles     # URL segment under the root that marks an article page
```

```bash
./scripts/sync_kb.sh            # discover, crawl, extract, chunk, embed, index
```

**A folder of Markdown files**

```bash
python scripts/build_sample_corpus.py --docs-dir my_docs --out data/clean/articles.jsonl
python indexer/build_index.py --articles data/clean/articles.jsonl --out-dir data/index
```

Then restart with `make run`. Only crawl sites whose terms allow it, and respect their `robots.txt`.

## Configuration

All settings live in `.env` (see [.env.example](.env.example) for the full list):

| Group | Variables |
|-------|-----------|
| Branding | `APP_NAME`, `APP_TAGLINE`, `APP_ICON_PATH`, `APP_LOGO_PATH`, `APP_INPUT_PLACEHOLDER` |
| Subject area | `KB_DOMAIN`, `KB_TOPICS`, `KB_SUGGESTED_QUESTIONS`, `KB_WARM_QUESTIONS` |
| Crawler | `KB_BASE_URL`, `KB_ROOT_URL`, `KB_ARTICLE_SEGMENT`, `KB_LISTING_SEGMENT`, `KB_USER_AGENT` |
| Retrieval | `RAG_INDEX_DIR`, `RAG_EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_SIMILARITY_THRESHOLD`, `RAG_MIN_SOURCES` |
| Model | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_THINK` |
| Optional features | `GUARDRAIL_ENABLED`, `WEB_SEARCH_ENABLED`, `RAG_CLARIFICATION_ENABLED`, `RAG_ANSWER_OPTIONS_ENABLED` |
| Services | `API_HOST`, `API_PORT`, `UI_PORT`, `RAG_API_URL` |

## Architecture

```
Question ─► Streamlit UI ─► FastAPI ─► [guardrail] ─► FAISS retrieval ─► prompt ─► Ollama
                                                                                    │
            Answer + citations + follow-ups  ◄── token stream ◄─────────────────────┘
```

| Folder | Purpose |
|--------|---------|
| `ingest/` | URL discovery, crawler, HTML to text extraction |
| `indexer/` | chunking, embeddings, FAISS index build |
| `runtime/` | FastAPI service, RAG logic, guardrail, clarifier, web search |
| `ui/` | Streamlit chat app and technical overview page |
| `common/` | shared configuration and branding |
| `eval/` | small evaluation question set and runner |
| `sample_data/` | neutral demo documents |

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | liveness check |
| `POST /chat` | `{"question": "..."}` returns the full answer and citations |
| `POST /chat/stream` | NDJSON stream of `token`, `meta` and `options` events |

Interactive docs are served at `/docs`.

## Performance notes

On a CPU-only machine a 7-8B model produces a few tokens per second. Use a smaller model (`OLLAMA_MODEL`), keep `OLLAMA_THINK=false`, and consider `make warm` before a demo.

## Development

```bash
make install-dev   # adds pytest and ruff
make test
make lint
```

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
