from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INDEX_DIR = ARTIFACTS_DIR / "index"
ARTICLES_FILE = ARTIFACTS_DIR / "articles.jsonl"

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_TOP_K = 6
DEFAULT_SIMILARITY_THRESHOLD = 0.28
DEFAULT_MIN_SOURCES = 2
