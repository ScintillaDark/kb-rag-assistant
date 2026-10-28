from __future__ import annotations

from ingest.robots import RobotsPolicy


class _Response:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_robots_policy_blocks_disallowed_paths(monkeypatch):
    monkeypatch.setattr(
        "ingest.robots.requests.get",
        lambda *_args, **_kwargs: _Response(200, "User-agent: *\nDisallow: /private"),
    )
    policy = RobotsPolicy("DemoBot")

    assert policy.can_fetch("https://docs.example.com/public")
    assert not policy.can_fetch("https://docs.example.com/private/page")


def test_robots_policy_fails_closed_when_robots_is_forbidden(monkeypatch):
    monkeypatch.setattr("ingest.robots.requests.get", lambda *_args, **_kwargs: _Response(403))
    policy = RobotsPolicy("DemoBot")

    assert not policy.can_fetch("https://docs.example.com/article")


def test_robots_policy_allows_missing_robots_file(monkeypatch):
    monkeypatch.setattr("ingest.robots.requests.get", lambda *_args, **_kwargs: _Response(404))
    policy = RobotsPolicy("DemoBot")

    assert policy.can_fetch("https://docs.example.com/article")


def test_robots_policy_fails_closed_for_temporary_errors(monkeypatch):
    monkeypatch.setattr("ingest.robots.requests.get", lambda *_args, **_kwargs: _Response(429))
    policy = RobotsPolicy("DemoBot")

    assert not policy.can_fetch("https://docs.example.com/article")


def test_robots_policy_reads_sitemap_directives(monkeypatch):
    monkeypatch.setattr(
        "ingest.robots.requests.get",
        lambda *_args, **_kwargs: _Response(200, "Sitemap: https://docs.example.com/sitemap.xml"),
    )
    policy = RobotsPolicy("DemoBot")

    assert policy.sitemaps("https://docs.example.com") == [
        "https://docs.example.com/sitemap.xml"
    ]


def test_robots_policy_rejects_non_http_urls():
    policy = RobotsPolicy("DemoBot")

    assert not policy.can_fetch("file:///etc/passwd")
