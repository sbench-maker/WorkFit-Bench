# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_and_context` | Rule test | The requested Markdown brief is readable and reports the interview identity, participants, corrected team context, and current tools without contradicting the transcript. |
| `completion__committed_followups` | Rule test | The follow-up list contains all four agreed date-owner-action commitments and does not promote explicitly deferred brainstorms into actions. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
