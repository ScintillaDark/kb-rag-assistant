"""Convert a folder of Markdown files into the articles.jsonl format used by the indexer.

Each file becomes one article. The first Markdown heading is used as the title and
the file name (without extension) becomes the last part of the URL.

    python scripts/build_sample_corpus.py \
        --docs-dir sample_data/docs --out data/sample/articles.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs-dir", default="sample_data/docs")
    parser.add_argument("--out", default="data/sample/articles.jsonl")
    parser.add_argument("--url-prefix", default="https://example.com/docs/")
    args = parser.parse_args()

    files = sorted(Path(args.docs_dir).glob("*.md"))
    if not files:
        raise SystemExit(f"No .md files found in {args.docs_dir}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for path in files:
            text = path.read_text(encoding="utf-8").strip()
            match = re.match(r"#\s+(.+)", text)
            title = match.group(1).strip() if match else path.stem.replace("-", " ").title()
            record = {
                "article_id": hashlib.sha1(path.stem.encode()).hexdigest(),
                "url": f"{args.url_prefix.rstrip('/')}/{path.stem}",
                "title": title,
                "text": text,
                "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(files)} articles to {out}")


if __name__ == "__main__":
    main()
