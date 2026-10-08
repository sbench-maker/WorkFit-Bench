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

Our Q4 planning meeting needs a decision brief from the frozen research and delivery estimates in `/root/data/`. Save it as `/root/results/prioritization_brief.json`.

- I need customer problems ranked by Opportunity Score, with unreliable or duplicate survey rows handled per the data notes.
- I need proposed initiatives compared with RICE, including dependencies and the fixed capacity limit in the recommended Q4 set.
- I need the trade-offs and any high-ranked exclusions explained so stakeholders can challenge the plan.
