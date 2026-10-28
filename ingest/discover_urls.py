from __future__ import annotations

import argparse
import os
import sys
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.branding import get_branding  # noqa: E402


def kb_path_of(kb_root: str) -> str:
    """URL path prefix that identifies KB pages, derived from the KB root URL."""
    return urlparse(kb_root).path.rstrip("/") or ""


def fetch_sitemap_urls(base_url: str, timeout: int = 20) -> list[str]:
    robots_url = urljoin(base_url, "/robots.txt")
    resp = requests.get(robots_url, timeout=timeout)
    resp.raise_for_status()

    sitemap_urls: list[str] = []
    for line in resp.text.splitlines():
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            sitemap = line.split(":", 1)[1].strip()
            if sitemap:
                sitemap_urls.append(sitemap)
    return sitemap_urls


def parse_xml_links(xml_text: str) -> list[str]:
    soup = BeautifulSoup(xml_text, "xml")
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")]


def discover_from_sitemaps(
    base_url: str,
    kb_path: str,
    timeout: int = 20,
    max_sitemaps: int = 250,
) -> set[str]:
    discovered: set[str] = set()
    queue = deque(fetch_sitemap_urls(base_url, timeout=timeout))
    seen = set(queue)
    processed = 0

    while queue and processed < max_sitemaps:
        sitemap_url = queue.popleft()
        processed += 1
        try:
            resp = requests.get(sitemap_url, timeout=timeout)
            resp.raise_for_status()
        except Exception:
            continue

        links = parse_xml_links(resp.text)
        if any(link.endswith(".xml") for link in links):
            for link in links:
                if not link.endswith(".xml") or link in seen:
                    continue

                # Prefer KB-related sitemap trees first for faster convergence.
                if kb_path.strip("/") in link or "sitemap" in link:
                    seen.add(link)
                    queue.append(link)
            continue

        for link in links:
            if f"{kb_path}/" in link:
                discovered.add(link)

    print(f"Sitemap traversal processed: {processed}")

    return discovered


def discover_from_kb_pages(
    kb_root: str,
    timeout: int = 20,
    max_pages: int = 120,
    article_segment: str = "detail",
    listing_segment: str = "product",
) -> set[str]:
    kb_path = kb_path_of(kb_root)
    to_visit = deque([kb_root])
    seen = {kb_root}
    discovered: set[str] = set()

    while to_visit and len(seen) <= max_pages:
        url = to_visit.popleft()
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
        except Exception:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = urljoin(url, a_tag["href"])
            parsed = urlparse(href)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

            if f"{kb_path}/" not in normalized:
                continue

            if f"{kb_path}/{article_segment}/" in normalized:
                discovered.add(normalized)
            elif f"{kb_path}/{listing_segment}/" in normalized:
                if normalized not in seen:
                    seen.add(normalized)
                    to_visit.append(normalized)
            elif normalized.rstrip("/") == kb_root.rstrip("/") and normalized not in seen:
                seen.add(normalized)
                to_visit.append(normalized)

    return discovered


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover knowledge-base article URLs")
    brand = get_branding()
    parser.add_argument("--base-url", default=brand.base_url, help="Base site URL (env: KB_BASE_URL)")
    parser.add_argument("--kb-root", default=brand.kb_root_url, help="KB root URL (env: KB_ROOT_URL)")
    parser.add_argument("--article-segment", default=os.getenv("KB_ARTICLE_SEGMENT", "detail"),
                        help="URL segment under the KB root that marks an article page (env: KB_ARTICLE_SEGMENT)")
    parser.add_argument("--listing-segment", default=os.getenv("KB_LISTING_SEGMENT", "product"),
                        help="URL segment under the KB root that marks a listing page (env: KB_LISTING_SEGMENT)")
    parser.add_argument("--out", required=True, help="Output file path for discovered URLs")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--max-sitemaps", type=int, default=250)
    parser.add_argument("--max-kb-pages", type=int, default=240)
    args = parser.parse_args()
    if not args.base_url or not args.kb_root:
        parser.error("set KB_BASE_URL and KB_ROOT_URL in .env, or pass --base-url and --kb-root")

    from_sitemaps = discover_from_sitemaps(
        args.base_url,
        kb_path_of(args.kb_root),
        timeout=args.timeout,
        max_sitemaps=args.max_sitemaps,
    )
    print(f"KB URLs from sitemap sources: {len(from_sitemaps)}")

    from_kb_pages = discover_from_kb_pages(
        args.kb_root,
        timeout=args.timeout,
        max_pages=args.max_kb_pages,
        article_segment=args.article_segment,
        listing_segment=args.listing_segment,
    )
    print(f"KB URLs from page traversal: {len(from_kb_pages)}")

    urls = sorted(from_sitemaps | from_kb_pages)

    with open(args.out, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")

    print(f"Discovered {len(urls)} KB article URLs")


if __name__ == "__main__":
    main()
