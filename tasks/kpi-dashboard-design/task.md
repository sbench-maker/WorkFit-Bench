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

Build a self-contained executive SaaS KPI dashboard from `/root/data/` and save it as `/root/results/saas_kpi_dashboard.html`. Show the current month with historical context and drilldowns that explain changes in MRR, churn, and LTV/CAC, and surface only actionable target breaches. Make the calculation definitions visible because Finance and Growth currently disagree about annual plans and cancellations. The dashboard must work offline in a browser.

The initial view must be present after normal offline browser rendering, not only described in JavaScript source. Also embed the final KPI, trend, alert, and drilldown view model as valid JSON in a `<script type="application/json">` element so every displayed value can be associated with its metric and period during review.
