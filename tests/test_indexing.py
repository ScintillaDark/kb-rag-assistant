from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from indexer.build_index import chunk_identifier, chunk_text, split_sections

ROOT = Path(__file__).resolve().parents[1]


def test_split_sections_and_chunking():
    sections = split_sections("# Title\nintro\n## Part\nbody text here")
    assert [h for h, _ in sections] == ["Title", "Part"]
    chunks = chunk_text("one two three four five six", chunk_tokens=4, overlap_tokens=1)
    assert chunks[0] == "one two three four"
    assert len(chunks) == 2


def test_chunk_identifiers_are_stable():
    identifier = chunk_identifier("article-1", "Setup", 0)

    assert identifier == chunk_identifier("article-1", "Setup", 0)
    assert identifier != chunk_identifier("article-1", "Troubleshooting", 0)
    assert identifier != chunk_identifier("article-1", "Setup", 1)


def test_sample_corpus_builder(tmp_path):
    out = tmp_path / "articles.jsonl"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_sample_corpus.py"),
         "--docs-dir", str(ROOT / "sample_data" / "docs"), "--out", str(out)],
        check=True,
    )
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) >= 5
    assert all(r["url"].startswith("https://example.com/docs/") and r["title"] for r in rows)
