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

Compare the AtlasPay renewal with BeaconAP as an AP automation replacement using the proposal, contract, diligence, and operating records in `/root/data`. Give procurement a three-year TCO, a side-by-side view of performance, contract, and security risks, a clear sign-off recommendation, and concrete negotiation points. Distinguish observed AtlasPay performance from BeaconAP commitments and flag material assumptions. Save the review to `/root/results/vendor_review.md`.

Use `requirements_matrix.csv` for must-have and weighted requirements, and preserve the evidence status in `input_manifest.json` when sources are missing or incomplete. Keep quoted vendor commitments, observed operating results, and analyst assumptions visibly separate in both the comparison and recommendation; a conditional sign-off should name the condition, owner, and fallback.
