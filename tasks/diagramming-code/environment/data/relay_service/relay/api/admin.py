"""Authenticated operator actions."""

from relay.framework import Request, admin_route
from relay.repositories.events import load_event
from relay.security.auth import require_admin
from relay.services.pipeline import process_event


@admin_route("/admin/replay")
def replay_event(request: Request) -> dict[str, object]:
    """Replay a previously stored event after an operator check."""
    operator = require_admin(request.headers)
    event_id = request.params.get("event_id", "")
    event = load_event(event_id)
    return process_event(event, requested_by=operator)
