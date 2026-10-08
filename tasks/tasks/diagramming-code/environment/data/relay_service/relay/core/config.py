"""Static configuration for the offline fixture."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str
    signature_key: str
    admin_roles: frozenset[str]


def load_settings() -> Settings:
    return Settings(
        service_name="lumen-relay",
        signature_key="<REDACTED>",
        admin_roles=frozenset({"delivery-admin"}),
    )
