# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__fleet_target_state` | Rule test | Every exported cluster has an attributable plan with the policy-correct logging, monitoring, Managed Prometheus, Dataplane V2 metrics, and service target state, including accurate no-op decisions. |
| `completion__command_correctness` | Rule test | Each drifting cluster has an update command that targets the correct project and location and implements every required setting change, while compliant clusters receive no gratuitous update and commands contain no unsafe payload or placeholder. |
| `completion__monitoring_design` | Rule test | Google Cloud Monitoring dashboards and alerts cover production control-plane latency, scheduling, workload CPU/memory and crash loops, composite node health, and the applicable PVC and GPU risks with correct conditions and scope. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
