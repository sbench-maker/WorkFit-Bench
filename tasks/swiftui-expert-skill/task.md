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

The LoopLog activity feed in `/root/data/LoopLog` is due for our iOS 17 release, but filtering and sorting can target the wrong favorite, some copy stays English in Japanese, and the screen still uses older SwiftUI patterns. Refactor the existing project so search, favorites, detail navigation, empty states, and the row animation remain intact. Keep the 500-item feed responsive and make row actions clear to VoiceOver.

Place the revised project at `/root/results/LoopLog`; don’t add dependencies or network-backed previews.
