# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_usability` | Rule test | The requested project, README, default persistent index, and batch JSON exist, are readable, and the documented CLI can reproduce the batch. |
| `completion__persistent_lifecycle` | Rule test | A fresh corpus can be indexed and then queried correctly after the original Markdown and catalog are unavailable. |
| `completion__retrieval_relevance` | Rule test | Representative questions across products and topics cite the exact section containing the applicable operational directive. |
| `completion__scope_safety` | Rule test | Citations match every requested product, release, region, audience, and lifecycle filter; unsupported scopes return insufficient with no borrowed citation. |
| `completion__answer_correctness` | Rule test | Every bundled query has one non-empty response, and representative answers preserve the material actions, thresholds, identifiers, and sequence facts in their directives. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
