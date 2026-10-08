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

Build a SERP-overlap topic-cluster plan for Hearthwise's “indoor herb garden” resource center from the frozen keyword metrics and search results in `/root/data/`. Merge keywords that belong on one page, exclude navigational terms, choose a pillar with coherent spokes, and design a usable internal-link matrix; every supplied keyword should have a traceable disposition, with borderline grouping decisions flagged. Save the machine-readable plan to `/root/results/cluster-plan.json` and an offline interactive map to `/root/results/cluster-map.html`.
