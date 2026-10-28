from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.scoring import score_case, summarize  # noqa: E402


def load_questions(path: Path) -> list[dict]:
    questions = []
    seen_ids: set[str] = set()
    with open(path, "r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object.")
            if not isinstance(row.get("id"), str) or not row["id"]:
                raise ValueError(f"{path}:{line_number}: id must be a non-empty string.")
            if row["id"] in seen_ids:
                raise ValueError(f"{path}:{line_number}: duplicate id {row['id']!r}.")
            if not isinstance(row.get("question"), str) or not row["question"].strip():
                raise ValueError(f"{path}:{line_number}: question must be a non-empty string.")
            if row.get("expected_outcome") not in {"answer", "abstain"}:
                raise ValueError(f"{path}:{line_number}: expected_outcome must be answer or abstain.")
            if not isinstance(row.get("expected_sources", []), list):
                raise ValueError(f"{path}:{line_number}: expected_sources must be an array.")
            if not isinstance(row.get("answer_contains", []), list):
                raise ValueError(f"{path}:{line_number}: answer_contains must be an array.")
            seen_ids.add(row["id"])
            questions.append(row)
    if not questions:
        raise ValueError(f"No evaluation questions found in {path}.")
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval, citations, abstention, answer terms, and latency."
    )
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/chat")
    parser.add_argument("--out", default="artifacts/eval_results.jsonl")
    parser.add_argument("--min-outcome-accuracy", type=float)
    parser.add_argument("--min-retrieval-source-recall", type=float)
    parser.add_argument("--min-citation-source-recall", type=float)
    args = parser.parse_args()

    api_key = os.getenv("API_KEY", "").strip()
    if not api_key:
        parser.error("Set API_KEY in the environment before running the evaluation.")

    questions_path = Path(args.questions)
    questions = load_questions(questions_path)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with requests.Session() as session:
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        for question in questions:
            response = session.post(
                args.api_url,
                json={"question": question["question"]},
                timeout=(10, 900),
            )
            response.raise_for_status()
            payload = response.json()
            scored = score_case(question, payload)
            scored["question"] = question["question"]
            scored["expected_sources"] = question.get("expected_sources", [])
            results.append(scored)

    with open(output_path, "w", encoding="utf-8") as output:
        for result in results:
            output.write(json.dumps(result, ensure_ascii=False) + "\n")

    summary = summarize(results)
    summary.update(
        {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "api_url": args.api_url,
            "ollama_model": os.getenv("OLLAMA_MODEL", "gemma4:latest"),
            "embedding_model": os.getenv(
                "RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            "dataset": str(questions_path),
            "dataset_sha256": hashlib.sha256(questions_path.read_bytes()).hexdigest(),
            "results_file": str(output_path),
        }
    )
    summary_path = output_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    for metric, value in summary.items():
        if isinstance(value, float):
            print(f"{metric}: {value:.3f}")
    print(f"Results: {output_path}")
    print(f"Summary: {summary_path}")

    thresholds = (
        ("outcome_accuracy", args.min_outcome_accuracy),
        ("retrieval_source_recall", args.min_retrieval_source_recall),
        ("citation_source_recall", args.min_citation_source_recall),
    )
    failed = [
        f"{metric}={summary[metric]:.3f} is below {minimum:.3f}"
        for metric, minimum in thresholds
        if minimum is not None
        and (summary[metric] is None or summary[metric] < minimum)
    ]
    if failed:
        parser.exit(1, "Evaluation thresholds failed: " + "; ".join(failed) + "\n")


if __name__ == "__main__":
    main()
