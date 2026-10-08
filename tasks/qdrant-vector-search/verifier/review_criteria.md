# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_replay` | Rule test | Both requested files exist; the JSON is readable and grouped by query, and the retriever rebuilds the batch artifact offline through the documented command with the same semantic hits. |
| `completion__filter_scope` | Rule test | Every batch request appears exactly once, returns the correct number of eligible hits, and never crosses tenant, product, language, publication-state, region, document-type, or effective-date constraints. |
| `completion__cosine_ranking` | Rule test | Within each eligible candidate set, point IDs are ordered by the requested cosine similarity and scores accurately represent that similarity. |
| `completion__payload_fidelity` | Rule test | Each hit includes the exact source payload for its point without exposing stored vectors as result metadata. |
| `completion__support_auditability` | LLM Judge | The batch output is organized so a support reviewer can trace each request to its ordered hits, understand the returned article context and applied scope, and recognize legitimate no-hit results without rereading raw vector files. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
