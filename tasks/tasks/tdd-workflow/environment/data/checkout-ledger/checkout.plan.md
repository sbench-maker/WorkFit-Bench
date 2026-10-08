# Checkout quote correction plan

## Context

Support reproduced a pricing defect when a `SAVE10` cart contains both ordinary merchandise and a stored-value gift card. Gift cards are tender-like products: they contribute to the amount due but are never taxable and never promotion-eligible.

## User journeys

1. As a shopper, I want `SAVE10` to reduce eligible merchandise only, so that buying a gift card does not create an unintended discount.
2. As an API client, I want `POST /quote` to return the same quote as the Python library for the same payload, so that channel choice never changes the amount due.
3. As an API client, I want invalid quote requests rejected predictably, so that checkout can show a useful error instead of using a partial total.

## Approved behavior

- Supported item kinds are `merchandise` and `gift_card`.
- A merchandise line may be taxable or non-taxable. A gift-card line must be non-taxable.
- `SAVE10` applies 10% to each merchandise line and never to a gift-card line. Round each line discount to cents with decimal half-up rounding, then sum the rounded discounts.
- For each taxable line, compute tax on its post-discount line amount and round that line's tax to cents with decimal half-up rounding. Sum the rounded line taxes.
- `subtotal`, `discount`, `tax`, and `total` are two-decimal strings, and `total = subtotal - discount + tax`.
- No promotion is represented by an absent, null, or blank `promo_code`. Any other code is invalid.
- A request needs at least one item. `quantity` must be an integer from 1 through 99; `unit_price` must be a positive amount with no more than two decimal places; and `tax_rate` must be between 0 and 0.25 inclusive.
- The library raises `QuoteError` for validation failures. The HTTP adapter returns status 400 with `{"error": {"code": "invalid_quote", "message": "..."}}`; valid requests return status 200 with `{"quote": ...}`.
- `POST /quote` is the only supported route. Malformed JSON is a validation failure; unknown routes return 404.

## Validation intent

Exercise ordinary merchandise, mixed merchandise/gift-card carts, per-line half-cent rounding, blank promotions, and representative validation failures. Preserve focused unit, adapter-level integration, and live local HTTP tests; no network service is required.

Run the project-declared test and coverage commands only. Do not add runtime dependencies or broaden the public API.
