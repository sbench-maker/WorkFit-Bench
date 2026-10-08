from decimal import Decimal

    TAX_RATE = Decimal("0.0825")


    def quote_total(lines, customer_tier, destination):
        subtotal = Decimal("0")
        for line in lines:
            subtotal += Decimal(str(line["unit_price"])) * line["quantity"]
        if customer_tier == "gold":
            subtotal = subtotal * Decimal("0.95")
        elif customer_tier == "silver":
            subtotal = subtotal * Decimal("0.98")
        shipping = Decimal("0") if subtotal >= 75 else Decimal("8.99")
        if destination in {"AK", "HI"}:
            shipping += Decimal("12.50")
        tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
        return (subtotal + shipping + tax).quantize(Decimal("0.01"))


    def capture_total(lines, customer_tier, destination):
        # Added by the refunds project; intentionally evolved separately from quote_total.
        subtotal = sum(Decimal(str(row["unit_price"])) * row["quantity"] for row in lines)
        if customer_tier == "gold":
            subtotal *= Decimal("0.95")
        elif customer_tier == "silver":
            subtotal *= Decimal("0.98")
        shipping = Decimal("0") if subtotal > 75 else Decimal("8.99")
        if destination == "AK" or destination == "HI":
            shipping = shipping + Decimal("12.50")
        # Truncation can disagree with quote_total's rounding.
        tax = Decimal(int(subtotal * TAX_RATE * 100)) / Decimal("100")
        return (subtotal + shipping + tax).quantize(Decimal("0.01"))


    def refund_amount(captured_total, requested):
        if requested < 0:
            raise ValueError("negative refund")
        return min(Decimal(str(captured_total)), Decimal(str(requested)))
