# RFC-27: Regional invoice ledger rollout

## Goal
Split invoice accounting by jurisdiction without interrupting existing billing, then migrate historical entries and roll out behind guarded flags.

## Delivery constraints
Work units are the atomic ownership and landing boundary. Dependencies are mandatory, while units with no dependency may proceed concurrently only when their planned files do not overlap. Migration and rollout work can affect live accounting and require explicit human control points.

## Work units
### WU-01 — Version invoice contract
Dependencies: none. Complexity: 4. Blast radius: medium. Reversible: true.
Planned files: packages/contracts/invoice.ts, packages/contracts/version.ts.
Acceptance references: AC-001, AC-002, AC-003.

### WU-02 — Introduce regional ledger model
Dependencies: WU-01. Complexity: 6. Blast radius: high. Reversible: true.
Planned files: services/ledger/model.ts, services/ledger/repository.ts, migrations/index.ts.
Acceptance references: AC-004, AC-005, AC-006.

### WU-03 — Add jurisdiction tax engine
Dependencies: WU-01. Complexity: 6. Blast radius: high. Reversible: true.
Planned files: services/tax/calculator.ts, services/tax/rules.ts, packages/contracts/invoice.ts.
Acceptance references: AC-007, AC-008, AC-009.

### WU-04 — Build ledger migration runner
Dependencies: WU-02. Complexity: 9. Blast radius: critical. Reversible: false.
Planned files: migrations/index.ts, migrations/regional_ledger.ts, scripts/migrate-ledger.ts.
Acceptance references: AC-010, AC-011, AC-012.

### WU-05 — Expose regional invoice API
Dependencies: WU-02|WU-03. Complexity: 7. Blast radius: high. Reversible: true.
Planned files: services/api/invoice.ts, services/api/routes.ts, packages/contracts/invoice.ts.
Acceptance references: AC-013, AC-014, AC-015.

### WU-06 — Create historical backfill worker
Dependencies: WU-04. Complexity: 7. Blast radius: high. Reversible: false.
Planned files: workers/backfill.ts, workers/checkpoint.ts, migrations/index.ts.
Acceptance references: AC-016, AC-017, AC-018.

### WU-07 — Update invoice administration UI
Dependencies: WU-05. Complexity: 3. Blast radius: medium. Reversible: true.
Planned files: web/admin/invoices.tsx, web/admin/invoice-client.ts, services/api/invoice.ts.
Acceptance references: AC-019, AC-020, AC-021.

### WU-08 — Add billing observability
Dependencies: WU-05|WU-11. Complexity: 4. Blast radius: medium. Reversible: true.
Planned files: ops/dashboards/billing.json, ops/alerts/billing.yaml, services/api/invoice.ts.
Acceptance references: AC-022, AC-023, AC-024.

### WU-09 — Implement guarded regional rollout
Dependencies: WU-06|WU-08|WU-12. Complexity: 8. Blast radius: critical. Reversible: true.
Planned files: config/rollout.yaml, services/api/feature-flags.ts, workers/backfill.ts.
Acceptance references: AC-025, AC-026, AC-027.

### WU-10 — Publish operator runbook
Dependencies: WU-09. Complexity: 2. Blast radius: low. Reversible: true.
Planned files: docs/regional-ledger-runbook.md, config/rollout.yaml.
Acceptance references: AC-028, AC-029, AC-030.

### WU-11 — Expand invoice fixture harness
Dependencies: WU-01. Complexity: 3. Blast radius: low. Reversible: true.
Planned files: tests/fixtures/invoices.json, tests/helpers/invoice-factory.ts, packages/contracts/invoice.ts.
Acceptance references: AC-031, AC-032, AC-033.

### WU-12 — Establish performance baseline
Dependencies: none. Complexity: 3. Blast radius: low. Reversible: true.
Planned files: benchmarks/invoice-api.js, benchmarks/ledger-query.js.
Acceptance references: AC-034, AC-035, AC-036.
