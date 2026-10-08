# Acme Router offline checkout

This fictional, dependency-free crate models the Apollo Router lifecycle closely enough to develop and test one native plugin without a registry or running gateway. Keep the public types and filenames because the load-test harness imports them directly.

## Query-budget policy

Implement `src/plugins/query_budget.rs` using the hooks exposed by `framework::Plugin`:

- At the HTTP/router phase, read the configured client-tier header case-insensitively. Trim and lowercase its value. Store a known tier in `TIER_CONTEXT_KEY`; missing, blank, or unknown values use the configured default tier.
- At the execution phase, obtain the tier from context and choose its configured ceiling. Mutation plans use the lower of that ceiling and `mutation_max_cost`. Cost exactly at the effective ceiling is allowed; only greater values are rejected.
- A rejection short-circuits the inner execution service and returns the configured HTTP status plus one GraphQL error. Its extension code is `error_code`; its numeric `actual_cost` and `cost_limit` extensions describe the decision.
- Disabled mode returns both services unchanged. Valid allowed requests reach each inner service exactly once.
- `QueryBudget::new` should reject unusable configuration (empty header/default/error code, missing default tier, zero ceilings) rather than leaving a runtime trap.

Register the plugin as `acme.query_budget`, expose it from `src/plugins/mod.rs`, and complete `config/router.yaml` from `policy/query_budget_policy.json`. The policy and the 240 generated cases are fictional local fixtures.

Run all checks with:

```bash
cargo test --offline
```
