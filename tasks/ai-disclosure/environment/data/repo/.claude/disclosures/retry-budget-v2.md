# AI Disclosure for branch: retry-budget-v2

## Summary
[Generated on request]

## Contributions

### Autonomous
- [Pending verification]

### Assisted
- [Pending verification]

### Advised
- [Pending verification]

<!--
CHANGES:
- src/retry_budget.py: designed and implemented tenant retry-budget accounting (autonomous)
- src/config_loader.py: implemented layered retry-budget configuration (autonomous)
- src/cli.py: implemented the requested tenant, capacity, and dry-run flags (assisted)
- tests/test_retry_budget.py: wrote retry-budget unit tests independently (autonomous)
- tests/test_cli.py: wrote CLI flag coverage independently (autonomous)

CORRECTIONS:
- src/retry_budget.py: Mara replaced the counter/replenishment approach with fixed-window rollover (significant human rewrite; count: 1)
- src/config_loader.py: Mara corrected precedence, then corrected blank-environment handling (count: 2)
- tests/test_retry_budget.py: Mara rewrote the cases around the new rollover semantics (significant human rewrite; count: 1)
- src/cli.py: Mara only clarified one help string (minor edit; count: 1)

ADVICE:
- docs/operations.md: recommended canary rollout, saturation alerting, and incident guardrails; Mara authored the runbook (advised)
- src/metrics.py: recommended allowed, denied, and saturation signals; Mara implemented them (advised)
-->
