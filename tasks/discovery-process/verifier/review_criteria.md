# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | LLM Judge | The requested JSON exists, is readable, and exposes the problem, research scope, synthesis, funnel, experiment, decision, and next-step content requested for review. |
| `completion__research_scope` | LLM Judge | The record uses all and only completed target interviews, identifies excluded participant records, and reports saturation consistently with interview order and coded themes. |
| `completion__theme_synthesis` | LLM Judge | The three leading pain points are ranked from distinct target interviews, intensity, strategic fit, and deduplicated support evidence, with traceable source IDs. |
| `completion__funnel_evidence` | LLM Judge | Eligible account counts, import-outcome activation groups, and the clean-versus-validation activation gap agree with the frozen funnel and target policy. |
| `completion__experiment_decision` | LLM Judge | Both randomized arms use intention-to-treat denominators, primary and guardrail outcomes are correct, thresholds are evaluated correctly, and the resulting roadmap call selects the supported solution. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
