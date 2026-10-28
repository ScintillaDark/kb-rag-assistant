# Installation Guide

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.10-3.12 | These are the versions exercised in CI |
| [Ollama](https://ollama.com/download) | runs the local language model |
| Docker Compose v2.24+ | required for the Compose install path |
| 8 GB RAM minimum | 16 GB or more for larger models |
| ~5 GB disk | Python packages (PyTorch) plus the model |
| GPU | optional; without one, answers are slower |

## Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip make git
curl -fsSL https://ollama.com/install.sh | sh

git clone https://github.com/ScintillaDark/kb-rag-assistant.git
cd kb-rag-assistant
make install
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Put the generated value in API_KEY in .env before starting
make sample
ollama pull gemma4:latest
make run
```

## macOS

```bash
brew install python make git ollama
git clone https://github.com/ScintillaDark/kb-rag-assistant.git
cd kb-rag-assistant
make install && make sample
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Put the generated value in API_KEY in .env before starting
ollama pull gemma4:latest
make run
```

## Windows

Use WSL2 with Ubuntu and follow the Linux steps, or use Docker (below).

## Docker

```bash
cp .env.example .env
# Set API_KEY to a generated secret in .env first.
# If needed, set APP_UID and APP_GID to the owner of ./data before creating containers.
docker compose up -d ollama
```

Pull the model and build the sample index before starting the API:

```bash
docker compose exec ollama ollama pull gemma4:latest
docker compose run --rm api make sample
docker compose up --build -d api ui
```

The UI is at <http://localhost:8501>. The index in `./data` is mounted into the containers. Ollama, API, and UI ports bind to `127.0.0.1` by default; set `HOST_BIND_ADDRESS` only when intentionally exposing them behind network controls. If you change `OLLAMA_MODEL` in `.env`, use that same model name in the `ollama pull` command. Set `APP_UID` and `APP_GID` to the host account that owns `./data` before starting the API/index-build containers so the non-root container can write to the mounted directory.

## Manual install (without make)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set API_KEY to a generated secret before starting.
python scripts/build_sample_corpus.py
python indexer/build_index.py --articles data/sample/articles.jsonl --out-dir data/index
./start.sh
```

## Verify the installation

```bash
curl http://127.0.0.1:8000/health          # {"status":"ok"}
curl http://127.0.0.1:8000/health/ready   # checks the index and configured Ollama model
curl -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I get started?"}' \
  http://127.0.0.1:8000/chat
make eval                                  # API_KEY must be exported
```

`API_KEY` is a shared service token. It is not end-user authentication. The built-in rate limiter and generation cap are in-memory and per process; use an authenticated TLS reverse proxy and shared gateway-level limits for a multi-worker deployment.

## Choosing a model

Set `OLLAMA_MODEL` in `.env` to any model you have pulled (`ollama list`). Smaller models such as `llama3.2:3b` or `qwen2.5:3b` answer much faster on CPU. If you use a reasoning model, keep `OLLAMA_THINK=false` for responsive streaming.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ensurepip is not available` | `sudo apt install python3-venv`, then `rm -rf .venv && make install` |
| `could not connect to ollama server` | start it with `ollama serve` |
| `No index found` | run `make sample` or `./scripts/sync_kb.sh` |
| Very slow first answer | the model is loading and processing the prompt; use a smaller model |
| Port already in use | change `API_PORT` / `UI_PORT` in `.env`, then `make stop && make run` |
| `pip install` is slow | PyTorch is large; use a CPU wheel: `pip install torch --index-url https://download.pytorch.org/whl/cpu` first |
