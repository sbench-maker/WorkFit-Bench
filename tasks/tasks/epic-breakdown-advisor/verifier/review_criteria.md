# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__usable_story_set` | LLM Judge | The requested Markdown plan is readable and substantive, contains a meaningful set of user stories with persona/action/outcome and Given/When/Then acceptance criteria, and gives each story an estimate no higher than the frozen five-point ceiling. |
| `completion__scope_and_policy_fidelity` | Rule test | The plan accounts for the complete frozen epic scope, including items it recommends deferring, and preserves the material value, regulated, international, bulk, carrier, SLA, and performance rules in the proposed behavior. |
| `completion__vertical_splitting_quality` | LLM Judge | The selected split patterns fit the epic, the first slice traverses the complete requester-visible return journey in a genuinely simple case, later slices add coherent user-valued variations, and no story is merely a technical layer or isolated workflow stage. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
