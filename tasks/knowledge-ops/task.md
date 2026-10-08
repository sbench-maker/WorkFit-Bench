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

Reconcile the offline engineering knowledge exports in `/root/data/` into `/root/results/knowledge_sync.json`. Deduplicate cross-source facts, classify each canonical topic into the right storage layer, and express create, update, no-op, or review actions without overwriting newer active project truth. Redact credential-like material from retained text, preserve provenance and cross-references, and include a browsable topic index plus a review queue for unresolved conflicts. Follow the bundled sync policy.
