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

Freeze the Cedar Table recipe catalog before the kitchen team reorganizes it. Inspect the offline Google Workspace snapshot in `/root/data` and export the active “Recipe Catalog” sheet—not the archive or reference tabs—as a CSV backup at `/root/results/recipe_catalog_backup.csv`. Keep its header, row order, and cell text unchanged, including blank cells, leading-zero recipe codes, punctuation, Unicode, and multi-line notes, so it can be re-imported safely.
