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

The Pulseboard status panel in `/root/data/` has a dead hover effect and a spinner that never advances. We need it ready for the Makepad 2.0 demo, with the card copy staying visible while the hover transition and loading loop run independently.

Using the bundled interaction brief and starter source, produce `/root/results/ops_status_panel.rs`. Keep the existing widget names, IDs, layout, and copy; implement the requested Animator states and shader behavior so the file can drop back into the demo without follow-up.
