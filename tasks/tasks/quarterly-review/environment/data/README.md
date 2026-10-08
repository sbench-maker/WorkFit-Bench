# Offline quarterly-review snapshot

All entities and records in this directory are fictional and locally constructed. Amounts are USD.

`financial_ledger.csv` uses positive amounts for revenue, COGS, and operating expenses. Gross profit is revenue minus COGS; operating income is gross profit minus operating expenses. Net margin in this simplified export is operating income divided by revenue because no interest or tax lines are present. Quarter comparisons should use the `quarter` field.

For customer concentration and revenue per customer, use Q2 revenue ledger lines joined by `customer_id`. A new customer win is a `new_business` deal at `closed_won` whose `close_date` falls in the reporting quarter. Churn is determined from `crm_customers.csv`. Pipeline entering Q3 is the gross amount of deals still open at quarter close whose `expected_close_date` is from 2026-07-01 through 2026-09-30; probability-weighted pipeline may also be shown.

PayPal validates only ledger revenue whose `payment_channel` is `PayPal`, not total company revenue. Reconcile Q2 by PayPal `transaction_date`, using gross sale activity plus refunds. Processing fees affect cash settlement but are not a reduction of booked revenue. Some Q1 transactions settled in Q2, and one Q2 transaction settled in July.

`export_manifest.json` records completeness and should be reflected wherever a limitation could change a decision.
