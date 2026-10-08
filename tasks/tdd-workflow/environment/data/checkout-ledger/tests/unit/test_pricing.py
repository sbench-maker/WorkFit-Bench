from decimal import Decimal

import pytest

from checkout_quote import QuoteError, calculate_quote


def item(*, price="20.00", quantity=1, kind="merchandise", taxable=True, sku="SKU-1"):
    return {
        "sku": sku,
        "unit_price": price,
        "quantity": quantity,
        "kind": kind,
        "taxable": taxable,
    }


@pytest.mark.unit
def test_quotes_plain_taxable_merchandise():
    quote = calculate_quote({"items": [item()], "tax_rate": "0.0825"})
    assert quote == {"subtotal": "20.00", "discount": "0.00", "tax": "1.65", "total": "21.65"}


@pytest.mark.unit
def test_save10_discounts_merchandise_before_tax():
    quote = calculate_quote({"items": [item()], "promo_code": "SAVE10", "tax_rate": "0.0825"})
    assert quote == {"subtotal": "20.00", "discount": "2.00", "tax": "1.49", "total": "19.49"}


@pytest.mark.unit
def test_blank_promotion_means_no_promotion():
    quote = calculate_quote({"items": [item(taxable=False)], "promo_code": "  ", "tax_rate": "0.10"})
    assert quote["discount"] == "0.00"
    assert quote["tax"] == "0.00"


@pytest.mark.unit
@pytest.mark.parametrize("rate", ["-0.01", "0.2501", "NaN"])
def test_rejects_invalid_tax_rates(rate):
    with pytest.raises(QuoteError):
        calculate_quote({"items": [item()], "tax_rate": rate})


@pytest.mark.unit
def test_money_fields_are_decimal_safe_strings():
    quote = calculate_quote({"items": [item(price="0.10", quantity=3)], "tax_rate": "0.10"})
    assert all(isinstance(quote[field], str) and Decimal(quote[field]).as_tuple().exponent == -2 for field in quote)
