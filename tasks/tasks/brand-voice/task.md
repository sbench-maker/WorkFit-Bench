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

Build a reusable voice profile for Mira Voss from the source archive in `/root/data`, then use it to write the Driftline Replay launch copy from the included campaign brief. Save `/root/results/voice_launch_kit.md` with a concise `VOICE PROFILE` plus one X post and one customer email; preserve the clear public/private channel split, and keep every product claim within the brief. Treat newer originals as the best evidence when older samples conflict.
