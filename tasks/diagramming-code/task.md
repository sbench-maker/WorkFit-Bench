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

Release review for the fictional Lumen Relay service is blocked on understanding how HTTP handlers reach its template runtime. Inspect `/root/data/relay_service` and create `/root/results/security_architecture.md` with a left-to-right Mermaid module dependency map plus a Mermaid attack-surface/data-flow view ending at `run_template`; include every request-handler path that reaches it and distinguish untrusted entry points. Add a short reviewer note naming the most important bypass or trust boundary visible in the code.
