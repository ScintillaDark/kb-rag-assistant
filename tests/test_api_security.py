from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import runtime.app as api
from common.settings import Settings


def _create_test_app(
    *,
    api_key="test-secret",
    rate_limit=30,
    max_generations=2,
    service_factory=None,
):
    settings = Settings(
        app_env="test",
        api_key=api_key,
        api_rate_limit_per_minute=rate_limit,
        api_max_concurrent_generations=max_generations,
    )
    return api.create_app(
        settings,
        service_factory=service_factory or (lambda _settings: _FakeService()),
        guardrail_factory=lambda _settings: None,
    )


def test_chat_requires_a_bearer_key():
    application = _create_test_app()

    with TestClient(application) as client:
        response = client.post("/chat", json={"question": "Explain the product setup"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_chat_rejects_requests_when_api_key_is_unconfigured():
    application = _create_test_app(api_key=None)

    with TestClient(application) as client:
        response = client.post("/chat", json={"question": "Explain the product setup"})

    assert response.status_code == 503


def test_chat_is_rate_limited_per_client():
    application = _create_test_app(rate_limit=1)
    headers = {"Authorization": "Bearer test-secret"}

    with TestClient(application) as client:
        first = client.post("/chat", json={"question": "Explain the product setup"}, headers=headers)
        second = client.post("/chat", json={"question": "Explain the product setup"}, headers=headers)

    assert first.status_code == 200
    assert first.headers["x-request-id"]
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) > 0


def test_root_chat_alias_uses_injected_service_and_generation_limit():
    application = _create_test_app()

    with TestClient(application) as client:
        response = client.post(
            "/",
            json={"question": "Explain the product setup"},
            headers={"Authorization": "Bearer test-secret"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Grounded response"


def test_chat_stream_uses_injected_service_and_releases_generation_slot():
    application = _create_test_app(max_generations=1)

    with TestClient(application) as client:
        response = client.post(
            "/chat/stream",
            json={"question": "Explain the product setup"},
            headers={"Authorization": "Bearer test-secret"},
        )
        events = [json.loads(line) for line in response.text.splitlines()]
        slot_available = application.state.generation_slots.acquire(blocking=False)
        if slot_available:
            application.state.generation_slots.release()

    assert response.status_code == 200
    assert events[0] == {"type": "token", "text": "Grounded response"}
    assert events[-1]["type"] == "meta"
    assert slot_available is True


def test_readiness_requires_configured_dependencies(monkeypatch):
    application = _create_test_app()
    monkeypatch.setattr(api.requests, "get", lambda *_args, **_kwargs: _TagsResponse(["model:latest"]))

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200


def test_lifespan_builds_injected_rag_service():
    calls = []
    application = _create_test_app(
        service_factory=lambda _settings: calls.append("loaded") or _FakeService()
    )

    with TestClient(application):
        assert calls == ["loaded"]


def test_chat_rejects_when_generation_capacity_is_full():
    application = _create_test_app(max_generations=1)

    with TestClient(application) as client:
        assert application.state.generation_slots.acquire(blocking=False)
        try:
            response = client.post(
                "/chat",
                json={"question": "Explain the product setup"},
                headers={"Authorization": "Bearer test-secret"},
            )
        finally:
            application.state.generation_slots.release()

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"


def test_production_environment_is_rejected_until_adapters_exist():
    with pytest.raises(RuntimeError, match="production adapters"):
        api.create_app(Settings(app_env="production"))


class _FakeService:
    ollama_base_url = "http://ollama"
    ollama_model = "model"

    def answer(self, _question):
        return {
            "answer": "Grounded response",
            "abstained": False,
            "abstain_reason": "",
            "citations": [],
            "retrieval": [],
            "cache_hit": False,
            "clarification_questions": [],
            "answer_options": [],
            "web_search_used": False,
        }

    def answer_stream(self, _question):
        yield {"type": "token", "text": "Grounded response"}
        yield {"type": "meta", "final_answer": "Grounded response"}


class _TagsResponse:
    def __init__(self, names):
        self._names = names

    def raise_for_status(self):
        return None

    def json(self):
        return {"models": [{"name": name} for name in self._names]}
