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

Our parcel-quoting package in `/root/data/parcel_quote` has duplicated zone and surcharge logic across its library and JSONL CLI paths. Refactor it into a cleaner multi-file design, removing dead code and reducing nesting, while preserving public imports, CLI JSON, rounding, validation, and error messages. The direction in `APPROVED_PLAN.md` is already approved.

Place the complete runnable repository at `/root/results/parcel_quote` and add `/root/results/refactor_notes.md` summarizing the structural changes and regression checks. Keep it offline, add no dependencies or product behavior, and do not commit.
