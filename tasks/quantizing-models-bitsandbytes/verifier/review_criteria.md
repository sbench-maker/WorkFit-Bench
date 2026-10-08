# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_coverage` | Rule test | The requested JSON is readable and contains exactly one model- and GPU-traceable plan for every queued request. |
| `completion__mode_and_placement` | Rule test | Each request has the correct accept/reject outcome, least-memory accuracy-compatible precision, and native or CPU-offload placement under the supplied memory and latency policy. |
| `completion__resource_accounting` | Rule test | Available GPU weight space, total weight memory, GPU residency, CPU spill, and expected accuracy loss are internally correct for the plan's declared mode and placement; rejected work does not invent deployment figures. |
| `completion__runtime_configuration` | Rule test | Accepted plans carry configuration consistent with their declared mode, target GPU, and model, including safe offload limits where needed. |
| `completion__summary_consistency` | LLM Judge | Counts by status, mode, and placement and aggregate memory totals reconcile to the submitted request-level plans. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
