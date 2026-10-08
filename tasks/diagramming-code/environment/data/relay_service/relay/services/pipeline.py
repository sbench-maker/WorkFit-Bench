"""Shared delivery pipeline for live and replayed events."""

from relay.models import DeliveryEvent
from relay.rendering.engine import render_template
from relay.sending.queue import enqueue_delivery
from relay.templates.catalog import select_template
from typing import Optional


def process_event(
    event: DeliveryEvent,
    requested_by: Optional[str] = None,
) -> dict[str, object]:
    """Select an approved template, render it, then queue delivery."""
    template = select_template(event.kind)
    context = build_context(event, requested_by=requested_by)
    message = render_template(template, context)
    delivery_id = enqueue_delivery(event.recipient, message)
    return {
        "event_id": event.event_id,
        "delivery_id": delivery_id,
        "requested_by": requested_by,
    }


def build_context(
    event: DeliveryEvent,
    requested_by: Optional[str] = None,
) -> dict[str, str]:
    context = {
        "event_id": event.event_id,
        "recipient": event.recipient,
        **{str(key): str(value) for key, value in event.attributes.items()},
    }
    if requested_by:
        context["requested_by"] = requested_by
    return context
