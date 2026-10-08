"""Metric names for retry-budget saturation."""

RETRY_ALLOWED = "retry_budget.allowed"
RETRY_DENIED = "retry_budget.denied"
RETRY_SATURATION = "retry_budget.saturation_ratio"


def saturation_ratio(active_retries: int, capacity: int) -> float:
    if capacity < 1:
        raise ValueError("capacity must be positive")
    return min(1.0, max(0.0, active_retries / capacity))

