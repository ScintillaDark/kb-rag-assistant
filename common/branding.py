"""Central, environment-driven branding and domain settings.

Everything that is specific to a particular knowledge base (name, URLs,
subject area, suggested questions, logo) lives here and is read from
environment variables or a local ``.env`` file. See ``.env.example``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

DEFAULT_SUGGESTED_QUESTIONS = [
    "How do I get started?",
    "How do I change the app name and logo?",
    "How do I index my own documents?",
    "Why are answers slow on my machine?",
    "How does the architecture work?",
    "Is my data sent to external services?",
]


def _split(value: str, sep: str) -> list[str]:
    return [item.strip() for item in value.split(sep) if item.strip()]


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Branding:
    app_name: str = "KnowledgeBase Assistant"
    tagline: str = "Ask anything about the documentation. Answers run on a local LLM."
    domain: str = "the documentation in the knowledge base"
    topics: list[str] = field(default_factory=list)
    input_placeholder: str = "Ask a question..."
    icon_path: Path = PROJECT_ROOT / "assets" / "kb-icon.png"
    logo_path: Path = PROJECT_ROOT / "assets" / "kb-logo.svg"
    base_url: str = ""
    kb_root_url: str = ""
    user_agent: str = "KBAssistant-Crawler/1.0 (+offline rag demo)"
    suggested_questions: list[str] = field(default_factory=lambda: list(DEFAULT_SUGGESTED_QUESTIONS))

    @property
    def topics_text(self) -> str:
        return ", ".join(self.topics) if self.topics else self.domain

    @property
    def assistant_role(self) -> str:
        return f"a support assistant for the {self.app_name} knowledge base"


@lru_cache(maxsize=1)
def get_branding() -> Branding:
    env = os.getenv
    questions = _split(env("KB_SUGGESTED_QUESTIONS", ""), "|") or list(DEFAULT_SUGGESTED_QUESTIONS)
    defaults = Branding()
    return Branding(
        app_name=env("APP_NAME", defaults.app_name),
        tagline=env("APP_TAGLINE", defaults.tagline),
        domain=env("KB_DOMAIN", defaults.domain),
        topics=_split(env("KB_TOPICS", ""), ","),
        input_placeholder=env("APP_INPUT_PLACEHOLDER", defaults.input_placeholder),
        icon_path=_resolve_path(env("APP_ICON_PATH", str(defaults.icon_path))),
        logo_path=_resolve_path(env("APP_LOGO_PATH", str(defaults.logo_path))),
        base_url=env("KB_BASE_URL", "").rstrip("/"),
        kb_root_url=env("KB_ROOT_URL", "").rstrip("/"),
        user_agent=env("KB_USER_AGENT", defaults.user_agent),
        suggested_questions=questions,
    )
