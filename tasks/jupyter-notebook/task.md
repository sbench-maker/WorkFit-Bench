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

Convert the rough training notes, SLA policy, and fictional ticket export in `/root/data/` into a self-contained Jupyter tutorial for new support analysts. Save it as `/root/results/first-response-sla-tutorial.ipynb`. Teach the policy-defined cleaning and classification through small runnable Python steps, include the requested worked summaries and an exercise with an answer scaffold, and explain the boundary and missing-response pitfalls. Keep it offline, standard-library-only, and concise enough for a 20-minute onboarding session.
