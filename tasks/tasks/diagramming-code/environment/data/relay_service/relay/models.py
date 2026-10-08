"""Shared domain records."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeliveryEvent:
    event_id: str
    kind: str
    recipient: str
    attributes: dict[str, object] = field(default_factory=dict)
