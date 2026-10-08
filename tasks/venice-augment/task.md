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

Release Engineering needs a go/no-go call on `orbit-ci:2026.09-rc2`. The frozen augmentation service and candidate manifest are under `/root/data/`. Search for the current compatibility, security, identity, and migration guidance, then scrape the relevant pages and reconcile stale or incomplete material against the candidate.

Save a self-contained `/root/results/output.json` with the decision, supported requirements and remediation actions, plus traceable source entries. Treat blocked social hits as unusable and don’t promote a claim from a search snippet unless the scraped page supports it.
