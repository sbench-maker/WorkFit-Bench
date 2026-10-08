"""Deterministic stand-in for an outbound queue."""

import hashlib


def enqueue_delivery(recipient: str, message: str) -> str:
    material = f"{recipient}:{message}".encode("utf-8")
    return "delivery_" + hashlib.sha256(material).hexdigest()[:12]
