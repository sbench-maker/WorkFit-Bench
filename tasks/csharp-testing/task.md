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

The reservation service in `/root/data/ParcelPilot` needs a reliable regression suite before the next release. Add focused xUnit tests for `InventoryReservationService.ReserveAsync`, covering its public contract around validation boundaries, case-insensitive duplicate SKUs, inventory decisions, dependency side effects, and cancellation-token propagation.

Leave the production code untouched, use the existing offline test project and packages, and place the completed repository at `/root/results/ParcelPilot`. The suite must run with `dotnet test` without network access.
