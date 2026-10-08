---
schema_version: "1.3"
verifier:
  type: test-script
  timeout_sec: 900.0
agent:
  timeout_sec: 900.0
environment:
  network_mode: no-network
  build_timeout_sec: 900.0
  os: linux
  cpus: 1
  memory_mb: 4096
  storage_mb: 10240
---

The treasury team needs the August trade blotter ready for cash reconciliation.

Update `/root/data/trade_settlement_input.xlsx` and save `/root/results/trade_settlement_final.xlsx`. Preserve the existing sheets and source fields. On `Trades`, add formula-driven local gross, broker fee in USD, and signed USD cash impact using the reference sheets; cancelled trades must have zero cash impact, while missing rates must stay visibly unresolved rather than becoming zero. Complete `Summary` by desk and currency with trade count, fees, cash impact, and a grand total. Keep the workbook editable and easy to review in Excel.
