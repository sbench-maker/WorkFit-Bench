# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__artifact_integrity` | Rule test | The requested DOCX exists, opens as a valid Office package, and contains the document and visual parts needed for the packet. |
| `completion__release_fact_accuracy` | Rule test | Release identity, timing, components, monitoring thresholds, endpoint, observation period, and artifact digest agree with release_facts.json, with obsolete draft values removed. |
| `completion__scope_preservation` | Rule test | Every deployment, verification, and rollback step from the draft remains present exactly once, and every approval row reflects the authoritative decision state. |
| `completion__template_and_navigation` | LLM Judge | Page geometry, corporate header/footer, semantic style properties, live pagination, heading outline levels, and updateable TOC behavior match the supplied template and requested navigation needs. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
