"""Request decoding helpers."""

import json
from typing import Any


def parse_json(raw_body: str) -> dict[str, Any]:
    value = json.loads(raw_body or "{}")
    if not isinstance(value, dict):
        raise ValueError("request body must be an object")
    return value
