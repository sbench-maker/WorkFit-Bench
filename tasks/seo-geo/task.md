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

Our product marketing team needs an AI-search visibility audit of the fictional Northstar Relay site. Use the frozen crawl, rendered-content, query, and brand-signal exports in `/root/data`; treat that snapshot as the complete evidence set and don't use the network.

Write `/root/results/GEO-ANALYSIS.md` with overall and platform readiness scores, crawl-eligibility/crawler/SSR/llms.txt/brand findings, specific citable-passage rewrites, and the five changes we should prioritize. Keep recommendations traceable to page paths or record IDs, and don't present speculative mechanisms as proven citation levers.
