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

Configure the offline n8n participant-intake workflow in `/root/data/` from the coordinator’s change brief and bundled node catalog, then save the deployable export as `/root/results/configured_workflow.json`. Keep the existing nodes, names, IDs, and wiring; make each node’s operation-specific and conditional parameters valid, preserve every documented response path, and do not invent credential IDs. The export must pass the bundled offline validator and remain inactive for human review.
