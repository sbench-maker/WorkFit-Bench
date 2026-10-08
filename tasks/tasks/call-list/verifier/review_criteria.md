# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__lead_ranking` | Rule test | The five call cards select and order the eligible contacts according to the frozen pipeline, activity, contact restriction, and ranking policy data. |
| `completion__calendar_feasibility` | Rule test | Each selected lead has one distinct 20-minute proposal on the target date inside working hours, with no collision with a busy or proposed interval. |
| `completion__follow_up_scope_and_safety` | Rule test | Drafts cover exactly the selected leads whose latest thread is unanswered beyond the policy threshold, and the artifact does not represent messages, events, or CRM changes as executed. |
| `completion__follow_up_draft_quality` | LLM Judge | Each due draft is concise, references the actual unresolved conversation, asks for a clear next step, and is ready for owner review without implying it was sent. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
