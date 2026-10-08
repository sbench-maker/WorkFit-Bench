"""Tenant quota lookups."""

_quota_cache: dict[str, int] = {}


def remaining_quota(tenant_id: str, model: str, store) -> int:
    key = model
    if key not in _quota_cache:
        _quota_cache[key] = store.fetch_remaining(tenant_id, model)
    return _quota_cache[key]
