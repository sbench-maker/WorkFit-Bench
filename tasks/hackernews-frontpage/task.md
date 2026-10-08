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

A failed fetch left us only the captured Hacker News front page at `/root/data/hn_frontpage_snapshot.html`. Extract all 30 displayed stories, in page order, into one JSON document at `/root/results/output.json`; for each story include the displayed rank, HN item ID, title, link URL, points, and comment count, plus the total count. Decode visible HTML text and links. Preserve unavailable scores/comments as `null`, while a `discuss` link means zero comments.
