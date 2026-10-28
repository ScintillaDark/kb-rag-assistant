from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 4) -> list[dict]:
    """Search the web via DuckDuckGo and return structured results.

    Each result is a dict with keys: ``title``, ``url``, ``snippet``.

    Returns an empty list when:
    - ``duckduckgo-search`` is not installed (install with ``pip install duckduckgo-search``)
    - The network request fails for any reason

    Callers must handle the empty-list case gracefully.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning(
            "ddgs package not installed; web search disabled. "
            "Run: pip install ddgs"
        )
        return []

    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                url = r.get("href", "")
                if not url:
                    continue
                results.append({
                    "title": r.get("title", "Web Result"),
                    "url": url,
                    "snippet": r.get("body", ""),
                })
    except Exception as exc:
        logger.warning("Web search request failed: %s", exc)

    return results
