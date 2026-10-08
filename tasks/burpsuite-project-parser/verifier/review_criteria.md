# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__audit_scope_fidelity` | LLM Judge | Every Burp audit item is represented once with the correct severity, confidence, and affected URL. |
| `completion__evidence_based_disposition` | Rule test | Confirmed behavior, traffic-contradicted scanner leads, and inconclusive findings are distinguished consistently with the captured evidence. |
| `completion__traffic_evidence_integrity` | Rule test | Findings contain traceable, substantive traffic evidence where capture exists, do not cite nonexistent traffic records, and include no body excerpt over 1000 characters. |
| `completion__capture_limitations` | Rule test | The artifact warns that the administrative host is absent from proxy capture and that a gzip-encoded script body cannot be corroborated from the text index. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
