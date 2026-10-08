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

Our webhook-to-ledger workflow needs one JavaScript Code node to clean the exported order events and emit ledger-ready items. Inspect the fixture and contract under `/root/data/`, then save paste-ready node code as `/root/results/code.js`.

- I need retry deliveries collapsed by event ID, with the latest valid delivery winning and money handled exactly in cents.
- I need malformed or cancelled events quarantined without crashing the batch, while valid events are normalized to UTC and reconciled by currency.
- I need it to run once for all items and preserve source-item linkage for downstream nodes.
