# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__catalog_coverage` | LLM Judge | Every authoritative release change appears exactly once and no unknown change is published. |
| `completion__factual_fidelity` | Rule test | Identity, command, availability, operational values, and customer notices agree with the authoritative release evidence for the records that are present. |
| `completion__publication_safety` | Rule test | The corrected catalog contains no unsupported guarantee or universal-availability claim and is clearly marked for the correct approved release. |
| `completion__review_convergence` | LLM Judge | The audit credibly shows two distinct, context-isolated reviewers using the same inputs and rubric in each round, specific blocker discovery, issue-driven repair, fresh re-review after changes, and a final gate that opens only when both reviewers pass within three rounds. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
