# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__primary_diagnosis` | Rule test | The report identifies Cloud NAT port exhaustion as the primary cause and correctly identifies the gateway, source service, destination, protocol port, and incident scope. |
| `completion__trend_and_sources` | Rule test | Hourly SRC-reporter traffic and NAT allocation-drop totals are accurate, and the three most impacted internal sources and their drop counts are correct. |
| `completion__alternative_evidence` | LLM Judge | The report uses the relevant firewall and RTT evidence to distinguish the incident from firewall blocking or genuine latency degradation. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
