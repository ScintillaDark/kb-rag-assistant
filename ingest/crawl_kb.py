from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.branding import get_branding  # noqa: E402


def load_urls(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def url_to_file_id(url: str) -> str:
    parsed = urlparse(url)
    canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Crawl KB pages and save raw HTML")
    parser.add_argument("--url-file", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    urls = load_urls(args.url_file)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": get_branding().user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    ok_count = 0
    error_count = 0

    with open(manifest_path, "w", encoding="utf-8") as mf:
        for idx, url in enumerate(urls, start=1):
            file_id = url_to_file_id(url)
            html_path = out_dir / f"{file_id}.html"

            status = "ok"
            code = None
            error = None
            content_hash = None

            attempt = 0
            while attempt <= args.retries:
                try:
                    resp = session.get(url, timeout=args.timeout)
                    code = resp.status_code
                    resp.raise_for_status()
                    html = resp.text
                    content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
                    html_path.write_text(html, encoding="utf-8")
                    status = "ok"
                    error = None
                    break
                except Exception as exc:
                    status = "error"
                    error = str(exc)
                    attempt += 1
                    if attempt <= args.retries:
                        time.sleep(min(2.0, args.sleep * (attempt + 1)))

            if status == "ok":
                ok_count += 1
            else:
                error_count += 1

            record = {
                "url": url,
                "file_id": file_id,
                "html_path": str(html_path),
                "status": status,
                "status_code": code,
                "content_hash": content_hash,
                "error": error,
            }
            mf.write(json.dumps(record, ensure_ascii=False) + "\n")

            if idx % 25 == 0:
                print(f"Processed {idx}/{len(urls)}")
            time.sleep(args.sleep)

    print(f"Crawl completed. Manifest: {manifest_path}")
    print(f"Fetched successfully: {ok_count}")
    print(f"Failed fetches: {error_count}")


if __name__ == "__main__":
    main()
