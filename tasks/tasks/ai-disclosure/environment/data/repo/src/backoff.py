"""Backoff helpers that existed before AI tracking was enabled."""

from __future__ import annotations


def retry_delay(attempt: int, base_seconds: float = 0.25) -> float:
    """Return capped exponential backoff for a zero-based retry attempt."""
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    return min(base_seconds * (2**attempt), 8.0)

