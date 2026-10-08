"""Public template preview endpoint."""

from relay.framework import Request, public_route
from relay.parsing.requests import parse_json
from relay.rendering.engine import render_template
from relay.validation.preview import preview_context


@public_route("/templates/preview")
def preview_template(request: Request) -> str:
    """Render a caller-provided template for the preview UI."""
    payload = parse_json(request.body)
    context = preview_context(payload)
    template = str(payload.get("template", ""))
    return render_template(template, context)
