from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)


class RobotsPolicy:
    def __init__(self, user_agent: str, timeout: int = 10) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._parsers: dict[str, RobotFileParser | None] = {}

    def can_fetch(self, url: str) -> bool:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        parser = self._parser_for_origin(origin)
        if parser is None:
            return False
        return parser.can_fetch(self.user_agent, url)

    def sitemaps(self, url: str) -> list[str]:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return []
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        parser = self._parser_for_origin(origin)
        if parser is None:
            return []
        return parser.site_maps() or []

    def _parser_for_origin(self, origin: str) -> RobotFileParser | None:
        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)
        return self._parsers[origin]

    def _load(self, origin: str) -> RobotFileParser | None:
        robots_url = f"{origin}/robots.txt"
        try:
            response = requests.get(
                robots_url,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            logger.warning("Unable to read robots.txt for %s: %s", origin, exc)
            return None

        if response.status_code in {401, 403}:
            parser = RobotFileParser(robots_url)
            parser.parse(["User-agent: *", "Disallow: /"])
            return parser
        if response.status_code == 404:
            parser = RobotFileParser(robots_url)
            parser.parse([])
            return parser
        if not 200 <= response.status_code < 300:
            logger.warning("robots.txt for %s returned HTTP %s; refusing to crawl.", origin, response.status_code)
            return None

        parser = RobotFileParser(robots_url)
        parser.parse(response.text.splitlines())
        return parser
