"""Small formatting helpers shared by checkout modules."""


def audit_event(name: str, *values: object) -> str:
    """Return the stable colon-delimited audit representation."""
    return ":".join([name, *(str(value) for value in values)])


def normalized_coupon_code(code: str) -> str:
    """Normalize coupon codes for output and audit records."""
    return code.strip().upper()
