# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | LLM Judge | The requested Markdown artifact is readable and contains a distinct reusable voice profile, X post, and customer email. |
| `completion__campaign_fidelity` | Rule test | Product identity, quantitative claims, availability statements, and safety boundaries in the launch drafts do not contradict the frozen campaign brief. |
| `completion__profile_source_fidelity` | LLM Judge | The voice profile draws its guidance from the supplied archive, prioritizes newer originals over conflicting 2023 outliers, and separates public language from private guidance. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
