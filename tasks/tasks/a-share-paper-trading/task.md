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

The trading desk has placed today's 10:05 A-share paper-trading work order in `/root/data/`. Execute its ten instructions in order for the specified account. First reconcile cash, positions, and open orders; then process cancellations, new orders, and fills. Enforce A-share board-lot sizes, T+1 sellability, price limits, tick sizes, quote freshness, and available-funds constraints. Record a clear reason for every instruction that cannot be executed. Write the final account and positions, the orders and trade receipts from this work order, and each instruction's outcome to `/root/results/output.json` for the trading supervisor to review.
