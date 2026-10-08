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

Our SDK 55 field-notes prototype in `/root/data/field-notes-app` still uses JavaScript tabs and loses each tab’s history around note details. Refactor it to native Home, Saved, and Search tabs, give each tab a stack that shares the note-detail route, and move filtering into the native header search. Keep `/`, `/saved`, `/search`, and `/notes/:id` stable, preserve the current note and saved-state behavior, and deliver the updated project at `/root/results/field-notes-app`.
