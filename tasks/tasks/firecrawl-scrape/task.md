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

Grab every documentation URL listed in `/root/data/targets.txt` and save clean, main-content Markdown plus the links found on each page. Some pages render client-side, so make sure their actual content is captured; redact personal contact details.

Put one Markdown file per URL and a machine-readable manifest tying each URL to its file and extracted links under `/root/results/snapshot/`.
