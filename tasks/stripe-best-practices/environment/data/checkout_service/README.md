# Papertrail checkout service

This small Python package is the offline stand-in for Papertrail Stationery's
Stripe-backed one-time checkout service. It uses only the standard library and
the bundled `stripe_mock.py`; no network calls are made.

## Public interface to preserve

`checkout_service.service.build_service(environ, orders_path, stripe_client=None)`
returns a service with:

- `create_checkout(order_id) -> mapping`
- `handle_webhook(raw_body: bytes, signature_header: str) -> mapping`

The returned service exposes its configured `client` so the local harness can
inspect recorded mock calls. Callers may inject a compatible client. The
default client is `stripe_mock.FakeStripeClient`.

## Checkout behavior

Orders and line items come from `orders.jsonl`; catalog values are frozen into
each order. Only `pending` orders can start checkout. This is a one-time payment
flow and the current version supported by the mock is `2026-06-24.dahlia`.
Create Checkout Sessions, not Charges or raw PaymentIntents. Session line items
must preserve each item's name, unit amount, currency, and quantity, and must
reconcile to `total_minor`. Use the configured success and cancel URLs, carry
the `order_id` as both metadata and client reference, and omit
`payment_method_types` so Dashboard-configured dynamic methods remain eligible.

Every Checkout Session has an `integration_identifier` made from
`tracking_prefix`, a hyphen, and eight independently generated ASCII letters.
This lets operations compare flows without making all sessions share one tag.

## Configuration and webhook contract

`build_service` reads `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET` from the
provided environment mapping and fails closed if either is absent or blank.
Neither value belongs in source, fixture files, returned errors, or logs.

`stripe_mock.Webhook.construct_event` implements the local signing contract:
the header is `t=<unix-seconds>,v1=<hex-hmac>`, and the HMAC-SHA256 message is
`<timestamp>.<raw request bytes>`. It rejects malformed, stale (over 300
seconds), or mismatched signatures before returning parsed JSON.

After verification, `checkout.session.completed` is payable only when
`payment_status` is `paid`; `checkout.session.async_payment_succeeded` is also
payable. In both cases, the event's metadata `order_id`, `amount_total`, and
`currency` must agree with the stored order. Valid payment moves a pending
order to `paid`, recording the event ID and payment timestamp. Other event
types are acknowledged without changing orders. Existing terminal states do
not regress. Event IDs must be persisted next to the orders so delivery retries
remain idempotent after rebuilding the service.

The supplied implementation intentionally predates this contract. Keep the
fixture data and public interface, replace the implementation, and add a short
`HANDOFF.md` for the next engineer.
