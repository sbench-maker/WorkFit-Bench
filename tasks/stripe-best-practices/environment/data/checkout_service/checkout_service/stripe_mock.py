"""Offline Stripe-shaped mock used by the exercise."""

from __future__ import annotations

import hashlib
import hmac
import json
import time


CURRENT_API_VERSION = "2026-06-24.dahlia"


class _CreateResource:
    def __init__(self, kind: str, owner: "FakeStripeClient"):
        self.kind = kind
        self.owner = owner

    def create(self, **params):
        self.owner.calls.append({"resource": self.kind, "params": params})
        prefix = "cs_mock" if self.kind == "checkout.sessions" else "ch_mock"
        return {"id": f"{prefix}_{len(self.owner.calls):06d}", **params}


class _Checkout:
    def __init__(self, owner: "FakeStripeClient"):
        self.sessions = _CreateResource("checkout.sessions", owner)


class FakeStripeClient:
    def __init__(self, api_key: str, api_version: str):
        self.api_key = api_key
        self.api_version = api_version
        self.calls = []
        self.checkout = _Checkout(self)
        self.charges = _CreateResource("charges", self)
        self.payment_intents = _CreateResource("payment_intents", self)


class Webhook:
    @staticmethod
    def construct_event(raw_body: bytes, signature_header: str, secret: str, *, now=None):
        if not isinstance(raw_body, bytes):
            raise ValueError("raw webhook body must be bytes")
        try:
            parts = dict(part.split("=", 1) for part in signature_header.split(","))
            timestamp = int(parts["t"])
            supplied = parts["v1"]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid webhook signature header") from exc
        current = int(time.time() if now is None else now)
        if abs(current - timestamp) > 300:
            raise ValueError("webhook signature timestamp outside tolerance")
        message = str(timestamp).encode("ascii") + b"." + raw_body
        expected = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("webhook signature mismatch")
        event = json.loads(raw_body.decode("utf-8"))
        if not isinstance(event, dict):
            raise ValueError("webhook event must be an object")
        return event


def make_signature_header(raw_body: bytes, secret: str, *, timestamp: int) -> str:
    message = str(timestamp).encode("ascii") + b"." + raw_body
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"
