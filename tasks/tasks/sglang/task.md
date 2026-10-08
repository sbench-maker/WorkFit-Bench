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

Build a reusable local LLM support-ticket router from the policy, tickets, runtime contract, and output contract in `/root/data/`. Use schema-constrained generation for each decision and batch the requests so the shared policy prefix is reused before the unique ticket content. Save the runnable implementation to `/root/results/router.py` and its primary batch result to `/root/results/output.json`; keep precedence-sensitive escalations intact, report observed batch/cache metrics, and make each route audit-friendly without echoing full ticket text.

Treat `routing_policy.json` as authoritative when signals overlap: apply its precedence before any model-generated explanation. The runtime and output contracts define the callable interface and result shape; do not substitute estimated cache metrics for values observed from the bundled runtime.
