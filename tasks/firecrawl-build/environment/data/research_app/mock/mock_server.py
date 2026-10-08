#!/usr/bin/env python3
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading


def build_handler(index: dict, log_path: Path | None):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def reply(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            auth = self.headers.get("Authorization", "")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(size))
            except (ValueError, json.JSONDecodeError):
                self.reply(400, {"success": False, "error": "invalid JSON"})
                return
            event = {"path": self.path, "authorization": auth, "body": payload}
            if log_path:
                with lock:
                    with log_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(event) + "\n")
            if not auth.startswith("Bearer ") or not auth[7:]:
                self.reply(401, {"success": False, "error": "unauthorized"})
                return
            if self.path == "/v1/search":
                if payload.get("limit") != 5:
                    self.reply(400, {"success": False, "error": "limit must be 5"})
                    return
                query = str(payload.get("query", "")).strip().casefold()
                matches = index["queries"].get(query, index["queries"]["default"])
                self.reply(200, {"success": True, "data": matches})
                return
            if self.path == "/v1/scrape":
                url = payload.get("url")
                if payload.get("formats") != ["markdown"]:
                    self.reply(400, {"success": False, "error": "markdown format required"})
                    return
                page = index["pages"].get(url)
                if page is None:
                    self.reply(404, {"success": False, "error": "page not found"})
                elif page.get("failure"):
                    self.reply(422, {"success": False, "error": page["failure"]})
                else:
                    self.reply(200, {"success": True, "data": {"markdown": page["markdown"], "metadata": {"title": page["title"], "sourceURL": url}}})
                return
            self.reply(404, {"success": False, "error": "unknown endpoint"})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    raw_log = os.environ.get("MOCK_LOG_PATH")
    log_path = Path(raw_log) if raw_log else None
    if log_path:
        log_path.write_text("", encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), build_handler(index, log_path))
    print(server.server_address[1], flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
