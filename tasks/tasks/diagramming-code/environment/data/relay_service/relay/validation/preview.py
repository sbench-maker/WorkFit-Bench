"""Constrain values passed into preview rendering."""

from typing import Any


def preview_context(payload: dict[str, Any]) -> dict[str, str]:
    raw_context = payload.get("context") or {}
    if not isinstance(raw_context, dict):
        raise ValueError("preview context must be an object")
    return {
        str(key)[:40]: str(value)[:200]
        for key, value in raw_context.items()
        if not str(key).startswith("_")
    }
