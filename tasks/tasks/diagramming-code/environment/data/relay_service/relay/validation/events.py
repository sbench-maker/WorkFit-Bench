"""Validation for signed delivery events."""

from typing import Any

from relay.models import DeliveryEvent


ALLOWED_KINDS = {"invoice.ready", "shipment.delayed", "account.welcome"}


def validate_event(payload: dict[str, Any]) -> DeliveryEvent:
    normalized = normalize_fields(payload)
    enforce_event_type(normalized["kind"])
    return DeliveryEvent(
        event_id=normalized["event_id"],
        kind=normalized["kind"],
        recipient=normalized["recipient"],
        attributes=normalized["attributes"],
    )


def normalize_fields(payload: dict[str, Any]) -> dict[str, Any]:
    event_id = str(payload.get("event_id", "")).strip()
    kind = str(payload.get("kind", "")).strip().lower()
    recipient = str(payload.get("recipient", "")).strip()
    attributes = payload.get("attributes") or {}
    if not event_id or not recipient or not isinstance(attributes, dict):
        raise ValueError("event identity, recipient, and attributes are required")
    return {
        "event_id": event_id,
        "kind": kind,
        "recipient": recipient,
        "attributes": attributes,
    }


def enforce_event_type(kind: str) -> None:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unsupported event kind: {kind}")
