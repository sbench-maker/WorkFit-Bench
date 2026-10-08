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

Trace the column-level upstream and downstream flow for `bigquery:helios-analytics.prod_finance.fct_invoice_daily.net_revenue` from the frozen Data Lineage search exports in `/root/data/`. Produce `/root/results/lineage_summary.md` as a concise left-to-right Markdown walkthrough for the team triaging the 17 August null-rate spike. Name small sets of assets and processing jobs, state the search scope and limits, and flag incomplete or historical lineage without presenting it as a proven root cause.
