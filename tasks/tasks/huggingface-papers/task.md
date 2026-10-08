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

Our applied-ML team needs a go/no-go brief on the paper snapshot in `/root/data/` for English/Spanish support-ticket summarization. Save a structured research brief to `/root/results/output.json`.

- I need the central claim, method, and strongest quantitative evidence separated from author interpretation.
- Include the paper's headline language-specific quality result for both English and Spanish, with the metric, evaluation split, and revision/version attached to each value; do not substitute operational latency or a different metric for either language result.
- I care whether the reported setup supports our 8 GB deployment; flag evidence gaps and revision conflicts rather than smoothing them over.
- Include the authors and every linked model, dataset, and Space so the team can reproduce the work.
