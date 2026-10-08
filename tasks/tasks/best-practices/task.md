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

Harborlight’s partner console is due for an internal production launch. Audit the frozen site in `/root/data/site/` for browser security, compatibility, and production-quality problems, then create a hardened copy at `/root/results/hardened_site/` without dropping routes, records, or user-visible behavior.

Also write `/root/results/security_audit.json`: a concise, prioritized record of material findings with file evidence, risk, remediation, and whether each item was fixed or needs an operational decision. The snapshot is fictional and the review must remain offline.
