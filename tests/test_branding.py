from __future__ import annotations

from common import branding


def _reload(monkeypatch, **env):
    for key in ("APP_NAME", "KB_DOMAIN", "KB_TOPICS", "KB_SUGGESTED_QUESTIONS", "KB_BASE_URL", "KB_ROOT_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    branding.get_branding.cache_clear()
    return branding.get_branding()


def test_defaults_are_generic(monkeypatch):
    brand = _reload(monkeypatch)
    assert brand.app_name == "KnowledgeBase Assistant"
    assert brand.base_url == ""
    assert brand.suggested_questions


def test_env_overrides(monkeypatch):
    brand = _reload(
        monkeypatch,
        APP_NAME="Acme Docs",
        KB_TOPICS="billing, setup",
        KB_SUGGESTED_QUESTIONS="One?|Two?",
        KB_ROOT_URL="https://docs.example.com/help/",
    )
    assert brand.app_name == "Acme Docs"
    assert brand.topics == ["billing", "setup"]
    assert brand.suggested_questions == ["One?", "Two?"]
    assert brand.kb_root_url == "https://docs.example.com/help"
    assert "Acme Docs" in brand.assistant_role
