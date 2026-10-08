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

Triage the security findings in `/root/data/harbor_portal.burp` for our release review. Start from the Burp audit items, corroborate them against captured requests, response headers, and only targeted response bodies, then write `/root/results/output.json` with a prioritized finding list, affected URLs, traffic evidence, disposition, and reviewer next steps. Treat scanner results as leads rather than proof; flag capture or encoding limits, and keep any included body excerpt safely truncated.

Keep each finding tied to a stable audit-item or request/response identifier, and distinguish confirmed, rejected/false-positive, and needs-review dispositions. The JSON schema is flexible, but the finding collection and its evidence should be directly discoverable without relying on prose outside `output.json`.
