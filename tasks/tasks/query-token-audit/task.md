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

Screen the pending swaps in `/root/data/` using the frozen token-audit responses and produce `/root/results/output.json`. For each queued request, give the reviewer an actionable pre-trade disposition, show the risk level and tax assessment when the audit is usable, and include every detected contract, trading, or scam flag with its evidence. Do not surface unreliable risk details for unavailable or unsupported audits, call any token “safe,” or drift into investment advice. Add a compact summary for queue triage.

Use `review_policy.json` for audit-usability states, disposition precedence, and what may be shown when a provider response is unavailable or unsupported. Retain the request and audit identifiers on each review so a lower-risk result cannot be mistaken for a general safety guarantee or attached to the wrong swap.
