"""Webhook signature checks."""

import hashlib
import hmac

from relay.core.config import load_settings


def verify_webhook(headers: dict[str, str], raw_body: str) -> None:
    supplied = headers.get("x-lumen-signature", "")
    expected = canonical_signature(raw_body)
    if not hmac.compare_digest(supplied, expected):
        raise PermissionError("invalid webhook signature")


def canonical_signature(raw_body: str) -> str:
    settings = load_settings()
    material = f"{settings.signature_key}:{raw_body}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()
