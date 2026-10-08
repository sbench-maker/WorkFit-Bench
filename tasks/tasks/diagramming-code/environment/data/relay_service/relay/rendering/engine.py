"""Prepare context before entering the template runtime."""

from relay.rendering.runtime import run_template


def render_template(template: str, context: dict[str, str]) -> str:
    safe_context = sanitize_context(context)
    return run_template(template, safe_context)


def sanitize_context(context: dict[str, str]) -> dict[str, str]:
    return {
        key: value.replace("<", "&lt;").replace(">", "&gt;")
        for key, value in context.items()
    }
