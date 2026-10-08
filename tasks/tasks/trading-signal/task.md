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

Use the frozen smart-money snapshot, open positions, and desk policy in `/root/data/` to prepare today’s copy-trade decision queue. Save `/root/results/output.json` with ranked buy opportunities and ranked sell alerts for held tokens, including trigger/current price, current return, max gain, exit rate, wallet conviction, and a brief evidence-based rationale for each. Keep stale or high-exit buys out of the actionable queue, and surface incomplete qualifying signals instead of guessing missing values.

Treat `desk_policy.json` as authoritative for eligibility, freshness, ranking, top-N, required fields, and percentage units. Keep buy opportunities, sell alerts, and incomplete qualifying signals as distinguishable collections. Preserve each signal's source ID; beyond those requirements, the JSON structure and key names may vary.

Structure `output.json` with the top-level arrays `buy_opportunities`, `sell_alerts`, and `incomplete_signals`. Every actionable entry must carry its source `signal_id` and the requested price, return, gain, exit-rate, and conviction fields. Every incomplete entry must list `missing_fields`; it must not also appear in either actionable array.
