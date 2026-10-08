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

Our Growth and Product teams need a corrected GA4/GTM tracking plan before Kiteframe's trial launch. Audit the product journey, current container export, and QA event stream in `/root/data/`; use the stated business decisions to identify tracking defects and define a lean event, property, conversion, consent, and validation design. Preserve quantified fixture evidence, and do not include personal data in proposed analytics properties. Write the implementation-ready JSON handoff to `/root/results/tracking_plan.json` using the contract in the data folder.
