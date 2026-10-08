# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__source_fidelity` | Rule test | The recap preserves the call identity, attendees, operational priorities, final pilot scope, and current CRM stage from the frozen inputs. |
| `completion__action_tracking` | Rule test | The internal recap captures the five vendor/customer handoffs with the correct owner, work, and agreed date or condition, including Maya's unresolved technical follow-up. |
| `completion__commitment_boundaries` | Rule test | The deliverables keep competitive notes internal, preserve confirmed-versus-open technical distinctions, use the corrected seat count and commercial/identity packaging, and label milestone dates as tentative or conditional. |
| `completion__customer_communication` | LLM Judge | The requested plain-text customer email from Maya states the customer outcome, responsibilities, dependencies, and next step without copying internal CRM or transcript-only details. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
