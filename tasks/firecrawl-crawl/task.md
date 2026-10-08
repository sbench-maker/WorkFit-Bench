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

Create a frozen content export of Northstar's current release-notes section for the support team's analysis. The local site fixture and CLI notes are under `/root/data/`. Crawl all reachable pages under `/docs/releases`, excluding drafts and legacy notes; follow links no deeper than five hops and cap the crawl at 80 pages. Save the completed crawl JSON, including extracted page content, to `/root/results/output.json`.
