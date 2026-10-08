# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__request_outcomes` | Rule test | Every queued request appears exactly once and is identified as completed, failed, or timed out according to the frozen service behavior. |
| `completion__record_coverage` | Rule test | Completed jobs contain the full set of unique extracted record IDs, while non-completed jobs do not masquerade as successful feeds with records. |
| `completion__record_fidelity` | Rule test | Extracted product, comment, post, review, and job values match the final records returned by the service, including the latest version of repeated records. |
| `completion__summary_and_failures` | LLM Judge | The compact totals reconcile with the ledger and extracted records, and each failed or timed-out request includes a usable reason. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
