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

Run the structured-feed requests in `/root/data/feed_requests.json` against the bundled offline dataset service described in `/root/data/README.md`, then consolidate the completed URL extractions into `/root/results/output.json`. Preserve each request ID and its website-specific records, deduplicate repeats within a request, and retain failed or timed-out jobs instead of treating them as empty successes. Include a compact collection summary so the content team can see what is usable.
