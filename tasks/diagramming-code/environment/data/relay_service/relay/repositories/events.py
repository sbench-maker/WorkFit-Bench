"""Stored event access for replay."""

from relay.core.storage import read_record
from relay.models import DeliveryEvent


def load_event(event_id: str) -> DeliveryEvent:
    row = read_record("events", event_id)
    return DeliveryEvent(
        event_id=row["event_id"],
        kind=row["kind"],
        recipient=row["recipient"],
        attributes=row.get("attributes", {}),
    )
