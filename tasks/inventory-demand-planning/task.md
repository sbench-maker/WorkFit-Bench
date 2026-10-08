---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 600.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
---

A supplier lead-time change has put our next DC replenishment cycle at risk.

Use the weekly demand, inventory, open-PO, vendor, and planning-policy files in `/root/data/` to create `/root/results/output.json` with a four-week forecast, recalculated safety stock, and executable replenishment recommendation for each SKU. Keep promo spikes and stockout-censored weeks out of baseline demand, account for lead-time variability and inventory position, respect case packs and MOQs, and flag pre-arrival stockout risks. Include a concise planner-review queue explaining the highest-priority actions.

Structure `output.json` with two top-level arrays: `sku_plans` and `planner_review_queue`. `sku_plans` must contain one record per SKU with `sku_id`, `weekly_forecast`, `forecast_4_week_units`, `safety_stock_units`, `inventory_position_units`, `recommended_order_quantity`, and `pre_arrival_stockout_risk`. Keep all measures for a SKU in that record. Use `planner_review_queue` for the prioritized exceptions and actions that need planner attention.
