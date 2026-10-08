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

Our FinOps budget review is tomorrow; the Azure Cost Management exports are frozen as of August 20.

Using `/root/data/`, create `/root/results/output.json` with the latest complete month’s portfolio and service cost breakdown plus an August–November subscription outlook against monthly budgets. Keep Actual and Forecast amounts separate so partial-month spend is not double-counted, mark unavailable forecasts instead of inventing values, and surface the priority budget risks with evidence for follow-up.
