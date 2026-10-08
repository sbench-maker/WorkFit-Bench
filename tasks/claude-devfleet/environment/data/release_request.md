# Polaris service-token rollout

The fictional Polaris Payments settlement service needs scoped machine-to-machine
credentials before the 2026-10-02 release window. Replace long-lived vendor tokens
with per-tenant signed service tokens while preserving a 30-day compatibility window.

The change must cover token issue, revocation, and last-used metadata endpoints; a
reversible zero-downtime database migration; signing and scope enforcement; redacted
logs plus metrics and dashboards; operator documentation; and unit, integration, and
security tests. Token bodies must never be logged. The release gate requires rollback
validation, mixed-version API coverage, and a security review of key rotation and
revocation behavior.

Repository evidence is frozen in repository_inventory.json and test_history.jsonl.
The release team approved this rehearsal in approval.json.
