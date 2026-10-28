from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import trafilatura
from bs4 import BeautifulSoup


def strip_noise(soup: BeautifulSoup) -> None:
    for tag in soup.select("nav, footer, script, style, noscript, form, aside"):
        tag.decompose()

    noise_selectors = [
        "[class*='header']",
        "[class*='footer']",
        "[class*='breadcrumb']",
        "[class*='chat']",
        "[class*='cookie']",
        "[class*='menu']",
        "[class*='subscribe']",
    ]
    for selector in noise_selectors:
        for tag in soup.select(selector):
            tag.decompose()


def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    title = soup.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(strip=True)
    return "Untitled"


def extract_text_with_trafilatura(html: str) -> str | None:
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="txt",
    )
    if not extracted:
        return None
    text = re.sub(r"\n{3,}", "\n\n", extracted).strip()
    return text or None


def extract_text_with_bs4(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    strip_noise(soup)
    title = extract_title(soup)

    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main is None:
        return title, ""

    lines: list[str] = []
    for tag in main.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if tag.name.startswith("h"):
            level = int(tag.name[1])
            lines.append("#" * min(level, 4) + " " + text)
        else:
            lines.append(text)

    merged = "\n".join(lines)
    merged = re.sub(r"\n{3,}", "\n\n", merged).strip()
    return title, merged


def load_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract clean KB article text from HTML snapshots")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-file", required=True)
    parser.add_argument("--min-chars", type=int, default=250)
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    manifest = load_manifest(Path(args.manifest))
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    skipped = 0

    with open(out_file, "w", encoding="utf-8") as out:
        for row in manifest:
            if row.get("status") != "ok":
                continue

            html_path = Path(row["html_path"])
            if not html_path.exists():
                alt_path = input_dir / f"{row['file_id']}.html"
                if not alt_path.exists():
                    skipped += 1
                    continue
                html_path = alt_path

            html = html_path.read_text(encoding="utf-8", errors="ignore")
            bs4_title, bs4_text = extract_text_with_bs4(html)
            tf_text = extract_text_with_trafilatura(html)

            text = tf_text if tf_text and len(tf_text) > len(bs4_text) else bs4_text
            if len(text) < args.min_chars:
                skipped += 1
                continue

            article_id = hashlib.sha1(row["url"].encode("utf-8")).hexdigest()
            record = {
                "article_id": article_id,
                "url": row["url"],
                "title": bs4_title,
                "text": text,
                "content_hash": row.get("content_hash"),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1

    print(f"Extracted articles: {kept}")
    print(f"Skipped pages: {skipped}")


if __name__ == "__main__":
    main()
