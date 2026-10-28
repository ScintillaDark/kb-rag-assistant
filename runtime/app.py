from __future__ import annotations

import json
import os
import time
from functools import lru_cache

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common.branding import get_branding
from runtime.guardrail import GuardrailResult, ScopeGuardrail, build_guardrail
from runtime.rag_service import LocalRAGService


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class HealthResponse(BaseModel):
    status: str


_brand = get_branding()
app = FastAPI(title=f"{_brand.app_name} API", version="0.1.0")

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


@app.on_event("startup")
def _warm_up() -> None:
    """Load the index and embedding model once at startup, not on the first request."""
    get_service()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
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
def root_chat(payload: ChatRequest) -> dict:
    return chat(payload)


@app.post("/chat/stream")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """Streaming endpoint — yields NDJSON token events then a final meta event."""
    svc = get_service()

    def generate():
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

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.post("/chat")
def chat(payload: ChatRequest) -> dict:
    t0 = time.perf_counter()

    # ── Scope guardrail (inactive unless GUARDRAIL_ENABLED=true) ──────────────
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
    # ─────────────────────────────────────────────────────────────────────────

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
