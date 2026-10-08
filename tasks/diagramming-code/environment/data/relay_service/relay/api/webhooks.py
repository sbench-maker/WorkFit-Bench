"""Public webhook ingestion."""

from relay.framework import Request, public_route
from relay.parsing.requests import parse_json
from relay.security.signatures import verify_webhook
from relay.services.pipeline import process_event
from relay.validation.events import validate_event


@public_route("/hooks/events")
def receive_event(request: Request) -> dict[str, object]:
    """Accept one event after checking its transport signature."""
    payload = parse_json(request.body)
    verify_webhook(request.headers, request.body)
    event = validate_event(payload)
    return process_event(event)
