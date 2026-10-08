# FulfilFlow data-layer brief

All names and records in this fixture are fictional. FulfilFlow is a multi-tenant B2B order-fulfilment service. The current service stores each order as one mutable JSON document. The next release will split checkout, warehouse picking, shipment tracking, support, and outbound integration into separate workers while retaining one transactional source of truth.

## Core domain and invariants

- A tenant is routed to exactly one home region (`eu`, `us`, or `apac`). Transactional rows for that tenant must remain in that region. Operators may support several tenants, but application database roles must never read another tenant's rows.
- Tenant IDs are supplied by the control plane. Business identifiers such as `external_order_ref`, SKU, and provider webhook IDs may repeat across tenants. `external_order_ref` is unique only within a tenant.
- An order belongs to one tenant and one customer. A customer may later be anonymized, but seven years of order totals and line-item descriptions, SKUs, quantities, tax, discounts, and captured unit prices must remain auditable. Product edits must not rewrite historical lines.
- Every money value is an integer number of minor currency units. An order has one ISO currency. A line total is quantity times captured unit price less line discount plus line tax; the order total reconciles to its lines plus order-level shipping, tax, and discount adjustments.
- An order starts as `pending`. Allowed forward transitions are `pending -> confirmed -> allocating -> partially_shipped -> shipped -> completed`; `pending`, `confirmed`, or `allocating` may transition to `cancelled`. Duplicate or out-of-order status messages must not regress the current state. The full status timeline is append-only.
- Stock is owned by `(tenant, warehouse, product)`. Reserving inventory and confirming the order must be atomic. Available stock may never be negative. A line may be split across warehouses. Reservations are `active`, `consumed`, `released`, or `expired`; retries must not create a second active reservation for the same order line and warehouse.
- A shipment can contain quantities from several lines and an order can have several shipments. A carrier tracking number is unique within a carrier, not globally.
- Inbound provider events are at-least-once and may arrive out of order. `(tenant, provider, provider_event_id)` identifies a logical delivery and must be idempotent for at least 120 days. Failed processing is retried without losing the original payload hash or first-received timestamp.
- Committed order and shipment changes are published through an outbox. A worker may claim a row more than once, but downstream delivery uses the outbox event ID for deduplication.
- Customer contact details are restricted data. They may be anonymized after 30 days following completion unless a legal hold applies. Order financial snapshots and status history remain. Audit records must identify tenant, actor, action, subject, and timestamp without copying contact details.

## Operational requirements

- PostgreSQL 16 is the required system of record. Optional supporting stores are allowed only for rebuildable caches, search, or analytics; they cannot own order or inventory truth.
- Service SLO is 99.95%. In-region node loss should fail over automatically. Region loss targets RPO at most 60 seconds and RTO at most 15 minutes. Cross-region replicas must not violate tenant residency.
- Checkout, inventory reservation, webhook deduplication, and outbox insertion require strong consistency. Customer history and warehouse queues can read a replica with at most 2 seconds of lag. Analytics may lag by 10 minutes and must not run expensive scans on the OLTP primary.
- Order and financial history is retained for seven years. Status and audit events are queried frequently for 90 days, infrequently afterward, and retained for seven years. Processed webhook bodies can be removed after 120 days, while compact deduplication keys must remain through that window. Legal holds override deletion.
- Peak write bursts last 20 minutes. Traffic is skewed: the largest 12 tenants produce about 38% of writes, and the largest tenant produces 6%. A design must avoid a single monotonic-ID or one-tenant hotspot.
- Schema changes must be backward compatible with two concurrently deployed application versions. The migration cannot pause checkout for more than 30 seconds. Source and target reconciliation, rollback triggers, and a way to preserve writes during rollback are required.

## Files in this directory

- `current_schema.sql`: simplified legacy PostgreSQL schema.
- `tenant_inventory.csv`: tenant scale, residency, migration blackout, deletion backlog, and legal-hold counts.
- `workload.csv`: deterministic two-week workload sample joined to tenants by `tenant_id`.
- `capacity_targets.json`: fixed current and 24-month scale/SLO targets.
- `generation_notes.json`: construction metadata; it does not contain expected answers.
