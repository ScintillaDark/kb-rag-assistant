# KnowledgeBase Assistant

![CI](https://github.com/ScintillaDark/kb-rag-assistant/actions/workflows/ci.yml/badge.svg?branch=main)

A **local-first, offline RAG chatbot** for any documentation set. It indexes your content once, retrieves the most relevant passages at question time, and generates cited answers with a local LLM through [Ollama](https://ollama.com). By default, no document or question leaves your machine; enabling web search sends search queries to the configured provider.

<p align="center"><img src="assets/kb-logo.png" alt="KnowledgeBase Assistant logo" width="120"></p>

> **Showcase status:** end-to-end local RAG demo with evaluation and baseline service controls. It is not a turnkey multi-user hosted service: use HTTPS and a trusted gateway for remote deployments, and review [SECURITY.md](SECURITY.md) before exposing it outside localhost.

## Features

- **Local inference by default**: FAISS vector search, sentence-transformers embeddings, Ollama generation
- **Real token streaming** in the chat UI, with cited sources and suggested follow-up questions
- **Bring your own content**: crawl a documentation site or index a folder of Markdown files
- **Configurable branding**: name, tagline, logo, suggested questions and subject area all come from `.env`
- **Evidence handling**: abstains when retrieved evidence is weak; optional web search can supply external evidence
- **Operational controls**: required shared API bearer key, per-IP rate limits, generation concurrency cap, readiness probe and request IDs
- **Index integrity**: stable chunk IDs, versioned manifests and artifact checksums
- **Evaluation harness**: expected-source, answer-term, abstention and latency measurements over a versioned demo dataset
- **Docker Compose and Makefile** workflows for local setup

## Quick start (about 5 minutes)

```bash
git clone https://github.com/ScintillaDark/kb-rag-assistant.git
cd kb-rag-assistant

make install          # creates .venv and installs dependencies
cp .env.example .env
# Set API_KEY in .env to a random secret before starting
make sample           # builds a demo index from sample_data/docs
ollama pull gemma4:latest
make run              # starts the API (8000) and the chat UI (8501)
```

Open <http://localhost:8501>. Stop everything with `make stop`.

See [INSTALL.md](INSTALL.md) for detailed, platform-specific instructions (Linux, macOS, Docker) and troubleshooting.
For a guided interview walkthrough and demo script, see [SHOWCASE.md](SHOWCASE.md).

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

Then restart the API so it loads the new index. The crawler enforces each site's `robots.txt` policy and fails closed if it cannot retrieve the policy. Only crawl sites whose terms allow it.

## Evaluate answer quality

Start the application with the sample index and export the same `API_KEY` value configured in `.env`:

```bash
export API_KEY='<same secret value as in .env>'
make eval
```

The evaluation set records expected source pages, answer terms, and whether a question should be answered or refused. The runner reports retrieval/citation source recall, term coverage, abstention precision/recall, outcome accuracy, and latency. It writes per-question output and a machine-readable summary under `artifacts/`. These are **transparent heuristic checks, not an LLM judge or a claim of semantic correctness**. Record hardware, model, and dataset hash when comparing runs; do not publish unmeasured quality or latency claims.

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
| API access and capacity | `API_KEY`, `API_RATE_LIMIT_PER_MINUTE`, `API_MAX_CONCURRENT_GENERATIONS` |
| Services | `API_HOST`, `API_PORT`, `UI_PORT`, `RAG_API_URL`, `HOST_BIND_ADDRESS`, `APP_UID`, `APP_GID` |

## Architecture

```
Question ─► Streamlit UI ─► FastAPI (bearer key / limits) ─► [optional guardrail]
                                                               │
                       ┌──────── web search (opt-in) ◄── weak evidence?
                       │                                       │
                       └──────────────────► FAISS retrieval ─► Ollama
                                               │                 │
                     Answer + evidence citations ◄── NDJSON stream
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
| `GET /health` | unauthenticated liveness check |
| `GET /health/ready` | readiness: API key, index/model load, and configured Ollama model |
| `POST /chat` | bearer-authenticated `{"question": "..."}`; returns answer, abstention state, retrieval and citations |
| `POST /chat/stream` | bearer-authenticated NDJSON stream of `token`, `meta` and `options` events |

Send an `Authorization: Bearer <API_KEY>` header to both chat endpoints. `/docs` and `/openapi.json` describe the API but do not grant chat access. The API key is a shared service credential, not individual user identity. The built-in rate limiter and concurrency cap are per process; use an authenticated TLS reverse proxy and gateway-level limits for multi-worker or internet-facing deployments.

## Production boundary

The project is suitable as a local-first showcase and a self-hosted starting point. Before serving untrusted users or sensitive corpora, add an identity provider and per-user authorization, a durable distributed rate limiter/queue, backups and index rollback, alerting, and a deployment-specific threat review. The optional LLM scope classifier is a topic filter—not an authorization control—and fails open if the classifier errors. Retrieved content is marked untrusted in prompts, but prompt-injection defenses are not guarantees.

## Performance notes

CPU performance depends on the selected model and hardware. Use a smaller model (`OLLAMA_MODEL`), keep `OLLAMA_THINK=false`, and consider `make warm` before a demo.

## Development

```bash
make install-dev   # adds pytest and ruff
make test
make lint
```

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
