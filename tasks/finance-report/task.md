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

Build a self-contained, single-page Q3 FY2025 financial report for Alder Peak Systems from the files in `/root/data/`. Save it as `/root/results/index.html`. Include an executive KPI strip, trailing-12-month revenue view, Q3 operating-cost breakdown, Q3-versus-Q2 P&L, top accounts, and a grounded Q4 outlook. Follow the supplied design tokens, keep figures traceable to the data definitions, and make the desktop report readable on a narrow screen.
