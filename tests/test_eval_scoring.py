from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from eval.run_eval import load_questions
from eval.scoring import score_case, summarize


def test_score_case_measures_sources_answers_and_abstention():
    expected = {
        "id": "getting-started",
        "expected_outcome": "answer",
        "expected_sources": ["getting-started"],
        "answer_contains": ["Ollama", "local"],
    }
    response = {
        "abstained": False,
        "abstain_reason": "",
        "answer": "Ollama runs locally.",
        "retrieval": [{"url": "https://example.com/docs/getting-started"}],
        "citations": [{"url": "https://example.com/docs/getting-started"}],
        "latency_ms": 125,
    }

    result = score_case(expected, response)

    assert result["outcome_correct"] is True
    assert result["abstain_reason"] == ""
    assert result["retrieval_source_recall"] == 1
    assert result["citation_source_recall"] == 1
    assert result["answer_term_coverage"] == 1


def test_summary_reports_outcome_and_source_metrics():
    rows = [
        {
            "expected_outcome": "abstain",
            "actual_abstained": True,
            "outcome_correct": True,
            "retrieval_source_recall": None,
            "citation_source_recall": None,
            "answer_term_coverage": None,
            "latency_ms": 100,
        },
        {
            "expected_outcome": "answer",
            "actual_abstained": False,
            "outcome_correct": True,
            "retrieval_source_recall": 1.0,
            "citation_source_recall": 0.5,
            "answer_term_coverage": 0.75,
            "latency_ms": 300,
        },
    ]

    result = summarize(rows)

    assert result["outcome_accuracy"] == 1
    assert result["expected_abstention_recall"] == 1
    assert result["abstention_precision"] == 1
    assert result["retrieval_source_recall"] == 1
    assert result["citation_source_recall"] == 0.5
    assert result["answer_term_coverage"] == 0.75
    assert result["p95_latency_ms"] == 300


def test_summary_uses_nearest_rank_for_p95_latency():
    rows = [
        {
            "expected_outcome": "answer",
            "actual_abstained": False,
            "outcome_correct": True,
            "retrieval_source_recall": None,
            "citation_source_recall": None,
            "answer_term_coverage": None,
            "latency_ms": latency,
        }
        for latency in range(1, 21)
    ]

    assert summarize(rows)["p95_latency_ms"] == 19


def test_load_questions_rejects_duplicate_ids(tmp_path):
    questions = tmp_path / "questions.jsonl"
    questions.write_text(
        '{"id":"same","question":"First question","expected_outcome":"answer"}\n'
        '{"id":"same","question":"Second question","expected_outcome":"answer"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate id"):
        load_questions(questions)


def test_repository_evaluation_set_has_expected_answer_and_abstention_cases():
    questions = load_questions(Path("eval/questions.jsonl"))

    assert len(questions) >= 20
    assert any(question["expected_outcome"] == "answer" for question in questions)
    assert any(question["expected_outcome"] == "abstain" for question in questions)


def test_evaluation_script_runs_directly_from_repository_root():
    script = Path("eval/run_eval.py").resolve()

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Evaluate retrieval" in completed.stdout
