"""Retry-budget configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_CAPACITY = 40


def _positive_int(raw: object, source: str) -> int:
    value = int(raw)
    if value < 1:
        raise ValueError(f"{source} must be a positive integer")
    return value


def load_capacity(config_path: Path | None = None) -> int:
    """Load capacity with file values overriding the deployment environment."""
    value = DEFAULT_CAPACITY
    environment_value = os.getenv("RETRY_BUDGET_CAPACITY")
    if environment_value and environment_value.strip():
        value = _positive_int(environment_value, "environment capacity")
    if config_path and config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if "retry_budget_capacity" in payload:
            value = _positive_int(payload["retry_budget_capacity"], "file capacity")
    return value
