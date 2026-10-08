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

Build a self-contained, interactive user-research synthesis dashboard from the frozen TalentLoop materials in `/root/data/`. It should help the product trio decide whether the September sprint should prioritize a shared approval-status timeline, configurable reminders, or clearer ownership controls. Keep quotes and metrics faithful, distinguish internal opinions from user evidence, surface segment conflicts, and make the recommendation traceable through themes and alternatives. Include a concise decision memo and a small, measurable experiment queue. Save it as `/root/results/index.html`.
