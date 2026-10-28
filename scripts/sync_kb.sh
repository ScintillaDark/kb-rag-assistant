#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

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

BASE_URL="${BASE_URL:-$(env_get KB_BASE_URL)}"
KB_ROOT="${KB_ROOT:-$(env_get KB_ROOT_URL)}"
if [[ -z "$BASE_URL" || -z "$KB_ROOT" ]]; then
  echo "Set KB_BASE_URL and KB_ROOT_URL in .env before syncing." >&2
  exit 1
fi
DISCOVERED_URLS="${DISCOVERED_URLS:-artifacts/discovered_urls.txt}"
RAW_DIR="${RAW_DIR:-data/raw_html}"
MANIFEST="${MANIFEST:-artifacts/crawl_manifest.jsonl}"
FAILED_URLS="${FAILED_URLS:-artifacts/failed_urls.txt}"
CLEAN_ARTICLES="${CLEAN_ARTICLES:-data/clean/articles.jsonl}"
INDEX_DIR="${INDEX_DIR:-data/index}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"

mkdir -p artifacts data/raw_html data/clean data/index

python3 ingest/discover_urls.py \
  --base-url "$BASE_URL" \
  --kb-root "$KB_ROOT" \
  --out "$DISCOVERED_URLS"

python3 ingest/crawl_kb.py \
  --url-file "$DISCOVERED_URLS" \
  --out-dir "$RAW_DIR" \
  --manifest "$MANIFEST" \
  --retries 2

python3 ingest/verify_crawl_coverage.py \
  --discovered "$DISCOVERED_URLS" \
  --manifest "$MANIFEST" \
  --failed-out "$FAILED_URLS" \
  --strict

python3 ingest/extract_articles.py \
  --input-dir "$RAW_DIR" \
  --manifest "$MANIFEST" \
  --out-file "$CLEAN_ARTICLES"

python3 indexer/build_index.py \
  --articles "$CLEAN_ARTICLES" \
  --out-dir "$INDEX_DIR" \
  --embedding-model "$EMBEDDING_MODEL"

echo "KB sync finished."
echo "Discovered URLs: $DISCOVERED_URLS"
echo "Crawl manifest: $MANIFEST"
echo "Clean articles: $CLEAN_ARTICLES"
echo "Index dir: $INDEX_DIR"
