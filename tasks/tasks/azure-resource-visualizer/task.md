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

We need an architecture handoff for fictional production group `rg-helio-prod`, using the frozen exports in `/root/data/`. Create `/root/results/rg-helio-prod-architecture.md`.

- I need every in-group resource accounted for with architecture-relevant SKU, region, and configuration details.
- I need the Mermaid topology to distinguish network placement, hosting dependencies, runtime and data flows, identity access, observability, and documented external dependencies.
- Please keep observations evidence-backed, treat candidates as unconfirmed, and never expose secret values.
