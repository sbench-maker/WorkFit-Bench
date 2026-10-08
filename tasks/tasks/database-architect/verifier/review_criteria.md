# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__relational_integrity` | Rule test | The target model covers the transactional domain and enforces tenant-scoped identity, financial snapshots, inventory safety, idempotency, history, shipment identity, and outbox/audit integrity. |
| `completion__access_and_lifecycle` | Rule test | Indexes and partitions support the high-value predicates, sort orders, retry queues, append-only timelines, and expiring webhook payloads represented in the workload and retention brief. |
| `completion__migration_and_resilience` | LLM Judge | The handoff gives an executable, low-downtime migration with reconciliation gates, tenant-aware rollout, explicit rollback triggers that preserve intervening writes, and backup/failover measures meeting residency, RPO, and RTO needs. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
