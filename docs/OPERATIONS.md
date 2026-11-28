# Operations Guide

## Build and run

Use the Makefile for routine local workflows:

```bash
make install
make sample
ollama pull gemma4:latest
make run
make stop
```

The API currently supports `APP_ENV=local`. `APP_ENV=test` is for tests that inject fake services. Starting with `APP_ENV=staging` or `APP_ENV=production` is intentionally rejected until the production adapters and security controls are implemented; changing this value alone does not enable a production deployment.

Docker Compose uses the same environment and loopback defaults:

```bash
cp .env.example .env
docker compose up -d ollama
docker compose exec ollama ollama pull gemma4:latest
docker compose run --rm api make sample
docker compose up --build -d api ui
docker compose ps
```

## Rebuild an index

For Markdown:

```bash
python scripts/build_sample_corpus.py --docs-dir my_docs --out data/clean/articles.jsonl
python indexer/build_index.py --articles data/clean/articles.jsonl --out-dir data/index
```

For a configured documentation website:

```bash
./scripts/sync_kb.sh
```

Restart the API after replacing the index.

## Readiness and logs

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/ready
docker compose logs api
docker compose logs ollama
docker compose logs ui
```

Request logs include a request ID, method, path, status code, and duration. They do not include document content or question text.

## Evaluation

Export the same API key before running the evaluation:

```bash
export API_KEY='<same secret value as in .env>'
make eval
```

The runner reports retrieval/citation source recall, answer-term coverage, abstention precision and recall, outcome accuracy, and latency. Results are heuristic checks, not independent semantic quality judgments.

Record:

- Git commit
- Ollama model
- embedding model
- index manifest ID
- hardware
- evaluation dataset hash
- application configuration relevant to retrieval and generation

## Backup and rollback

At minimum, back up:

- `data/clean/articles.jsonl`
- `data/index/manifest.json`
- `data/index/faiss.index`
- `data/index/chunks.jsonl`
- `data/index/embeddings.npy`
- the `.env.example`-aligned deployment configuration

For a failed rebuild, retain the prior `data/index` directory until the new readiness check passes. The manifest and SHA-256 hashes prevent an artifact mismatch from being silently accepted.

## Production checklist

Before exposing the service beyond loopback:

1. Add HTTPS and user authentication.
2. Authorize access to selected knowledge bases or documents.
3. Move API keys and web-search/provider credentials to a secret manager.
4. Use shared rate limiting and distributed generation queues.
5. Add dashboards, traces, structured error alerting, and backup drills.
6. Pin models and dependencies, and test upgrades against the evaluation set.
7. Establish a reviewed crawler and data-retention policy.
8. Document privacy decisions for optional web search and external providers.
