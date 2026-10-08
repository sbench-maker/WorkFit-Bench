# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__notebook_artifact` | Rule test | The requested file is a readable nbformat 4 notebook with an ordered mix of substantive markdown and code cells rather than an unfilled scaffold. |
| `completion__fresh_run_reproducibility` | Rule test | All code cells execute successfully in order from a clean Python state using only the standard library and bundled local data. |
| `completion__policy_summary_correctness` | Rule test | The executed notebook exposes complete priority and channel summaries whose eligible, met, breached, pending, and one-decimal compliance values agree with the supplied policy and ticket export. |
| `completion__instructional_progression` | LLM Judge | The notebook leads an analyst through context, prerequisites, explained transformations, a worked result, and a runnable practice exercise with an answer scaffold. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
