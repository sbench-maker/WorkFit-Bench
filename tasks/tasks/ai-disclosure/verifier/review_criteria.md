# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__contribution_scope` | LLM Judge | The finalized disclosure covers every recorded post-opt-in AI contribution while excluding pre-opt-in and human-only work. |
| `completion__attribution_accuracy` | Rule test | Included work is assigned to the correct Autonomous, Assisted, or Advised level, and materially revised work clearly acknowledges human co-creation. |
| `completion__pr_consistency` | Rule test | The paste-ready PR block preserves the disclosure's category assignments and links to the correct branch disclosure path without introducing contradictory claims. |
| `completion__narrative_transparency` | LLM Judge | The disclosure summary and PR framing concisely distinguish surviving independent work, directed implementation, advice, and significant human redesign, without overstating AI ownership of the core feature. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
