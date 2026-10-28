from __future__ import annotations

import math
from urllib.parse import urlparse


def _source_name(url: str) -> str:
    return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].casefold()


def score_case(expected: dict, response: dict) -> dict:
    expected_sources = {str(source).casefold() for source in expected.get("expected_sources", [])}
    retrieval_sources = {
        _source_name(str(hit.get("url", "")))
        for hit in response.get("retrieval", [])
        if hit.get("url")
    }
    citation_sources = {
        _source_name(str(citation.get("url", "")))
        for citation in response.get("citations", [])
        if citation.get("url")
    }
    answer = str(response.get("answer", "")).casefold()
    answer_terms = [str(term).casefold() for term in expected.get("answer_contains", [])]
    actual_abstained = bool(response.get("abstained", False))
    expected_abstained = expected.get("expected_outcome") == "abstain"

    return {
        "id": expected["id"],
        "expected_outcome": expected["expected_outcome"],
        "actual_abstained": actual_abstained,
        "abstain_reason": response.get("abstain_reason", ""),
        "outcome_correct": actual_abstained == expected_abstained,
        "retrieval_source_recall": (
            len(expected_sources & retrieval_sources) / len(expected_sources)
            if expected_sources
            else None
        ),
        "citation_source_recall": (
            len(expected_sources & citation_sources) / len(expected_sources)
            if expected_sources
            else None
        ),
        "answer_term_coverage": (
            sum(term in answer for term in answer_terms) / len(answer_terms)
            if answer_terms
            else None
        ),
        "latency_ms": response.get("latency_ms"),
        "citation_count": len(response.get("citations", [])),
        "answer": response.get("answer", ""),
    }


def summarize(results: list[dict]) -> dict:
    total = len(results)
    if not total:
        raise ValueError("Evaluation dataset is empty.")

    def average(key: str) -> float | None:
        values = [row[key] for row in results if row[key] is not None]
        return sum(values) / len(values) if values else None

    expected_abstentions = [row for row in results if row["expected_outcome"] == "abstain"]
    actual_abstentions = [row for row in results if row["actual_abstained"]]
    correct_abstentions = [row for row in expected_abstentions if row["outcome_correct"]]
    correct_answers = [
        row for row in results
        if row["expected_outcome"] == "answer" and row["outcome_correct"]
    ]
    latencies = sorted(row["latency_ms"] for row in results if row["latency_ms"] is not None)

    return {
        "questions": total,
        "outcome_accuracy": sum(row["outcome_correct"] for row in results) / total,
        "expected_abstention_recall": (
            len(correct_abstentions) / len(expected_abstentions)
            if expected_abstentions
            else None
        ),
        "abstention_precision": (
            len(correct_abstentions) / len(actual_abstentions)
            if actual_abstentions
            else None
        ),
        "answer_outcome_accuracy": (
            len(correct_answers) / (total - len(expected_abstentions))
            if total > len(expected_abstentions)
            else None
        ),
        "retrieval_source_recall": average("retrieval_source_recall"),
        "citation_source_recall": average("citation_source_recall"),
        "answer_term_coverage": average("answer_term_coverage"),
        "average_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "p95_latency_ms": latencies[math.ceil(len(latencies) * 0.95) - 1]
        if latencies
        else None,
    }
