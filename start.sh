#!/usr/bin/env bash
# Start the API and the chat UI in the background. Settings come from .env.
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Read a single KEY from .env without sourcing it (values may contain spaces).
env_get() {
  local key="$1" default="${2:-}" val=""
  if [[ -f .env ]]; then
    val="$(grep -E "^${key}=" .env | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true)"
  fi
  echo "${!key:-${val:-$default}}"
}

API_HOST="$(env_get API_HOST 127.0.0.1)"
API_PORT="$(env_get API_PORT 8000)"
UI_PORT="$(env_get UI_PORT 8501)"
INDEX_DIR="$(env_get RAG_INDEX_DIR data/index)"
export RAG_API_URL="$(env_get RAG_API_URL "http://${API_HOST}:${API_PORT}/chat")"

mkdir -p logs

if [[ ! -f "${INDEX_DIR}/faiss.index" ]]; then
  echo "No index found in ${INDEX_DIR}. Run 'make sample' (demo) or './scripts/sync_kb.sh' first." >&2
  exit 1
fi

./stop.sh >/dev/null 2>&1 || true
sleep 1

echo "Starting API on ${API_HOST}:${API_PORT}..."
nohup python3 -m uvicorn runtime.app:app --host "$API_HOST" --port "$API_PORT" \
  > logs/api.log 2>&1 &
echo $! > logs/api.pid

echo "Waiting for API..."
for _ in $(seq 1 60); do
  if python3 - "$API_HOST" "$API_PORT" <<'PY' 2>/dev/null
import sys, urllib.request
urllib.request.urlopen(f"http://{sys.argv[1]}:{sys.argv[2]}/health", timeout=2)
PY
  then
    echo "API is up."
    break
  fi
  sleep 1
done

echo "Starting UI on port ${UI_PORT}..."
nohup python3 -m streamlit run ui/chat_app.py --server.headless true --server.port "$UI_PORT" \
  > logs/ui.log 2>&1 &
echo $! > logs/ui.pid

echo
echo "Chat UI -> http://localhost:${UI_PORT}"
echo "API     -> http://${API_HOST}:${API_PORT}/docs"
echo "Logs    -> logs/api.log  logs/ui.log"
echo "Stop    -> ./stop.sh"
