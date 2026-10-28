"""
Scope Guardrail — pre-processing layer that classifies whether a user question
is within the chatbot's configured scope before it reaches the RAG pipeline.

Design goals
────────────
• Lightest possible LLM usage: forces a SINGLE token (ALLOW / REJECT) via
  num_predict=3 and temperature=0.
• Inactive by default: controlled by the GUARDRAIL_ENABLED env-var (default false).
  When disabled the layer is a pure pass-through with zero latency cost.
• Clear rejection categories surfaced to the caller so the UI can show a
  meaningful message.

Rejected categories
───────────────────
  out_of_scope    – completely unrelated topics (sports, food, travel, etc.)
  code_generation – requests to write/generate code, scripts, programs
  media_generation– requests to create images, video, audio, documents
  general_chat    – casual conversation, jokes, general trivia, homework help

Allowed categories
──────────────────
  Anything within KB_DOMAIN / KB_TOPICS (see .env), plus related installation,
  configuration and troubleshooting questions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests

from common.branding import get_branding

# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    allowed: bool
    category: str          # "allowed" | "out_of_scope" | "code_generation" |
                           #  "media_generation" | "general_chat" | "error"
    rejection_message: str # Empty string when allowed=True


# ── Rejection messages (user-facing, friendly) ───────────────────────────────

def _rejection_messages() -> dict[str, str]:
    brand = get_branding()
    return {
        "out_of_scope": (
            f"I'm specialised in {brand.domain}. "
            "That topic falls outside what I can help with — please ask something "
            "related to the knowledge base."
        ),
        "code_generation": (
            "I'm not able to write or generate code on request. "
            f"I can help you understand {brand.domain}, configuration steps, or "
            "troubleshoot issues instead."
        ),
        "media_generation": (
            "I can't generate images, videos, or other media. "
            f"Let me know if you have a question about {brand.domain}."
        ),
        "general_chat": (
            f"I'm focused on {brand.domain}. "
            "Feel free to ask me anything about those topics."
        ),
    }


def _fallback_rejection() -> str:
    return f"That question is outside my scope. I can help with {get_branding().domain}."


# ── Classifier prompt ─────────────────────────────────────────────────────────

_CLASSIFICATION_PROMPT = """\
You are a strict scope classifier for the {app_name} chatbot.

ALLOWED topics (reply ALLOW):
- {topics}
- Installation, configuration, usage and troubleshooting related to the above
- General questions that a user of this knowledge base would reasonably ask

REJECT topics — reply with exactly the category word:
- OUT_OF_SCOPE  : sports, cooking, travel, news, entertainment, finance, medicine, or any topic unrelated to the allowed topics
- CODE_GENERATION: "write me code", "generate a script", "implement this function", programming homework
- MEDIA_GENERATION: generate an image, video, audio, PDF, PowerPoint, or any file
- GENERAL_CHAT  : jokes, small talk, greetings only, trivia, homework unrelated to the allowed topics

Reply with EXACTLY one of: ALLOW, OUT_OF_SCOPE, CODE_GENERATION, MEDIA_GENERATION, GENERAL_CHAT
No explanation. No punctuation. One word only.

User message: {question}
Answer:"""


# ── Guardrail class ───────────────────────────────────────────────────────────

class ScopeGuardrail:
    """
    Thin wrapper around a local Ollama call that classifies questions.

    Parameters
    ----------
    ollama_base_url : str
        URL of the Ollama server (e.g. "http://localhost:11434").
    ollama_model : str
        Model to use for classification. Any model works; smaller/faster is
        better since we only need a single token.
    timeout : int
        HTTP timeout in seconds for the classification call.
    """

    def __init__(
        self,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "gemma4:latest",
        timeout: int = 15,
    ) -> None:
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_model = ollama_model
        self.timeout = timeout

    def _classify(self, question: str) -> str:
        """Call Ollama and return the raw classification token."""
        brand = get_branding()
        prompt = _CLASSIFICATION_PROMPT.format(
            app_name=brand.app_name, topics=brand.topics_text, question=question.strip()
        )
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "think": os.getenv("OLLAMA_THINK", "false").lower() == "true",
            "options": {
                "temperature": 0,
                "num_predict": 10,   # force a very short response
                "top_k": 1,          # greedy — fastest single-token generation
            },
        }
        resp = requests.post(
            f"{self.ollama_base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        raw: str = resp.json().get("response", "").strip().upper()
        # Extract the first recognised token in case the model adds punctuation
        for token in ("ALLOW", "OUT_OF_SCOPE", "CODE_GENERATION", "MEDIA_GENERATION", "GENERAL_CHAT"):
            if token in raw:
                return token
        # Fallback: if the model said something unexpected, allow and log
        return "ALLOW"

    def check(self, question: str) -> GuardrailResult:
        """
        Classify a question and return a GuardrailResult.

        Never raises — on any error the question is allowed through so the
        guardrail failure is transparent to the user.
        """
        try:
            label = self._classify(question)
        except Exception:
            # On timeout or any other error: allow through silently
            return GuardrailResult(allowed=True, category="error", rejection_message="")

        if label == "ALLOW":
            return GuardrailResult(allowed=True, category="allowed", rejection_message="")

        category_key = label.lower()
        rejection_message = _rejection_messages().get(category_key, _fallback_rejection())
        return GuardrailResult(allowed=False, category=category_key, rejection_message=rejection_message)


# ── Module-level helpers ──────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Return True only when GUARDRAIL_ENABLED=true (case-insensitive)."""
    return os.getenv("GUARDRAIL_ENABLED", "false").strip().lower() == "true"


def build_guardrail() -> Optional[ScopeGuardrail]:
    """
    Construct a ScopeGuardrail if GUARDRAIL_ENABLED=true, else return None.

    Usage in app.py:
        guardrail = build_guardrail()   # called once at startup

        # per request:
        if guardrail:
            result = guardrail.check(question)
            if not result.allowed:
                return {"answer": result.rejection_message, ...}
    """
    if not is_enabled():
        return None
    return ScopeGuardrail(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("GUARDRAIL_MODEL", os.getenv("OLLAMA_MODEL", "gemma4:latest")),
        timeout=int(os.getenv("GUARDRAIL_TIMEOUT", "15")),
    )
