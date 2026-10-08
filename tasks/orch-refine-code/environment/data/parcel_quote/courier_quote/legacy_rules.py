"""Abandoned seasonal experiment; no production code imports this module."""

LEGACY_CITY_OVERRIDES = {
    "Northbridge": 1.25,
    "Lakehurst": 1.10,
    "Amberfield": 0.95,
}


def legacy_peak_multiplier(month: int, city: str) -> float:
    """Return a retired floating-point multiplier from a never-shipped pilot."""
    if month in (11, 12):
        return LEGACY_CITY_OVERRIDES.get(city, 1.15)
    return 1.0
