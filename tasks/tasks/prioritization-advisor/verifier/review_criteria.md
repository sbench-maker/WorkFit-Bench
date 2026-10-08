# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__framework_fit` | LLM Judge | The primary recommendation is a defensible recurring prioritization framework for AsterLane's early-PMF stage, small team, uneven data, stakeholder misalignment, and mixed backlog, and its rationale distinguishes framework fit from a universal ranking claim. |
| `completion__evidence_and_tradeoffs` | LLM Judge | The recommendation accurately uses the packet to diagnose the RICE pilot and stakeholder conflict, treats unknown reach responsibly, and protects mandatory obligations and strategic judgment without fabricating capacity or certainty. |
| `completion__implementation_design` | LLM Judge | The rollout is usable for recurring monthly and quarterly decisions: it defines how items enter comparison, supplies a concrete scoring or classification template, assigns collaborative roles, handles evidence and disagreements, and records gates or overrides within the team's time constraints. |
| `completion__alternative_and_lifecycle` | LLM Judge | The runner-up is contextually plausible with clear gains and losses, and the recommendation gives specific failure safeguards and stable reassessment triggers that avoid both framework whiplash and set-it-and-forget-it use. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
