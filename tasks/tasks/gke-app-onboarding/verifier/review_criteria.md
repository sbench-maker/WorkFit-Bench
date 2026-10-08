# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__containerization` | Rule test | The Dockerfile uses the required Node major version, installs production dependencies, includes the application code, starts the service on its declared port as a non-root user, and does not include the development staff fixture. |
| `completion__workload_reliability` | Rule test | The Deployment targets the brief's workload, namespace, replicas, immutable image, resources, rolling-update policy, shutdown allowance, and distinct application health endpoints. |
| `completion__configuration_security` | Rule test | The workload references the existing ConfigMaps and Secret without embedding values, mounts staff data read-only, supplies writable cache storage, and applies the brief's pod/container security controls. |
| `completion__internal_connectivity` | Rule test | An internal ClusterIP Service selects the Deployment pods and routes port 80 to the actual application port, with no externally exposing resource. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
