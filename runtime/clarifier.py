from __future__ import annotations

import json
import re
from typing import Callable

from common.branding import get_branding

# Words that carry little semantic meaning on their own
_FILLER_WORDS = {
    "what", "how", "why", "when", "where", "who", "which", "is", "are",
    "was", "were", "can", "could", "would", "should", "do", "does", "did",
    "a", "an", "the", "i", "my", "me", "please", "tell", "explain",
    "describe", "show", "give", "help", "need", "want", "about", "this",
    "that", "it", "its", "get", "know", "find", "use", "using",
}


def is_ambiguous(question: str) -> bool:
    """Return True when the question is too vague to answer without clarification.

    Heuristics (any one triggers ambiguity):
    - Fewer than 4 words
    - Multiple question marks (compound questions)
    - Fewer than 2 content (non-filler) words
    """
    q = question.strip()
    if not q:
        return True

    # Compound question
    if q.count("?") >= 2:
        return True

    words = re.findall(r"\b\w+\b", q.lower())

    # Very short
    if len(words) < 4:
        return True

    # Almost entirely filler words
    content_words = [w for w in words if w not in _FILLER_WORDS]
    if len(content_words) < 2:
        return True

    return False


def generate_clarifications(question: str, llm_fn: Callable[[str], str]) -> list[str]:
    """Ask the LLM to produce up to 3 clarifying questions for an ambiguous query.

    Returns a list of strings. Returns an empty list if the LLM output cannot be
    parsed as a JSON array (caller should fall through to normal answering in that case).
    """
    brand = get_branding()
    prompt = (
        f"You are a helpful support assistant for the {brand.app_name} knowledge base ({brand.topics_text}).\n"
        "The user asked a question that is too vague to answer precisely.\n"
        "Generate exactly 3 short, targeted clarifying questions to understand what they need.\n"
        "Return ONLY a valid JSON array of strings — no extra text, no markdown fences.\n"
        'Example: ["Which product or version are you using?", '
        '"Which operating system?", '
        '"Are you seeing a specific error message?"]\n\n'
        f"User question: {question}\n\n"
        "Clarifying questions (JSON array only):"
    )

    raw = llm_fn(prompt)

    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if not match:
        return []

    try:
        items = json.loads(match.group(0))
        return [str(item).strip() for item in items if str(item).strip()][:3]
    except Exception:
        return []
