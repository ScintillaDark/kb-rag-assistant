from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def simple_tokenize(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def split_sections(markdown_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = "Root"
    current_lines: list[str] = []

    for line in markdown_text.splitlines():
        if re.match(r"^#{1,4}\s+", line.strip()):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
                current_lines = []
            current_heading = line.strip().lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    return [(h, t) for h, t in sections if t]


def chunk_text(text: str, chunk_tokens: int, overlap_tokens: int) -> list[str]:
    tokens = simple_tokenize(text)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunk = " ".join(tokens[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(tokens):
            break
        start = max(end - overlap_tokens, start + 1)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build embeddings + FAISS index from extracted articles")
    parser.add_argument("--articles", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--embedding-model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--chunk-tokens", type=int, default=550)
    parser.add_argument("--overlap-tokens", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    with open(args.articles, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    chunks: list[dict[str, str | int]] = []
    for rec in records:
        sections = split_sections(rec["text"])
        if not sections:
            sections = [("Root", rec["text"])]

        for section_heading, section_text in sections:
            for chunk_idx, chunk in enumerate(
                chunk_text(section_text, args.chunk_tokens, args.overlap_tokens)
            ):
                chunk_id = f"{rec['article_id']}_{abs(hash(section_heading))}_{chunk_idx}"
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "article_id": rec["article_id"],
                        "title": rec["title"],
                        "url": rec["url"],
                        "heading_path": section_heading,
                        "text": chunk,
                        "token_count": len(simple_tokenize(chunk)),
                    }
                )

    if not chunks:
        raise RuntimeError("No chunks were generated. Check extraction output.")

    model = SentenceTransformer(args.embedding_model)
    texts = [c["text"] for c in chunks]
    vectors = model.encode(
        texts,
        batch_size=args.batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).astype("float32")

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    faiss.write_index(index, str(out_dir / "faiss.index"))
    np.save(out_dir / "embeddings.npy", vectors)

    with open(out_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    manifest = {
        "embedding_model": args.embedding_model,
        "total_articles": len(records),
        "total_chunks": len(chunks),
        "chunk_tokens": args.chunk_tokens,
        "overlap_tokens": args.overlap_tokens,
        "faiss_metric": "inner_product_cosine",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Indexed articles: {len(records)}")
    print(f"Generated chunks: {len(chunks)}")
    print(f"Index path: {out_dir / 'faiss.index'}")


if __name__ == "__main__":
    main()
