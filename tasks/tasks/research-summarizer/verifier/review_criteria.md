# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_scope` | LLM Judge | The requested Markdown brief is readable, substantive, and covers all four supplied documents. |
| `completion__factual_fidelity` | Rule test | Decision-relevant numeric findings for each source are reported accurately and remain attributable to the correct source. |
| `completion__traceability_references` | Rule test | Each source has usable page or section anchors and a complete APA-style reference based only on supplied metadata, including an explicit undated treatment for the white paper. |
| `completion__evidence_synthesis` | LLM Judge | The brief compares all four sources on agreement, disagreement, non-comparability, and shared evidence gaps, then states a weight-of-evidence conclusion. |
| `completion__decision_recommendation` | LLM Judge | The brief gives an explicit rollout recommendation and safeguards, distinguishing reviewed AI drafts from fully automated posting. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
