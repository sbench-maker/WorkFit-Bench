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

Our HR people-directory service under `/root/data/` is ready for its first GKE release. Build an onboarding bundle at `/root/results/gke-onboarding/` with a production Dockerfile and Kubernetes manifests, using the repository’s deployment brief.

- I need the service to remain internal, highly available, and wired to its real readiness and liveness behavior.
- I’m concerned about staff data or secret values being baked into the image or manifests.
- I want the pinned image, runtime dependencies, resource policy, and existing platform-managed configuration carried through accurately.
