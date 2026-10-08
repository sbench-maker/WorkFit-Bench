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

The video platform team has six Remotion support cases queued for tomorrow. Use the offline documentation mirror in `/root/data` to find the relevant pages and verify the guidance in their Markdown snapshots. Save the handoff to `/root/results/output.json`, following the mirror README’s format. For each case, give the documented answer and the smallest set of canonical page URLs that supports it; flag material version or environment caveats rather than guessing.

Structure `output.json` with `snapshot_id` and a top-level `cases` array. Each of the six queued cases must appear exactly once and contain `case_id`, `answer`, `sources`, and `caveats`. `sources` must be an array of canonical Remotion documentation URLs; use an empty `caveats` array when no material version or environment qualification applies.
