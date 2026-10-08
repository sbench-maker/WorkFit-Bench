#!/usr/bin/env python3
"""Offline search/fetch interface for the constructed documentation snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
BASE_HOST = "www.remotion.dev"


def tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def search(query: str, limit: int) -> int:
    payload = json.loads((ROOT / "search_index.json").read_text(encoding="utf-8"))
    query_tokens = tokens(query)
    scored = []
    for position, record in enumerate(payload["records"]):
        hierarchy = " ".join(str(v) for v in record["hierarchy"].values())
        title_tokens = tokens(hierarchy)
        content_tokens = tokens(record.get("content", ""))
        score = sum(5 for term in query_tokens if term in title_tokens)
        score += sum(2 for term in query_tokens if term in content_tokens)
        score += sum(1 for term in query_tokens if any(word.startswith(term) for word in content_tokens))
        if score:
            scored.append((score, -position, record))
    hits = [item[2] for item in sorted(scored, reverse=True)[:limit]]
    print(json.dumps({"results": [{"hits": hits}]}, ensure_ascii=False, indent=2))
    return 0


def fetch(url: str) -> int:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != BASE_HOST:
        print("URL is outside this mirror", file=sys.stderr)
        return 2
    path = parsed.path[:-3] if parsed.path.endswith(".md") else parsed.path
    prefix = "/docs/"
    if not path.startswith(prefix):
        print("URL is not a documentation page", file=sys.stderr)
        return 2
    slug = path[len(prefix):].strip("/")
    target = ROOT / "pages" / (slug.replace("/", "__") + ".md")
    if not target.is_file():
        print("Page is not in this snapshot", file=sys.stderr)
        return 3
    print(target.read_text(encoding="utf-8"), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("url")
    args = parser.parse_args()
    if args.command == "search":
        return search(args.query, max(1, min(args.limit, 50)))
    return fetch(args.url)


if __name__ == "__main__":
    raise SystemExit(main())
