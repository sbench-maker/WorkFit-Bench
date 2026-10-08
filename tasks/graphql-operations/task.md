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

The media-review client is replacing its handwritten request strings for the workspace described in `/root/data/ui_contract.json`; the frozen API schema and representative variables are in `/root/data/`. Create `/root/results/review-workspace.graphql` with production-ready operations to load and page through the workspace assets, submit a reviewer decision, and subscribe to decision changes. Keep payloads limited to what the UI consumes, make internal notes conditional, and factor shared asset and reviewer selections so cache updates stay consistent.
