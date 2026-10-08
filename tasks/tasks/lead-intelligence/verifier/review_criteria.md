# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__qualified_shortlist` | Rule test | The plan contains exactly the twelve highest-ranked eligible people after verified profile resolution, with no duplicate identities, opted-out contacts, active opportunities, or customers. |
| `completion__scoring_and_ranking` | Rule test | Each present shortlisted person has the fit score determined by the six campaign signals, and the list follows the stated score and tie-break order. |
| `completion__verified_paths_and_routing` | Rule test | Lead records use the best verified introduction path when one exists, reject unverified decoys, and route the first draft through the highest available channel and correct recipient under the campaign order. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
