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

The pricing module in `/root/data/checkout_project` works, but `calculate_order_quote` has become difficult to review after several rushed changes. Refactor only `checkout/pricing.py` for clarity and consistency with the neighboring modules while preserving every observable behavior, including exception details and audit-event ordering. Do not modify or weaken the supplied tests. Put the revised module at `/root/results/pricing.py` and add a short `/root/results/refactor_notes.md` describing the main simplifications and regression checks performed.
