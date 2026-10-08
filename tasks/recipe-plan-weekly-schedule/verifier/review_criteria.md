# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__gap_accuracy` | Rule test | Reported usable gaps cover the target week's real 75-minute opportunities without treating buffered commitments, protected lunch, or the opaque all-day absence as free time, while correctly handling cancelled, transparent, overnight, tentative, and cross-timezone events. |
| `completion__proposed_schedule` | Rule test | Exactly six correctly titled 75-minute blocks are placed on valid 15-minute boundaries inside usable gaps, with no collisions, at least four distinct days, and no more than two blocks on a day. |
| `completion__agenda_transition` | LLM Judge | The updated workweek agenda preserves each active source event at its original time, includes every proposed addition, avoids duplicate commitments, does not present a cancelled item as active, and stays within the requested week. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
