# Webhook order-event transform contract

The input to the Code node is the array in `webhook_items.json`. Each array element is one n8n item. The webhook envelope is under `item.json`; the business payload is under `item.json.body`.

The node runs in **Run Once for All Items** mode. It must return n8n items and may return them in any order. Every returned detail item must include `pairedItem: { item: <zero-based input index> }` pointing to the delivery that produced that detail. The aggregate summary has no source-item link.

## Input payload

A structurally valid delivery has:

- `json.received_at`: an ISO-8601 timestamp with `Z` or a numeric UTC offset.
- `json.body.event_id`, `order_id`, and `customer.id`: non-empty strings after trimming.
- `json.body.event_type`: `paid`, `refunded`, or `cancelled`, ignoring surrounding whitespace and case.
- `json.body.occurred_at`: an ISO-8601 timestamp with `Z` or a numeric UTC offset.
- `json.body.currency`: `USD`, `EUR`, or `GBP`, ignoring surrounding whitespace and case.
- `json.body.amounts`: `subtotal`, `tax`, `shipping`, and `discount`. Each is a finite non-negative number or a trimmed decimal string with at most two fractional digits. The total `subtotal + tax + shipping - discount` must be greater than zero.

Identifiers are trimmed in output. Currency and event type are normalized to upper- and lower-case respectively. Timestamps without an explicit timezone are invalid.

## Validation and retry handling

Validate every physical delivery first. A malformed delivery becomes its own quarantine detail and does not participate in retry selection. Include every applicable reason from this list:

- `INVALID_ENVELOPE`: missing/non-object `json`, missing/non-object `body`, or invalid `received_at`.
- `MISSING_EVENT_ID`, `MISSING_ORDER_ID`, `MISSING_CUSTOMER_ID`.
- `UNSUPPORTED_EVENT_TYPE`, `INVALID_TIMESTAMP`, `UNSUPPORTED_CURRENCY`, `INVALID_AMOUNT`.

Among structurally valid deliveries, group by the trimmed `event_id`. Keep the one with the latest `received_at`; if timestamps tie, keep the higher input index. Count every other valid delivery as a retry and emit no detail for it. A selected `cancelled` event becomes a quarantine detail with the sole reason `CANCELLED`.

## Returned item shapes

For each selected `paid` or `refunded` event, emit:

```json
{
  "json": {
    "recordType": "ledger",
    "eventId": "EVT-0001",
    "orderId": "ORD-10001",
    "eventType": "paid",
    "occurredAtUtc": "2026-06-01T00:37:00.000Z",
    "currency": "USD",
    "signedAmountCents": 2450,
    "customerId": "CUST-002"
  },
  "pairedItem": {"item": 0}
}
```

`signedAmountCents` is the exact total in cents, positive for `paid` and negative for `refunded`.

For an invalid physical delivery or a selected cancellation, emit:

```json
{
  "json": {
    "recordType": "quarantine",
    "eventId": "EVT-0002",
    "orderId": "ORD-10002",
    "inputIndex": 7,
    "reasons": ["INVALID_AMOUNT"]
  },
  "pairedItem": {"item": 7}
}
```

Use trimmed string IDs when available; otherwise use `null`. Reason ordering is not significant.

Return exactly one summary item, including for empty input:

```json
{
  "json": {
    "recordType": "summary",
    "inputCount": 0,
    "canonicalEventCount": 0,
    "duplicateRetries": 0,
    "ledgerCount": 0,
    "quarantineCount": 0,
    "netByCurrencyCents": {"USD": 0, "EUR": 0, "GBP": 0}
  }
}
```

Summary counts must reconcile to the emitted details. Currency totals include ledger details only.
