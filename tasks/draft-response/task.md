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

Draft an executive-ready email response to the active HelioFleet escalation identified in `/root/data/`, using the frozen CRM, support, correspondence, incident, and policy records there. Save the sendable email and clearly separated internal review notes in `/root/results/heliofleet_escalation_response.md`; tailor it to the customer relationship and prior thread, state only approved facts and commitments, and give a concrete next update. The customer is threatening to cancel, so be candid and accountable without promising a resolution time, service credit, or roadmap change that has not been authorized.
