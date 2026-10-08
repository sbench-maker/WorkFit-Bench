# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__incident_facts` | Rule test | The brief reports the supported incident identity, reconciled population, regional counts, affected and excluded data categories, support-note flag, and unresolved root cause from the frozen exports. |
| `completion__timeline_reconciliation` | Rule test | The brief distinguishes the supported activity-window boundary, first suspicious use, analyst escalation, vendor confirmation/provisional awareness, containment, and initial notice rather than treating conflicting timestamps as interchangeable. |
| `completion__agreement_obligations` | Rule test | All agreements implicated by the affected vendor, customer accounts, and insurance response are connected to their material notice, cooperation, liability, or consent terms. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
