# 2027 electricity RFP fixture

All entities and measurements in this package are fictional and were constructed for this procurement exercise.

- `facilities.csv` identifies the sites and their market. `planning_base_kw` is descriptive only; calculate the requested profile from interval data.
- `interval_load.csv` contains one representative weekday and weekend profile per month at 15-minute resolution. Each interval represents the number of calendar days in `represented_days`; `pricing_period` is the settlement bucket to use.
- `network_tariffs.csv` supplies site-level non-bypassable and demand-based charges.
- `market_prices.csv` gives the three frozen index-price scenarios by market, month, and pricing period.
- `suppliers.csv`, `supplier_bids.csv`, and `contract_exceptions.csv` are the RFP response package. Empty numeric bid cells are missing terms, not zeroes.
- `procurement_policy.json` is the approved screening, costing, award, and review policy. An exception only blocks eligibility when its status is `open` and its clause code is prohibited by that policy.

For an award split, a market scenario total is the share-weighted average of the awarded offers' market total-delivered costs; each offer's total already contains the same market network cost. Portfolio totals are the sum of the two market totals. Budget variance is scenario cost minus the approved budget.
