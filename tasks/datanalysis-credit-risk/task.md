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

Clean and screen the pre-loan modeling extract under `/root/data/` and deliver `/root/results/credit_cleaning_report.xlsx`. Use the supplied screening policy and diagnostic exports, keep OOS partners out of modeling calculations, treat sentinel values as missing, and apply the feature gates in policy order. The workbook should let a model-risk reviewer reconcile sample exclusions, organization/month quality, missingness, IV/PSI, null-importance and correlation decisions, and identify the final modeling variables with clear reasons.
