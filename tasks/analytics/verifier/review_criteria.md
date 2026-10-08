# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__qa_audit_accuracy` | Rule test | All six scoped QA metrics correctly quantify duplicates, consent leakage, personal-data properties, invalid names, and incomplete events from the frozen stream. |
| `completion__event_measurement_design` | Rule test | Every required product action has a consistently named event with an implementation source, a success trigger, the decision-critical properties, granted-consent gating, and no PII fields. |
| `completion__ga4_measurement_configuration` | Rule test | The conversion set and counting semantics match the supplied KPI definitions, while event-varying segmentation is registered without redefining automatic acquisition or standard ecommerce fields. |
| `completion__implementation_validation_readiness` | LLM Judge | The handoff gives developers and analysts actionable changes and test scenarios that verify success triggers, required values, consent denial, privacy, and retry/reload deduplication before launch. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
