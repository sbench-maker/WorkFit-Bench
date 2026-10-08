"""Sensitive, deliberately small template execution runtime."""

import re


TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def sensitive_sink(function):
    function.sensitive_boundary = True
    return function


@sensitive_sink
def run_template(template: str, context: dict[str, str]) -> str:
    """Evaluate supported placeholders; treat this as a security boundary."""
    tokens = compile_tokens(template)
    return evaluate_tokens(template, tokens, context)


def compile_tokens(template: str) -> list[str]:
    return TOKEN.findall(template)


def evaluate_tokens(
    template: str,
    tokens: list[str],
    context: dict[str, str],
) -> str:
    rendered = template
    for token in tokens:
        rendered = rendered.replace("{{" + token + "}}", context.get(token, ""))
        rendered = rendered.replace("{{ " + token + " }}", context.get(token, ""))
    return rendered
