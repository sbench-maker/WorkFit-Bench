"""Application assembly and route registration."""

from relay.api.admin import replay_event
from relay.api.health import health_check
from relay.api.preview import preview_template
from relay.api.webhooks import receive_event
from relay.core.config import load_settings
from relay.framework import Router


def build_app() -> Router:
    """Construct the small HTTP application used by the review fixture."""
    settings = load_settings()
    router = Router(service_name=settings.service_name)
    router.bind(receive_event)
    router.bind(preview_template)
    router.bind(replay_event)
    router.bind(health_check)
    return router
