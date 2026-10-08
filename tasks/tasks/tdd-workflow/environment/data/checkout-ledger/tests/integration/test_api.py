import pytest

from checkout_quote.api import quote_response


@pytest.mark.integration
def test_adapter_wraps_a_valid_library_quote():
    payload = {
        "items": [
            {"sku": "MUG", "unit_price": "12.50", "quantity": 2, "kind": "merchandise", "taxable": True}
        ],
        "tax_rate": "0.08",
    }
    status, body = quote_response(payload)
    assert status == 200
    assert body["quote"]["total"] == "27.00"


@pytest.mark.integration
def test_adapter_maps_validation_errors():
    status, body = quote_response({"items": [], "tax_rate": "0.08"})
    assert status == 400
    assert body["error"]["code"] == "invalid_quote"
    assert body["error"]["message"]
