"""HTTP adapter for the checkout quote library."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .pricing import QuoteError, calculate_quote


def quote_response(payload: Any) -> tuple[int, dict[str, Any]]:
    """Translate the library contract into the HTTP response contract."""
    try:
        return 200, {"quote": calculate_quote(payload)}
    except QuoteError as exc:
        return 400, {"error": {"code": "invalid_quote", "message": str(exc)}}


class QuoteHandler(BaseHTTPRequestHandler):
    """Minimal JSON request handler; deliberately quiet during tests."""

    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path != "/quote":
            self._send(404, {"error": {"code": "not_found", "message": "route not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": {"code": "invalid_quote", "message": "request body must be valid JSON"}})
            return
        status, body = quote_response(payload)
        self._send(status, body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), QuoteHandler)
