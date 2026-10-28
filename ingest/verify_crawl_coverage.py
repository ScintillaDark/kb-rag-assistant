from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_discovered(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_manifest(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows[row["url"]] = row
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify crawl completeness against discovered URLs")
    parser.add_argument("--discovered", required=True, help="Path to discovered_urls.txt")
    parser.add_argument("--manifest", required=True, help="Path to crawl_manifest.jsonl")
    parser.add_argument(
        "--failed-out",
        default="artifacts/failed_urls.txt",
        help="Path to write failed/missing URLs",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when coverage is incomplete",
    )
    args = parser.parse_args()

    discovered = load_discovered(Path(args.discovered))
    manifest = load_manifest(Path(args.manifest))

    missing: list[str] = []
    failed: list[str] = []

    for url in discovered:
        row = manifest.get(url)
        if row is None:
            missing.append(url)
            continue
        if row.get("status") != "ok":
            failed.append(url)

    total = len(discovered)
    ok = total - len(missing) - len(failed)
    coverage = (ok / total * 100.0) if total else 0.0

    print(f"Discovered URLs: {total}")
    print(f"Successfully fetched: {ok}")
    print(f"Missing from manifest: {len(missing)}")
    print(f"Failed fetches: {len(failed)}")
    print(f"Coverage: {coverage:.2f}%")

    failed_out = Path(args.failed_out)
    failed_out.parent.mkdir(parents=True, exist_ok=True)
    with open(failed_out, "w", encoding="utf-8") as f:
        for url in missing:
            f.write(url + "\n")
        for url in failed:
            f.write(url + "\n")

    print(f"Missing/failed URLs written to: {failed_out}")

    if args.strict and (missing or failed):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
