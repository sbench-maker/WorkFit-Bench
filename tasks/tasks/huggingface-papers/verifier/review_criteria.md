# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__linked_asset_coverage` | Rule test | Every linked model, dataset, and Space in the structured API snapshots is represented in the brief. |
| `completion__quantitative_evidence` | Rule test | The brief reports the corrected English and Spanish quality results plus the device latency and memory figures central to the adoption decision. |
| `completion__paper_identity` | Rule test | The brief identifies the requested paper revision and all four authors from the frozen paper metadata. |
| `completion__deployment_judgment` | LLM Judge | The go/no-go recommendation is useful for the stated English/Spanish 8 GB target: it reconciles the tested hardware with the actual memory boundary, handles the v1/v2 conflict, scopes language evidence, and proposes proportionate next checks. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
