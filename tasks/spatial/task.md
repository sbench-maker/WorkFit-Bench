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

Our web map needs a service-ready venue layer from the local exports in `/root/data/`. Build `/root/results/venue_service_map.geojson` as a WGS84 GeoJSON FeatureCollection containing only active venues with valid coordinates, preserving their venue metadata and adding the applicable service zone plus the nearest pickup hub and spheroid distance in meters. Treat zone boundaries as covered; where zones overlap, use the lowest numeric priority from the zone data, and retain out-of-zone venues with a null zone.
