"""Order quote calculation.

This module is intentionally behaviorally stable. The implementation reflects
several rushed additions and is the subject of the refactoring exercise.
"""

from __future__ import annotations

from .formatting import audit_event, normalized_coupon_code
from .validation import require_non_negative_integer, require_positive_integer


REGION_SHIPPING = {"local": 500, "national": 900, "international": 1800}
REGION_TAX_BPS = {"local": 825, "national": 650, "international": 0}


def calculate_order_quote(order: dict, audit_events: list[str] | None = None) -> dict:
    """Calculate the checkout quote and append stable audit events when requested."""
    a = audit_events
    if not isinstance(order, dict):
        raise TypeError("order must be a mapping")
    oid = order.get("order_id")
    if not isinstance(oid, str) or not oid.strip():
        raise ValueError("order_id is required")
    if a is not None:
        a.append(audit_event("start", oid))
    ls = order.get("lines")
    if not isinstance(ls, list) or len(ls) == 0:
        if a is not None:
            a.append(audit_event("rejected", "empty_order"))
        raise ValueError("order must contain at least one line")
    for x in ls:
        if not isinstance(x, dict):
            if a is not None:
                a.append(audit_event("rejected", "invalid_line"))
            raise ValueError("each line must be a mapping")
        s = x.get("sku")
        if not isinstance(s, str) or not s.strip():
            if a is not None:
                a.append(audit_event("rejected", "missing_sku"))
            raise ValueError("line sku is required")
        try:
            require_positive_integer(x.get("quantity"), f"line {s} has invalid quantity")
        except ValueError:
            if a is not None:
                a.append(audit_event("rejected", "invalid_quantity"))
            raise
        try:
            require_non_negative_integer(x.get("unit_price_cents"), f"line {s} has invalid unit price")
        except ValueError:
            if a is not None:
                a.append(audit_event("rejected", "invalid_unit_price"))
            raise
    c = order.get("customer", {})
    t = c.get("tier", "standard")
    if t not in ("standard", "silver", "gold"):
        if a is not None:
            a.append(audit_event("rejected", "unsupported_tier"))
        raise ValueError(f"unsupported customer tier: {t}")
    d = order.get("destination", {})
    r = d.get("region")
    if r not in REGION_SHIPPING:
        if a is not None:
            a.append(audit_event("rejected", "unsupported_region"))
        raise ValueError(f"unsupported destination region: {r}")
    try:
        credit = require_non_negative_integer(c.get("store_credit_cents", 0), "store credit must be a non-negative integer")
    except ValueError:
        if a is not None:
            a.append(audit_event("rejected", "invalid_credit"))
        raise
    if not isinstance(order.get("expedited", False), bool):
        if a is not None:
            a.append(audit_event("rejected", "invalid_expedited"))
        raise ValueError("expedited must be a boolean")
    if a is not None:
        a.append(audit_event("validated", len(ls)))

    # calculate subtotal
    total = 0
    for x in ls:
        total = total + x["unit_price_cents"] * x["quantity"]
    subtotal = total

    # calculate the tier discount
    tier_discount = 0
    if t == "silver":
        eligible = 0
        for x in ls:
            if x.get("category", "") != "gift_card":
                eligible = eligible + x["unit_price_cents"] * x["quantity"]
        tier_discount = eligible * 5 // 100
    else:
        if t == "gold":
            eligible = 0
            for x in ls:
                if x.get("category", "") != "gift_card":
                    eligible = eligible + x["unit_price_cents"] * x["quantity"]
            tier_discount = eligible * 10 // 100
        else:
            tier_discount = 0
    if tier_discount > 0:
        if a is not None:
            a.append(audit_event("tier_discount", tier_discount))

    coupon_discount = 0
    free_ship = False
    applied = []
    cp = order.get("coupon")
    if cp is not None:
        code = cp.get("code")
        if not isinstance(code, str) or not code.strip():
            if a is not None:
                a.append(audit_event("rejected", "invalid_coupon"))
            raise ValueError("coupon code is required")
        code = normalized_coupon_code(code)
        kind = cp.get("kind")
        if kind not in ("percent", "fixed", "free_shipping"):
            if a is not None:
                a.append(audit_event("rejected", "unsupported_coupon"))
            raise ValueError(f"unsupported coupon kind: {kind}")
        if cp.get("expires_on") is not None and cp.get("expires_on") < order.get("as_of", ""):
            if a is not None:
                a.append(audit_event("coupon_ignored", code, "expired"))
        else:
            minimum = cp.get("min_subtotal_cents", 0)
            if subtotal < minimum:
                if a is not None:
                    a.append(audit_event("coupon_ignored", code, "min_subtotal"))
            else:
                if kind == "percent":
                    v = require_non_negative_integer(cp.get("value"), "coupon value must be a non-negative integer")
                    coupon_discount = (subtotal - tier_discount) * v // 100
                    cap = cp.get("max_discount_cents")
                    if cap is not None:
                        coupon_discount = min(coupon_discount, cap)
                    coupon_discount = min(coupon_discount, subtotal - tier_discount)
                    applied.append(code)
                    if a is not None:
                        a.append(audit_event("coupon", code, coupon_discount))
                else:
                    if kind == "fixed":
                        v = require_non_negative_integer(cp.get("value"), "coupon value must be a non-negative integer")
                        coupon_discount = min(v, subtotal - tier_discount)
                        cap = cp.get("max_discount_cents")
                        if cap is not None:
                            coupon_discount = min(coupon_discount, cap)
                        applied.append(code)
                        if a is not None:
                            a.append(audit_event("coupon", code, coupon_discount))
                    else:
                        free_ship = True
                        applied.append(code)

    base_shipping = REGION_SHIPPING[r]
    if r != "international" and subtotal - tier_discount - coupon_discount >= 12000:
        base_shipping = 0
    shipping_waiver = 0
    if free_ship:
        shipping_waiver = base_shipping
        base_shipping = 0
        if a is not None:
            a.append(audit_event("coupon", applied[-1], shipping_waiver))
    shipping = base_shipping
    if d.get("remote", False):
        shipping = shipping + 400
    fragile = False
    for x in ls:
        if x.get("fragile", False):
            fragile = True
    if fragile:
        shipping = shipping + 250
    if order.get("expedited", False):
        shipping = shipping + 800
    if a is not None:
        a.append(audit_event("shipping", shipping))

    taxable_merchandise = 0
    for x in ls:
        if x.get("taxable", True):
            taxable_merchandise = taxable_merchandise + x["unit_price_cents"] * x["quantity"]
    merchandise_after_discount = subtotal - tier_discount - coupon_discount
    if merchandise_after_discount == 0:
        taxable_after_discount = 0
    else:
        taxable_after_discount = taxable_merchandise * merchandise_after_discount // subtotal
    if c.get("tax_exempt", False):
        tax = 0
    else:
        tax = (taxable_after_discount + shipping) * REGION_TAX_BPS[r] // 10000
    if a is not None:
        a.append(audit_event("tax", tax))

    before_credit = merchandise_after_discount + shipping + tax
    used_credit = min(credit, before_credit)
    if used_credit > 0:
        if a is not None:
            a.append(audit_event("credit", used_credit))
    final_total = before_credit - used_credit
    if a is not None:
        a.append(audit_event("complete", final_total))
    return {
        "currency": "USD",
        "subtotal_cents": subtotal,
        "discount_cents": tier_discount + coupon_discount,
        "shipping_cents": shipping,
        "tax_cents": tax,
        "credit_applied_cents": used_credit,
        "total_cents": final_total,
        "discount_codes": applied,
    }
