"""Operator lookup for the admin route."""

from relay.core.storage import read_record


def find_operator(token: str) -> dict[str, str]:
    if not token:
        raise PermissionError("empty operator token")
    return read_record("operators", token)
