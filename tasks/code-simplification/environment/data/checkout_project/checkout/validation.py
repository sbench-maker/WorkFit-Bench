"""Validation helpers for checkout inputs."""


def require_non_negative_integer(value: object, message: str) -> int:
    """Return an integer value or raise the package's standard validation error."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(message)
    return value


def require_positive_integer(value: object, message: str) -> int:
    """Return a positive integer or raise the package's standard validation error."""
    value = require_non_negative_integer(value, message)
    if value == 0:
        raise ValueError(message)
    return value
