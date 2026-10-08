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

An Australian client wants to buy exactly 0.018 BTC with AUD and has AUD 450 in their Binance fiat wallet. Use the frozen fiat API request/response snapshots under `/root/data/` to confirm support, compare current payment routes against their limits and quotations, and handle any wallet funding shortfall with the available deposit methods. Write an execution-ready recommendation to `/root/results/output.json`, including the market reference, a viable fallback, and the relevant regional action links; keep all prices clearly indicative.

Treat `client_request.json` as the client constraint and `mock_api_snapshots.jsonl` as the available route, quote, limit, and link evidence at the frozen evaluation time. Distinguish the recommended route, wallet shortfall/funding step, and fallback route in the JSON, and retain the source route or quote identifiers. Do not imply that a deposit or purchase was actually executed.
