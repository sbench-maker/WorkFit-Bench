"""Operator authentication."""

from relay.core.config import load_settings
from relay.repositories.operators import find_operator


def require_admin(headers: dict[str, str]) -> str:
    token = parse_bearer(headers.get("authorization", ""))
    operator = find_operator(token)
    ensure_admin_role(operator)
    return operator["operator_id"]


def parse_bearer(value: str) -> str:
    prefix = "Bearer "
    if not value.startswith(prefix):
        raise PermissionError("missing bearer token")
    return value[len(prefix) :]


def ensure_admin_role(operator: dict[str, str]) -> None:
    settings = load_settings()
    if operator.get("role") not in settings.admin_roles:
        raise PermissionError("operator lacks replay permission")
