from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator

import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from common.branding import get_branding
from runtime.guardrail import GuardrailResult, ScopeGuardrail, build_guardrail
from runtime.rag_service import LocalRAGService


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class HealthResponse(BaseModel):
    status: str


_brand = get_branding()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_service()
    yield


app = FastAPI(title=f"{_brand.app_name} API", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)
_rate_lock = threading.Lock()
_rate_windows: OrderedDict[str, tuple[int, int]] = OrderedDict()
_max_concurrent_generations = int(os.getenv("API_MAX_CONCURRENT_GENERATIONS", "2"))
if _max_concurrent_generations < 1:
    raise RuntimeError("API_MAX_CONCURRENT_GENERATIONS must be at least 1.")
_generation_slots = threading.BoundedSemaphore(_max_concurrent_generations)

# Guardrail is None when GUARDRAIL_ENABLED != "true" (the default)
_guardrail: ScopeGuardrail | None = build_guardrail()


@lru_cache(maxsize=1)
def get_service() -> LocalRAGService:
    return LocalRAGService(
        index_dir=os.getenv("RAG_INDEX_DIR", "data/index"),
        embedding_model=os.getenv(
            "RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma4:latest"),
        top_k=int(os.getenv("RAG_TOP_K", "4")),
        similarity_threshold=float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.32")),
        min_sources=int(os.getenv("RAG_MIN_SOURCES", "2")),
        response_cache_ttl_seconds=int(os.getenv("RAG_RESPONSE_CACHE_TTL_SECONDS", "900")),
        response_cache_max_entries=int(os.getenv("RAG_RESPONSE_CACHE_MAX_ENTRIES", "128")),
        clarification_enabled=os.getenv("RAG_CLARIFICATION_ENABLED", "true").lower() == "true",
        web_search_enabled=os.getenv("WEB_SEARCH_ENABLED", "false").lower() == "true",
        web_search_max_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", "4")),
        answer_options_enabled=os.getenv("RAG_ANSWER_OPTIONS_ENABLED", "true").lower() == "true",
        ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "600")),
        ollama_think=os.getenv("OLLAMA_THINK", "false").lower() == "true",
    )


def require_api_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    expected_key = os.getenv("API_KEY", "").strip()
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured.",
        )
    if credentials is None or not secrets.compare_digest(credentials.credentials, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        limit = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "30"))
    except ValueError as exc:
        logger.error("API_RATE_LIMIT_PER_MINUTE must be an integer.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API rate limiting is misconfigured.",
        ) from exc
    if limit < 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API rate limiting is misconfigured.",
        )

    client_ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    window = now // 60
    with _rate_lock:
        current_window, count = _rate_windows.get(client_ip, (window, 0))
        if current_window != window:
            current_window, count = window, 0
        if count >= limit:
            retry_after = 60 - (now % 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded.",
                headers={"Retry-After": str(retry_after)},
            )
        _rate_windows[client_ip] = (current_window, count + 1)
        _rate_windows.move_to_end(client_ip)
        while len(_rate_windows) > 10_000:
            _rate_windows.popitem(last=False)


def acquire_generation_slot() -> None:
    if not _generation_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation capacity is busy; retry shortly.",
            headers={"Retry-After": "5"},
        )


@app.middleware("http")
async def log_request(request: Request, call_next):
    request_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.exception(
            "Unhandled request error request_id=%s path=%s",
            request_id,
            request.url.path,
        )
        raise
    finally:
        logger.info(
            "http_request %s",
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
                sort_keys=True,
            ),
        )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/health/ready", response_model=HealthResponse)
def readiness() -> HealthResponse:
    try:
        if not os.getenv("API_KEY", "").strip():
            raise RuntimeError("API_KEY is not configured.")
        service = get_service()
        response = requests.get(
            f"{service.ollama_base_url}/api/tags",
            timeout=(2, 5),
        )
        response.raise_for_status()
        available_models = {
            model.get("name", "").strip()
            for model in response.json().get("models", [])
            if isinstance(model, dict)
        }
        requested_model = service.ollama_model
        model_is_available = requested_model in available_models or (
            ":" not in requested_model and f"{requested_model}:latest" in available_models
        )
        if not model_is_available:
            raise RuntimeError(f"Configured Ollama model {requested_model!r} is not available.")
    except (OSError, requests.RequestException, ValueError, RuntimeError) as exc:
        logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required application dependencies are not ready.",
        ) from exc
    return HealthResponse(status="ok")


@app.get("/")
def root() -> dict:
    return {
        "name": f"{_brand.app_name} API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "chat": "/chat",
    }


@app.post("/")
def root_chat(payload: ChatRequest, _: None = Depends(require_api_access)) -> dict:
    return chat(payload)


@app.post("/chat/stream")
def chat_stream(
    payload: ChatRequest,
    _: None = Depends(require_api_access),
) -> StreamingResponse:
    """Streaming endpoint — yields NDJSON token events then a final meta event."""
    svc = get_service()
    acquire_generation_slot()

    def generate():
        try:
            # Guardrail check (no-op when GUARDRAIL_ENABLED != true)
            if _guardrail is not None:
                gate: GuardrailResult = _guardrail.check(payload.question)
                if not gate.allowed:
                    yield json.dumps({"type": "token", "text": gate.rejection_message}) + "\n"
                    yield json.dumps({
                        "type": "meta",
                        "final_answer": gate.rejection_message,
                        "citations": [],
                        "cache_hit": False,
                        "abstained": True,
                        "guardrail_blocked": True,
                        "guardrail_category": gate.category,
                        "clarification_questions": [],
                        "answer_options": [],
                        "web_search_used": False,
                    }) + "\n"
                    return

            for event in svc.answer_stream(payload.question):
                yield json.dumps(event) + "\n"
        finally:
            _generation_slots.release()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/chat")
def chat(payload: ChatRequest, _: None = Depends(require_api_access)) -> dict:
    acquire_generation_slot()
    t0 = time.perf_counter()

    try:
        # ── Scope guardrail (inactive unless GUARDRAIL_ENABLED=true) ──────────
        if _guardrail is not None:
            gate: GuardrailResult = _guardrail.check(payload.question)
            if not gate.allowed:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                return {
                    "question": payload.question,
                    "answer": gate.rejection_message,
                    "abstained": True,
                    "abstain_reason": gate.category,
                    "citations": [],
                    "retrieval": [],
                    "cache_hit": False,
                    "latency_ms": elapsed_ms,
                    "guardrail_blocked": True,
                    "guardrail_category": gate.category,
                    "clarification_questions": [],
                    "answer_options": [],
                    "web_search_used": False,
                }
        # ─────────────────────────────────────────────────────────────────────

        svc = get_service()
        result = svc.answer(payload.question)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "question": payload.question,
            "answer": result["answer"],
            "abstained": result["abstained"],
            "abstain_reason": result["abstain_reason"],
            "citations": result["citations"],
            "retrieval": result["retrieval"],
            "cache_hit": result.get("cache_hit", False),
            "latency_ms": elapsed_ms,
            "guardrail_blocked": False,
            "guardrail_category": "allowed",
            "clarification_questions": result.get("clarification_questions", []),
            "answer_options": result.get("answer_options", []),
            "web_search_used": result.get("web_search_used", False),
        }
    finally:
        _generation_slots.release()
