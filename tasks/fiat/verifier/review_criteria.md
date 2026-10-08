# Task delivery conditions

Every condition is mandatory. The final task score is 1 only if all pass; otherwise it is 0. There is no quality weighting or partial score.

| ID | Decision method | Required delivery condition |
|---|---|---|
| `completion__route_eligibility` | LLM Judge | The comparison includes all active methods that satisfy both limit types for 0.018 BTC, excludes suspended or limit-ineligible methods from the usable set, and recommends the lowest quoted BUY route. |
| `completion__economics_and_fallback` | Rule test | The current payment quotations, 0.018 BTC cost estimates, indicative market reference, and lowest-cost direct fallback are numerically correct. |
| `completion__wallet_funding` | Rule test | The artifact reconciles the existing wallet balance to the purchase cost and offers only deposit methods whose status and limits permit that shortfall. |
| `completion__market_support` | LLM Judge | The artifact positively confirms that an Australian AUD/BTC BUY request is supported by the applicable frozen capability response. |

Rule conditions pass only when all mapped test cases pass. LLM conditions pass only with an evidence-backed 10/10 binary decision. Unavailable verifier or Judge evidence is an evaluation error, not a task result.
