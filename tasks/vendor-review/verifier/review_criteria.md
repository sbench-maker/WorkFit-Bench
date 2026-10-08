# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested Markdown artifact is readable, substantive, and exposes both vendors plus the requested cost, performance, contract/security, recommendation, and negotiation content. |
| `completion__tco_accuracy` | Rule test | Each vendor's three-year TCO and the cost difference are calculated from the forecast, mandatory fees, escalators, overages, transition costs, and exit treatment in the packet. |
| `completion__comparison_fact_accuracy` | Rule test | The review reports the incumbent's observed availability and Sev-1 performance accurately and preserves material, frozen comparison facts about commitments, integration, timing, and exit terms. |
| `completion__risk_assessment` | LLM Judge | The assessment distinguishes observed evidence from commitments, prioritizes vendor-specific legal, security, continuity, operational, implementation, and financial risks, and pairs material gaps with feasible mitigations. |
| `completion__decision_and_negotiation` | LLM Judge | The recommendation gives procurement an implementable sign-off path that weighs TCO, performance, policy blockers, and transition feasibility, with specific leverage points, conditions, and a workable fallback. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
