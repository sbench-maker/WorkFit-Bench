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

We’re validating the offline retrieval path for our support RAG service before the cluster rollout. The frozen export in `/root/data/` includes a collection contract, knowledge-base points, and filtered batch queries; tenant, language, product, publication state, and effective dates must remain isolated during cosine search.

Load it into embedded Qdrant, run every request, and leave a repeatable `/root/results/retriever.py` plus the results at `/root/results/output.json`. Include each hit’s payload metadata so Support can audit why it was returned.
