from __future__ import annotations

import json
import logging
import secrets
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Iterator, Protocol

import requests
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from common.branding import get_branding
from common.settings import Settings
from runtime.guardrail import GuardrailResult, ScopeGuardrail, build_guardrail
from runtime.rag_service import LocalRAGService


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class HealthResponse(BaseModel):
    status: str


class RAGService(Protocol):
    ollama_base_url: str
    ollama_model: str

    def answer(self, question: str) -> dict[str, Any]: ...

    def answer_stream(self, question: str) -> Iterator[dict[str, Any]]: ...


logger = logging.getLogger(__name__)
_bearer_scheme = HTTPBearer(auto_error=False)


def build_local_service(settings: Settings) -> LocalRAGService:
    return LocalRAGService(
        index_dir=settings.index_dir,
        embedding_model=settings.embedding_model,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        top_k=settings.top_k,
        similarity_threshold=settings.similarity_threshold,
        min_sources=settings.min_sources,
        response_cache_ttl_seconds=settings.response_cache_ttl_seconds,
        response_cache_max_entries=settings.response_cache_max_entries,
        clarification_enabled=settings.clarification_enabled,
        web_search_enabled=settings.web_search_enabled,
        web_search_max_results=settings.web_search_max_results,
        answer_options_enabled=settings.answer_options_enabled,
        ollama_timeout=settings.ollama_timeout_seconds,
        ollama_think=settings.ollama_think,
    )


def build_local_guardrail(settings: Settings) -> ScopeGuardrail | None:
    return build_guardrail(
        enabled=settings.guardrail_enabled,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.guardrail_model,
        timeout=settings.guardrail_timeout_seconds,
        think=settings.ollama_think,
    )


ServiceFactory = Callable[[Settings], RAGService]
GuardrailFactory = Callable[[Settings], ScopeGuardrail | None]


def get_service(request: Request) -> RAGService:
    return request.app.state.service


def get_guardrail(request: Request) -> ScopeGuardrail | None:
    return request.app.state.guardrail


def require_api_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    settings: Settings = request.app.state.settings
    expected_key = settings.api_key
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

    limit = settings.api_rate_limit_per_minute
    client_ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    window = now // 60
    with request.app.state.rate_lock:
        rate_windows: OrderedDict[str, tuple[int, int]] = request.app.state.rate_windows
        current_window, count = rate_windows.get(client_ip, (window, 0))
        if current_window != window:
            current_window, count = window, 0
        if count >= limit:
            retry_after = 60 - (now % 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded.",
                headers={"Retry-After": str(retry_after)},
            )
        rate_windows[client_ip] = (current_window, count + 1)
        rate_windows.move_to_end(client_ip)
        while len(rate_windows) > 10_000:
            rate_windows.popitem(last=False)


def acquire_generation_slot(request: Request) -> None:
    generation_slots: threading.BoundedSemaphore = request.app.state.generation_slots
    if not generation_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation capacity is busy; retry shortly.",
            headers={"Retry-After": "5"},
        )


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


def health() -> HealthResponse:
    return HealthResponse(status="ok")


def readiness(request: Request, service: RAGService = Depends(get_service)) -> HealthResponse:
    settings: Settings = request.app.state.settings
    try:
        if not settings.api_key:
            raise RuntimeError("API_KEY is not configured.")
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


def root() -> dict:
    brand = get_branding()
    return {
        "name": f"{brand.app_name} API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "chat": "/chat",
    }


def _chat_response(
    payload: ChatRequest,
    service: RAGService,
    guardrail: ScopeGuardrail | None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if guardrail is not None:
        gate = guardrail.check(payload.question)
        if not gate.allowed:
            return {
                "question": payload.question,
                "answer": gate.rejection_message,
                "abstained": True,
                "abstain_reason": gate.category,
                "citations": [],
                "retrieval": [],
                "cache_hit": False,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "guardrail_blocked": True,
                "guardrail_category": gate.category,
                "clarification_questions": [],
                "answer_options": [],
                "web_search_used": False,
            }

    result = service.answer(payload.question)
    return {
        "question": payload.question,
        "answer": result["answer"],
        "abstained": result["abstained"],
        "abstain_reason": result["abstain_reason"],
        "citations": result["citations"],
        "retrieval": result["retrieval"],
        "cache_hit": result.get("cache_hit", False),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        "guardrail_blocked": False,
        "guardrail_category": "allowed",
        "clarification_questions": result.get("clarification_questions", []),
        "answer_options": result.get("answer_options", []),
        "web_search_used": result.get("web_search_used", False),
    }


def root_chat(
    payload: ChatRequest,
    request: Request,
    _: None = Depends(require_api_access),
) -> dict[str, Any]:
    acquire_generation_slot(request)
    try:
        return _chat_response(payload, get_service(request), get_guardrail(request))
    finally:
        request.app.state.generation_slots.release()


def chat_stream(
    request: Request,
    payload: ChatRequest,
    _: None = Depends(require_api_access),
    svc: RAGService = Depends(get_service),
    guardrail: ScopeGuardrail | None = Depends(get_guardrail),
) -> StreamingResponse:
    """Streaming endpoint — yields NDJSON token events then a final meta event."""
    acquire_generation_slot(request)

    def generate() -> Iterator[str]:
        try:
            # Guardrail check (no-op when GUARDRAIL_ENABLED != true)
            if guardrail is not None:
                gate: GuardrailResult = guardrail.check(payload.question)
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
            request.app.state.generation_slots.release()

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def chat(
    request: Request,
    payload: ChatRequest,
    _: None = Depends(require_api_access),
    service: RAGService = Depends(get_service),
    guardrail: ScopeGuardrail | None = Depends(get_guardrail),
) -> dict[str, Any]:
    acquire_generation_slot(request)
    try:
        return _chat_response(payload, service, guardrail)
    finally:
        request.app.state.generation_slots.release()


def create_app(
    settings: Settings | None = None,
    *,
    service_factory: ServiceFactory | None = None,
    guardrail_factory: GuardrailFactory | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.app_env in {"staging", "production"}:
        raise RuntimeError(
            f"APP_ENV={settings.app_env} is not available until production adapters are implemented."
        )
    if settings.app_env == "test" and service_factory is None:
        raise ValueError("Tests must inject a service_factory.")
    if settings.app_env == "test" and guardrail_factory is None:
        raise ValueError("Tests must inject a guardrail_factory.")

    selected_service_factory = (
        build_local_service if service_factory is None else service_factory
    )
    selected_guardrail_factory = (
        build_local_guardrail if guardrail_factory is None else guardrail_factory
    )
    brand = get_branding()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        application.state.service = selected_service_factory(settings)
        application.state.guardrail = selected_guardrail_factory(settings)
        yield

    application = FastAPI(
        title=f"{brand.app_name} API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.rate_lock = threading.Lock()
    application.state.rate_windows = OrderedDict()
    application.state.generation_slots = threading.BoundedSemaphore(
        settings.api_max_concurrent_generations
    )
    application.middleware("http")(log_request)
    application.add_api_route("/health", health, methods=["GET"], response_model=HealthResponse)
    application.add_api_route(
        "/health/ready", readiness, methods=["GET"], response_model=HealthResponse
    )
    application.add_api_route("/", root, methods=["GET"])
    application.add_api_route("/", root_chat, methods=["POST"])
    application.add_api_route("/chat/stream", chat_stream, methods=["POST"])
    application.add_api_route("/chat", chat, methods=["POST"])
    return application


app = create_app()
