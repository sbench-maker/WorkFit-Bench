"""Decimal checkout pricing used by every delivery channel."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


CENT = Decimal("0.01")
MAX_TAX_RATE = Decimal("0.25")


class QuoteError(ValueError):
    """Raised when a quote payload violates the public contract."""


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise QuoteError(f"{field} must be a decimal number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise QuoteError(f"{field} must be a decimal number") from None
    if not number.is_finite():
        raise QuoteError(f"{field} must be finite")
    return number


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validated_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise QuoteError("items must be a non-empty list")

    validated: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise QuoteError(f"items[{index}] must be an object")
        sku = item.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            raise QuoteError(f"items[{index}].sku is required")
        kind = item.get("kind")
        if kind not in {"merchandise", "gift_card"}:
            raise QuoteError(f"items[{index}].kind is unsupported")
        quantity = item.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 99:
            raise QuoteError(f"items[{index}].quantity must be an integer from 1 to 99")
        price = _decimal(item.get("unit_price"), f"items[{index}].unit_price")
        if price <= 0 or price.as_tuple().exponent < -2:
            raise QuoteError(f"items[{index}].unit_price must be positive with at most two decimals")
        taxable = item.get("taxable")
        if not isinstance(taxable, bool):
            raise QuoteError(f"items[{index}].taxable must be boolean")
        if kind == "gift_card" and taxable:
            raise QuoteError(f"items[{index}] gift cards cannot be taxable")
        validated.append(
            {
                "sku": sku.strip(),
                "kind": kind,
                "quantity": quantity,
                "unit_price": price,
                "taxable": taxable,
            }
        )
    return validated


def calculate_quote(payload: dict[str, Any]) -> dict[str, str]:
    """Validate a payload and return its money totals as two-decimal strings.

    The current implementation contains the reported promotion defect: SAVE10 is
    calculated from every line, including stored-value gift cards.
    """
    if not isinstance(payload, dict):
        raise QuoteError("quote payload must be an object")
    items = _validated_items(payload)

    promo = payload.get("promo_code")
    if isinstance(promo, str):
        promo = promo.strip()
    if promo in {None, ""}:
        promo = None
    if promo not in {None, "SAVE10"}:
        raise QuoteError("promo_code is unsupported")

    tax_rate = _decimal(payload.get("tax_rate", "0"), "tax_rate")
    if not Decimal("0") <= tax_rate <= MAX_TAX_RATE:
        raise QuoteError("tax_rate must be between 0 and 0.25")

    subtotal = Decimal("0")
    discount = Decimal("0")
    tax = Decimal("0")
    for item in items:
        line_subtotal = _money(item["unit_price"] * item["quantity"])
        # BUG: stored-value gift cards are included in SAVE10.
        line_discount = _money(line_subtotal * Decimal("0.10")) if promo == "SAVE10" else Decimal("0")
        line_tax = _money((line_subtotal - line_discount) * tax_rate) if item["taxable"] else Decimal("0")
        subtotal += line_subtotal
        discount += line_discount
        tax += line_tax

    total = subtotal - discount + tax
    return {
        "subtotal": f"{_money(subtotal):.2f}",
        "discount": f"{_money(discount):.2f}",
        "tax": f"{_money(tax):.2f}",
        "total": f"{_money(total):.2f}",
    }
