# Architecture

KnowledgeBase Assistant is a local-first RAG service composed of a crawler or Markdown importer, an index builder, a FastAPI runtime, and a Streamlit interface.

## Components

| Component | Implementation | Responsibility |
|-----------|----------------|----------------|
| Ingestion | `ingest/` | Discover URLs, honor `robots.txt`, crawl HTML, and extract articles |
| Markdown build | `scripts/build_sample_corpus.py` | Convert a folder of Markdown files into normalized articles |
| Indexing | `indexer/build_index.py` | Split sections into chunks, create embeddings, and write FAISS artifacts |
| Runtime | `runtime/app.py`, `runtime/rag_service.py` | Authenticate requests, limit concurrency, retrieve evidence, and generate answers |
| Interface | `ui/chat_app.py` | Stream answers, show citations, and offer clarifications or follow-ups |
| Shared config | `common/config.py`, `common/branding.py` | Load environment settings and knowledge-base branding |
| Evaluation | `eval/` | Measure retrieval recall, answer terms, abstention behavior, and latency |

See [System Diagrams](DIAGRAMS.md) for the visual component, sequence, state, and deployment views.

## Ingestion

The crawler is fail-closed around robots policy: if policy cannot be retrieved or a URL is disallowed, it is not fetched. HTML extraction and Markdown conversion produce JSONL article records.

The indexer groups text by Markdown heading, applies token-based chunking, and generates normalized sentence-transformer embeddings. The FAISS index uses inner product, which behaves as cosine similarity for normalized vectors. Artifact checksums and a manifest are written so the API can reject mismatched models or corrupted files before serving.

## Retrieval and generation

1. Normalize and embed the question with the configured sentence-transformer model.
2. Search the FAISS index for the configured top-k chunks.
3. Filter hits by the similarity threshold.
4. Require independent sources for a sufficiently independent answer when the top result is near the threshold.
5. Build a prompt containing at most three retrieved chunks and instruct the model to answer only from those sources.
6. Stream generation through Ollama with low-temperature settings.
7. Remove stray citation sections, resolve citations to source URLs, and cache the final response.

Weak evidence can abstain. If web search is enabled, weak evidence can trigger an explicitly disclosed DuckDuckGo search fallback through the `ddgs` Python package. Search failures produce normal abstention rather than exposing provider details to the chat response.

## Answer controls

- **Clarification:** ambiguous questions can produce targeted clarification choices before retrieval.
- **Scope guardrail:** optional Ollama classification rejects clearly out-of-scope or generation requests.
- **Abstention:** the service refuses to invent an answer when retrieved evidence is insufficient.
- **Source citations:** KB citations include source URLs and score; web citations are marked as external.
- **Follow-up options:** the model can suggest up to three next questions.
- **Cache:** successful and abstained responses use a bounded in-process TTL cache.

The guardrail is not authorization and fails open on classifier or provider errors.

## Operational boundaries

- The response cache, rate limiter, and generation semaphore are per process.
- One process loads the index and embedding model once at startup.
- The API uses a shared bearer key, not end-user identity.
- The default Docker network exposes ports only on the loopback host.
- Containerized Ollama and application data persist in Docker volumes.

For remote or multi-user deployment, add HTTPS, per-user authorization, shared rate limiting, distributed capacity control, backups, migration/rollback procedures, tracing, and alerting.
