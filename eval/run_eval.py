from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def load_questions(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run basic eval against local RAG API")
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--api-url", default="http://localhost:8000/chat")
    parser.add_argument("--out", default="artifacts/eval_results.jsonl")
    args = parser.parse_args()

    questions = load_questions(Path(args.questions))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for q in questions:
        resp = requests.post(args.api_url, json={"question": q["question"]}, timeout=180)
        resp.raise_for_status()
        data = resp.json()

        row = {
            "id": q["id"],
            "category": q.get("category", "unknown"),
            "question": q["question"],
            "abstained": data.get("abstained", False),
            "latency_ms": data.get("latency_ms"),
            "citation_count": len(data.get("citations", [])),
            "answer": data.get("answer", ""),
        }
        results.append(row)

    with open(out_path, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    total = len(results)
    abstained = sum(1 for r in results if r["abstained"])
    with_citations = sum(1 for r in results if r["citation_count"] > 0)
    avg_latency = (
        sum((r["latency_ms"] or 0) for r in results) / total if total else 0
    )

    print(f"Questions: {total}")
    print(f"Abstained: {abstained}")
    print(f"With citations: {with_citations}")
    print(f"Average latency ms: {avg_latency:.2f}")
    print(f"Saved results to: {out_path}")


if __name__ == "__main__":
    main()
