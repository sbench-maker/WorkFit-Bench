# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__assumption_coverage` | Rule test | Every assumption in the frozen register is represented in the decision brief. |
| `completion__matrix_decisions` | Rule test | Each represented assumption is assigned the correct high/low Impact and Risk quadrant and the corresponding test, proceed, reject, or defer action under the supplied scoring rules, including threshold-boundary cases. |
| `completion__experiment_quality` | LLM Judge | Every assumption selected for testing has a tailored experiment that fits an available resource and its capacity, stays within the two-week/no-production and assumption-specific constraints, measures actual behavior, and states a numeric threshold plus the pass/fail roadmap decision. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
