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

The reward boost screen in the bundled Android sample still has a stub controller. Inspect `/root/data/android_app/` and finish its rewarded-ad integration, saving the completed `RewardedBoostController.java` to `/root/results/RewardedBoostController.java`. Use the fixture's GMA API contract and placement configuration: keep the watch button unavailable until an ad is ready, show only after the player explicitly taps it, grant exactly the SDK-provided reward, and reload after dismissal or presentation failure. SDK callbacks are background callbacks, so UI changes must be marshalled to the UI thread.
