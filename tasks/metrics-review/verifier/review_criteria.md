# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__scorecard_correctness` | Rule test | Current, previous, target, change, and status values correctly reflect the metric definitions, weighted source observations, directionality, and target bands. |
| `completion__scope_consistency` | LLM Judge | Every source-defined metric is represented without conflicting scorecard duplicates, and weekly value teams is identifiable as the North Star. |
| `completion__evidence_based_diagnosis` | LLM Judge | The review identifies the concentrated Starter EMEA deterioration, distinguishes the regional incident from the persistent post-incident pattern, recognizes meaningful bright spots, and treats timing or correlation as hypotheses rather than proof. |
| `completion__action_and_alert_quality` | LLM Judge | The review provides next steps tied to its highest-impact findings and defines alerts with scope, trigger, severity, owner, and response. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
