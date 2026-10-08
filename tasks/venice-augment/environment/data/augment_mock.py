#!/usr/bin/env python3
"""Offline HTTP mock for the frozen augmentation search and scrape objects."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlparse


DATA_DIR = Path(__file__).resolve().parent
SNAPSHOT = json.loads((DATA_DIR / "web_snapshot.json").read_text(encoding="utf-8"))
DOCUMENTS = SNAPSHOT["documents"]
BY_URL = {row["url"]: row for row in DOCUMENTS}


def tokens(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9.:-]+", value.lower()) if len(term) > 1}


def perform_search(payload: dict) -> tuple[int, dict]:
    query = payload.get("query")
    limit = payload.get("limit", 10)
    provider = payload.get("search_provider", "brave")
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 400:
        return 400, {"error": {"code": "INVALID_REQUEST", "message": "query must contain 1-400 characters"}}
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        return 400, {"error": {"code": "INVALID_REQUEST", "message": "limit must be 1-20"}}
    if provider not in {"brave", "google"}:
        return 400, {"error": {"code": "INVALID_REQUEST", "message": "search_provider must be brave or google"}}

    query_terms = tokens(query)
    ranked = []
    for position, row in enumerate(DOCUMENTS):
        haystack = " ".join(
            [row["title"], row["snippet"], row.get("authority", ""), " ".join(row.get("search_terms", []))]
        )
        hay_terms = tokens(haystack)
        overlap = len(query_terms & hay_terms)
        phrase_bonus = sum(2 for phrase in row.get("search_terms", []) if phrase.lower() in query.lower())
        score = overlap * 10 + phrase_bonus
        if score:
            date_bias = row["date"] if provider == "google" else ""
            ranked.append((score, date_bias, -position, row))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    results = [
        {"title": row["title"], "url": row["url"], "content": row["snippet"], "date": row["date"]}
        for _, _, _, row in ranked[:limit]
    ]
    return 200, {"query": query, "results": results}


def perform_scrape(payload: dict) -> tuple[int, dict]:
    url = payload.get("url")
    if not isinstance(url, str) or not url:
        return 400, {"error": {"code": "INVALID_REQUEST", "message": "url is required"}}
    row = BY_URL.get(url)
    if row is None:
        return 500, {"error": {"code": "UPSTREAM_FAILURE", "message": "URL is absent from the frozen snapshot"}}
    if row["retrieval_state"] == "blocked":
        return 400, {"error": {"code": "BLOCKED_SOURCE", "message": "Automated access to this social source is blocked"}}
    return 200, {"url": url, "content": row["content"], "format": "markdown"}


class Handler(BaseHTTPRequestHandler):
    server_version = "OrchidAugmentMock/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "documents": len(DOCUMENTS)})
        else:
            self.send_json(404, {"error": {"code": "NOT_FOUND", "message": "Unknown route"}})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self.send_json(400, {"error": {"code": "INVALID_REQUEST", "message": "Body must be JSON"}})
            return
        route = urlparse(self.path).path
        if route == "/api/v1/augment/search":
            self.search(payload)
        elif route == "/api/v1/augment/scrape":
            self.scrape(payload)
        else:
            self.send_json(404, {"error": {"code": "NOT_FOUND", "message": "Unknown route"}})

    def search(self, payload: dict) -> None:
        status, response = perform_search(payload)
        self.send_json(status, response)

    def scrape(self, payload: dict) -> None:
        status, response = perform_scrape(payload)
        self.send_json(status, response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--call", choices=("search", "scrape"))
    parser.add_argument("--payload-json")
    args = parser.parse_args()
    if args.call:
        if not args.payload_json:
            parser.error("--payload-json is required with --call")
        payload = json.loads(args.payload_json)
        status, response = perform_search(payload) if args.call == "search" else perform_scrape(payload)
        print(json.dumps({"status": status, "response": response}, ensure_ascii=False))
        return
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
