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

Audit the fictional Breakwater AMM snapshot under `/root/data` before its deployment review. Write `/root/results/amm_security_review.json` with a ship/block decision, evidence-linked findings, severity, exploit impact, and practical remediations.

- I’m worried donation and token-transfer behavior could break vault share accounting or withdrawals.
- Swaps and oracle updates must resist stale execution, adverse slippage, and one-block price manipulation.
- I need every listed state-changing entrypoint covered, with verified controls separated from release blockers.
