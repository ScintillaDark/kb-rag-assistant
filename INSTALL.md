# Installation Guide

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.9+ | 3.10-3.12 recommended |
| [Ollama](https://ollama.com/download) | runs the local language model |
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
ollama pull gemma4:latest
make run
```

## Windows

Use WSL2 with Ubuntu and follow the Linux steps, or use Docker (below).

## Docker

```bash
docker compose up --build
```

This starts the API, the UI and an Ollama container. Pull a model once:

```bash
docker compose exec ollama ollama pull gemma4:latest
docker compose run --rm api make sample
```

The UI is at <http://localhost:8501>. The index in `./data` is mounted into the containers.

## Manual install (without make)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/build_sample_corpus.py
python indexer/build_index.py --articles data/sample/articles.jsonl --out-dir data/index
./start.sh
```

## Verify the installation

```bash
curl http://127.0.0.1:8000/health          # {"status":"ok"}
python eval/run_eval.py                    # optional quick evaluation
```

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
