# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__portfolio_scope` | LLM Judge | The requested JSON is readable and contains 12-15 distinct candidates, a ranked top three drawn from them, and one refined winner with the requested pitch, experiments, objection, response, and pilot. |
| `completion__evidence_integrity` | Rule test | Each shortlisted direction is traceable to valid observation IDs, and the shortlist collectively connects its judgment to the supplied prior projects and capability changes without invented references. |
| `completion__pilot_constraint_consistency` | Rule test | The winner's pilot fits the 14-day offline envelope, does not exceed any stated resource estimates, avoids unavailable production or external dependencies, and uses declared local assets. |
| `completion__winner_refinement` | LLM Judge | The selected winner includes a problem-and-insight pitch, a concrete contribution, discriminating experiments, a serious objection and response, and a pilot decision. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
