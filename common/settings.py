from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ENVIRONMENTS = {"local", "test", "staging", "production"}


def _read_bool(values: Mapping[str, str], name: str, default: bool) -> bool:
    value = values.get(name, str(default)).strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be 'true' or 'false'.")
    return value == "true"


def _read_int(values: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(values.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _read_float(values: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(values.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc


@dataclass(frozen=True)
class Settings:
    app_env: str = "local"
    api_key: str | None = field(default=None, repr=False)
    api_rate_limit_per_minute: int = 30
    api_max_concurrent_generations: int = 2
    index_dir: str = "data/index"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:latest"
    top_k: int = 4
    similarity_threshold: float = 0.32
    min_sources: int = 2
    response_cache_ttl_seconds: int = 900
    response_cache_max_entries: int = 128
    clarification_enabled: bool = True
    web_search_enabled: bool = False
    web_search_max_results: int = 4
    answer_options_enabled: bool = True
    ollama_timeout_seconds: int = 600
    ollama_think: bool = False
    guardrail_enabled: bool = False
    guardrail_model: str = "gemma4:latest"
    guardrail_timeout_seconds: int = 15

    def __post_init__(self) -> None:
        if self.app_env not in APP_ENVIRONMENTS:
            allowed = ", ".join(sorted(APP_ENVIRONMENTS))
            raise ValueError(f"APP_ENV must be one of: {allowed}.")
        for name in (
            "api_rate_limit_per_minute",
            "api_max_concurrent_generations",
            "top_k",
            "min_sources",
            "web_search_max_results",
            "ollama_timeout_seconds",
            "guardrail_timeout_seconds",
            "response_cache_max_entries",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1.")
        if self.response_cache_ttl_seconds < 0:
            raise ValueError("response_cache_ttl_seconds must not be negative.")
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1.")
        if not self.index_dir.strip():
            raise ValueError("index_dir must not be empty.")
        if not self.ollama_base_url.strip():
            raise ValueError("ollama_base_url must not be empty.")
        if not self.ollama_model.strip():
            raise ValueError("ollama_model must not be empty.")
        if self.guardrail_enabled and not self.guardrail_model.strip():
            raise ValueError("guardrail_model must not be empty when the guardrail is enabled.")

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> Settings:
        if values is None:
            load_dotenv(PROJECT_ROOT / ".env", override=False)
            values = os.environ

        api_key = values.get("API_KEY", "").strip() or None
        ollama_model = values.get("OLLAMA_MODEL", "gemma4:latest").strip()
        return cls(
            app_env=values.get("APP_ENV", "local").strip().lower(),
            api_key=api_key,
            api_rate_limit_per_minute=_read_int(values, "API_RATE_LIMIT_PER_MINUTE", 30),
            api_max_concurrent_generations=_read_int(
                values, "API_MAX_CONCURRENT_GENERATIONS", 2
            ),
            index_dir=values.get("RAG_INDEX_DIR", "data/index"),
            embedding_model=values.get(
                "RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            ollama_base_url=values.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=ollama_model,
            top_k=_read_int(values, "RAG_TOP_K", 4),
            similarity_threshold=_read_float(values, "RAG_SIMILARITY_THRESHOLD", 0.32),
            min_sources=_read_int(values, "RAG_MIN_SOURCES", 2),
            response_cache_ttl_seconds=_read_int(
                values, "RAG_RESPONSE_CACHE_TTL_SECONDS", 900
            ),
            response_cache_max_entries=_read_int(
                values, "RAG_RESPONSE_CACHE_MAX_ENTRIES", 128
            ),
            clarification_enabled=_read_bool(values, "RAG_CLARIFICATION_ENABLED", True),
            web_search_enabled=_read_bool(values, "WEB_SEARCH_ENABLED", False),
            web_search_max_results=_read_int(values, "WEB_SEARCH_MAX_RESULTS", 4),
            answer_options_enabled=_read_bool(
                values, "RAG_ANSWER_OPTIONS_ENABLED", True
            ),
            ollama_timeout_seconds=_read_int(values, "OLLAMA_TIMEOUT", 600),
            ollama_think=_read_bool(values, "OLLAMA_THINK", False),
            guardrail_enabled=_read_bool(values, "GUARDRAIL_ENABLED", False),
            guardrail_model=values.get("GUARDRAIL_MODEL", ollama_model),
            guardrail_timeout_seconds=_read_int(values, "GUARDRAIL_TIMEOUT", 15),
        )
