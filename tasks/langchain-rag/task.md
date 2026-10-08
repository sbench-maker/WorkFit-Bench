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

Our support team needs a reusable offline knowledge assistant. Complete the starter in `/root/data/solara_support_rag/` so it loads and chunks the Markdown manuals, builds a restart-safe local index, and answers the bundled batch with source IDs while honoring release, region, audience, and lifecycle filters; outdated or unsupported scopes must never be blended in. Save the runnable project and persisted index under `/root/results/solara_support_rag/`, plus the batch answers at `/root/results/output.json`. Keep the workflow network-free.
