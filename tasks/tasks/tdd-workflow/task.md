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

Take the failing checkout quote service in `/root/data/checkout-ledger` and implement the correction described in `checkout.plan.md`: `SAVE10` must not discount non-taxable gift cards, and the HTTP quote must match the library result. Work test-first, cover pricing and validation at unit, integration, and end-to-end levels, and keep line coverage at 80% or higher. Deliver the completed Git repository to `/root/results/checkout-ledger`, preserving separate RED and GREEN checkpoints and adding a concise evidence report at `docs/testing/checkout.tdd.md`.
