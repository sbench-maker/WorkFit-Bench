# Frozen connector export guide

All entities in this directory are fictional. `connector_snapshot.json` fixes the reporting date, timezone, comparison windows, and availability of each connector. Calendar timestamps and Slack timestamps include their UTC offsets.

`quickbooks_summary.json` and `quickbooks_invoices.csv` are the finance snapshot. Only `open` invoices belong in outstanding receivables; days past due are measured on the reporting date. `payment_transactions.csv` combines PayPal and Square exports, and settlements include only `completed` transactions whose local transaction date is inside the stated window.

`hubspot_deals.csv` is the current deal snapshot. Weighted pipeline includes open stages only and uses `amount_usd * probability`; the `previous_week_*` columns are the frozen prior snapshot. `hubspot_deal_events.csv` records the associated stage history. `calendar_events.json` and `slack_messages.jsonl` are the commitment and internal-signal exports. Shared `customer_id` values join records across files. `owner_preferences.json` contains this owner's materiality and attention settings.
