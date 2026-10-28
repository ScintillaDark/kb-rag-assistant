from __future__ import annotations

import threading

from fastapi.testclient import TestClient

import runtime.app as api


def _reset_rate_limits():
    with api._rate_lock:
        api._rate_windows.clear()


def test_chat_requires_a_bearer_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret")
    _reset_rate_limits()

    response = TestClient(api.app).post("/chat", json={"question": "Explain the product setup"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_chat_rejects_requests_when_api_key_is_unconfigured(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    _reset_rate_limits()

    response = TestClient(api.app).post("/chat", json={"question": "Explain the product setup"})

    assert response.status_code == 503


def test_chat_is_rate_limited_per_client(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret")
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setattr(api, "get_service", lambda: _FakeService())
    _reset_rate_limits()
    headers = {"Authorization": "Bearer test-secret"}
    client = TestClient(api.app)

    first = client.post("/chat", json={"question": "Explain the product setup"}, headers=headers)
    second = client.post("/chat", json={"question": "Explain the product setup"}, headers=headers)

    assert first.status_code == 200
    assert first.headers["x-request-id"]
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) > 0


def test_readiness_requires_configured_dependencies(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret")
    monkeypatch.setattr(
        api,
        "get_service",
        lambda: type("Service", (), {"ollama_base_url": "http://ollama", "ollama_model": "model"})(),
    )
    monkeypatch.setattr(api.requests, "get", lambda *_args, **_kwargs: _TagsResponse(["model:latest"]))

    response = TestClient(api.app).get("/health/ready")

    assert response.status_code == 200


def test_lifespan_loads_rag_service(monkeypatch):
    calls = []
    monkeypatch.setattr(api, "get_service", lambda: calls.append("loaded"))

    with TestClient(api.app):
        assert calls == ["loaded"]


def test_chat_rejects_when_generation_capacity_is_full(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-secret")
    monkeypatch.setattr(api, "_generation_slots", threading.BoundedSemaphore(1))
    assert api._generation_slots.acquire(blocking=False)

    try:
        response = TestClient(api.app).post(
            "/chat",
            json={"question": "Explain the product setup"},
            headers={"Authorization": "Bearer test-secret"},
        )
    finally:
        api._generation_slots.release()

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"


class _FakeService:
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


class _TagsResponse:
    def __init__(self, names):
        self._names = names

    def raise_for_status(self):
        return None

    def json(self):
        return {"models": [{"name": name} for name in self._names]}
