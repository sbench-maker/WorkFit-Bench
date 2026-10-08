from decimal import Decimal
    from app.checkout import quote_total


    def test_basic_quote():
        lines = [{"sku": "BOX", "unit_price": "10.00", "quantity": 2}]
        assert quote_total(lines, "standard", "CA") == Decimal("30.64")
