# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__yesterday_accuracy` | Rule test | Yesterday accurately covers the subject's completed webhook work, active audit-panel work, and code review, with useful ticket and PR traceability and no prior-day boundary leak. |
| `completion__today_fidelity` | Rule test | Today carries forward the explicit component-test and review-response plan plus the scheduled rollout-metrics pairing. |
| `completion__blocker_handling` | Rule test | The blocker section identifies the still-blocked replay issue, what is needed, and who can help, without presenting resolved ticket or CI failures as active blockers. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
