from __future__ import annotations

from runtime.clarifier import generate_clarifications, is_ambiguous
from runtime.guardrail import GuardrailResult, ScopeGuardrail, build_guardrail


def test_is_ambiguous():
    assert is_ambiguous("help")
    assert is_ambiguous("what is it?")
    assert not is_ambiguous("How do I change the application name?")


def test_generate_clarifications_parses_json():
    result = generate_clarifications("it broke", lambda _prompt: 'noise ["A?", "B?", "C?", "D?"]')
    assert result == ["A?", "B?", "C?"]


def test_generate_clarifications_bad_output():
    assert generate_clarifications("it broke", lambda _prompt: "no json here") == []


def test_guardrail_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GUARDRAIL_ENABLED", raising=False)
    assert build_guardrail() is None


def test_guardrail_rejects_with_generic_message(monkeypatch):
    guard = ScopeGuardrail()
    monkeypatch.setattr(guard, "_classify", lambda _q: "OUT_OF_SCOPE")
    result: GuardrailResult = guard.check("Who won the match?")
    assert not result.allowed
    assert result.category == "out_of_scope"
    assert "ectigo" not in result.rejection_message


def test_guardrail_allows_on_error(monkeypatch):
    guard = ScopeGuardrail()

    def boom(_q):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(guard, "_classify", boom)
    assert guard.check("anything").allowed
