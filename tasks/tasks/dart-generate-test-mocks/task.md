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

Our reservation service is ready, but its database behavior is unprotected. In `/root/data/reservation_app`, complete the Dart unit-test suite for `ReservationService` using generated Mockito mocks—no live database—and cover the documented decisions, async failures, write ordering, and rollback behavior. Keep the cases easy for the team to extend, make the full suite pass offline, and place the finished project (including generated mock source) at `/root/results/reservation_app`.
