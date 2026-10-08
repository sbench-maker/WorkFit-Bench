from __future__ import annotations

import csv
import os
import re
from pathlib import Path

import pytest


RESULTS = Path(os.environ.get("RESULTS_DIR", "/root/results"))
DATA = Path(os.environ.get("DATA_DIR", "/root/data"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _norm(text: str) -> str:
    text = re.sub(r"--[^\n]*", " ", text.lower())
    text = text.replace('"', "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _balanced_parenthesized(text: str, start: int) -> tuple[str, int]:
    depth = 0
    quote = None
    i = start
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    i += 2
                    continue
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    raise ValueError("unbalanced CREATE TABLE parentheses")


def _tables(sql: str) -> dict[str, str]:
    clean = re.sub(r"--[^\n]*", " ", sql)
    pattern = re.compile(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\".]+)\s*\(", re.I
    )
    found: dict[str, str] = {}
    for match in pattern.finditer(clean):
        name = match.group(1).replace('"', "").split(".")[-1].lower()
        body, end = _balanced_parenthesized(clean, match.end() - 1)
        tail = clean[end : clean.find(";", end) if clean.find(";", end) >= 0 else len(clean)]
        found[name] = _norm(body + " " + tail)
    return found


def _indexes(sql: str) -> list[str]:
    return [
        _norm(match.group(0))
        for match in re.finditer(
            r"create\s+(?:unique\s+)?index\b.*?;", sql, flags=re.I | re.S
        )
    ]


ALIASES = {
    "customers": ("customers", "customer", "buyers", "buyer_accounts"),
    "products": ("products", "product", "catalog_items", "skus"),
    "warehouses": ("warehouses", "warehouse", "fulfillment_centers"),
    "inventory": ("inventory_stock", "inventory", "stock_balances", "warehouse_stock"),
    "orders": ("orders", "sales_orders", "customer_orders"),
    "lines": ("order_lines", "sales_order_lines", "line_items"),
    "reservations": ("inventory_reservations", "stock_reservations", "reservations"),
    "shipments": ("shipments", "fulfillments", "parcel_shipments"),
    "shipment_items": ("shipment_items", "shipment_lines", "fulfillment_items"),
    "status_events": ("order_status_events", "order_events", "status_history"),
    "webhook_keys": ("webhook_dedup_keys", "webhook_receipts", "inbound_event_keys", "inbox_keys"),
    "webhook_payloads": ("webhook_deliveries", "inbound_events", "webhook_payloads", "inbox_events"),
    "outbox": ("outbox_events", "outbox", "transactional_outbox"),
    "audit": ("audit_events", "audit_log", "audit_records"),
}


def _find_table(tables: dict[str, str], entity: str) -> tuple[str, str] | None:
    aliases = ALIASES[entity]
    for name, body in tables.items():
        if name in aliases:
            return name, body
    for name, body in tables.items():
        if any(alias in name for alias in aliases):
            return name, body
    return None


def _col(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(name)}\b", text) for name in alternatives)


def _has_key_group(body: str, groups: list[tuple[str, ...]]) -> bool:
    """Accept UNIQUE/PK column order and constraint naming differences."""
    for match in re.finditer(r"(?:primary\s+key|unique)\s*\(([^)]*)\)", body):
        columns = match.group(1)
        if all(_col(columns, group) for group in groups):
            return True
    return False


def _tenant_fk_count(sql: str) -> int:
    count = 0
    for match in re.finditer(
        r"foreign\s+key\s*\(([^)]*)\)\s*references\s+[\w.]+\s*\(([^)]*)\)",
        _norm(sql),
    ):
        local_columns, referenced_columns = match.groups()
        tenant_group = ("tenant_id", "organization_id", "account_id")
        if _col(local_columns, tenant_group) and _col(referenced_columns, tenant_group):
            count += 1
    return count


def _schema_bundle() -> tuple[str, str, dict[str, str], list[str]]:
    schema_path = RESULTS / "schema.sql"
    architecture_path = RESULTS / "architecture.md"
    if not schema_path.is_file() or not architecture_path.is_file():
        pytest.skip("requested artifact missing; reported once by artifact usability")
    sql = _read(schema_path)
    architecture = _read(architecture_path)
    try:
        tables = _tables(sql)
    except ValueError as exc:
        pytest.skip(f"schema cannot be normalized: {exc}")
    if not tables:
        pytest.skip("schema contains no normalizable CREATE TABLE statements")
    return sql, architecture, tables, _indexes(sql)


def _body(tables: dict[str, str], entity: str) -> str:
    match = _find_table(tables, entity)
    assert match is not None, f"relational model omits the {entity} domain object"
    return match[1]


def _contains_column_group(indexes: list[str], table_names: tuple[str, ...], groups: list[tuple[str, ...]]) -> bool:
    for idx in indexes:
        if not re.search(r"\bon\s+[\w.]*?(?:" + "|".join(map(re.escape, table_names)) + r")\s*\(", idx):
            continue
        if all(_col(idx, group) for group in groups):
            return True
    return False


@pytest.mark.parametrize(
    "case",
    [
        "domain_coverage",
        "tenant_scoped_keys",
        "financial_history",
        "inventory_safety",
        "status_history",
        "webhook_idempotency",
        "shipment_identity_and_outbox_audit",
    ],
)
def test_relational_integrity(case: str):
    sql, architecture, tables, indexes = _schema_bundle()
    combined = _norm(sql + "\n" + architecture)

    if case == "domain_coverage":
        required = (
            "customers", "products", "warehouses", "inventory", "orders", "lines",
            "reservations", "shipments", "shipment_items", "status_events",
            "webhook_keys", "outbox", "audit",
        )
        missing = [entity for entity in required if _find_table(tables, entity) is None]
        assert not missing, f"target model omits transactional domain objects: {missing}"

    elif case == "tenant_scoped_keys":
        entities = ("customers", "products", "warehouses", "inventory", "orders", "lines", "reservations", "shipments", "status_events", "webhook_keys", "outbox", "audit")
        missing_tenant = [entity for entity in entities if not _col(_body(tables, entity), ("tenant_id", "organization_id", "account_id"))]
        assert not missing_tenant, f"tenant ownership is absent from: {missing_tenant}"
        order_body = _body(tables, "orders")
        assert _has_key_group(
            order_body,
            [("tenant_id", "organization_id", "account_id"), ("external_order_ref", "external_ref", "client_order_id")],
        ), (
            "external order identity is not enforced within tenant scope"
        )
        assert _tenant_fk_count(sql) >= 5, "too few tenant-scoped foreign keys; cross-tenant relationships remain possible"
        shared_isolation = (
            ("row level security" in combined and ("create policy" in combined or "tenant context" in combined))
            or ("security barrier" in combined and "revoke" in combined)
            or ("tenant-scoped role" in combined and ("view" in combined or "privilege" in combined))
        )
        assert shared_isolation or re.search(r"(?:database|schema)\s+per\s+tenant", combined), (
            "the shared model lacks a concrete database-enforced tenant isolation boundary"
        )

    elif case == "financial_history":
        order = _body(tables, "orders")
        line = _body(tables, "lines")
        assert _col(order, ("currency", "currency_code")) and _col(order, ("total_minor", "total_amount_minor", "grand_total_minor")), (
            "orders do not persist currency and auditable minor-unit totals"
        )
        needed = [
            ("quantity", "qty"),
            ("unit_price_minor", "captured_unit_price_minor", "price_minor"),
            ("sku_snapshot", "captured_sku", "sku"),
            ("description_snapshot", "captured_description", "item_description"),
            ("line_total_minor", "total_minor", "extended_amount_minor"),
        ]
        assert all(_col(line, group) for group in needed), "order lines do not retain the required financial/product snapshots"
        arithmetic_guard = (
            ("check" in line and ("quantity *" in line or "* quantity" in line or "qty *" in line))
            or ("generated always" in line and ("quantity *" in line or "qty *" in line))
            or ("trigger" in combined and "line_total" in combined and ("quantity *" in combined or "qty *" in combined))
        )
        assert arithmetic_guard, (
            "line arithmetic is not guarded by a database constraint"
        )

    elif case == "inventory_safety":
        inventory = _body(tables, "inventory")
        reservations = _body(tables, "reservations")
        assert _col(inventory, ("warehouse_id", "fulfillment_center_id")) and _col(inventory, ("product_id", "sku_id")), (
            "stock is not keyed by warehouse and product"
        )
        assert "check" in inventory and _col(inventory, ("reserved_quantity", "reserved_qty")) and _col(inventory, ("on_hand_quantity", "on_hand", "stock_quantity")), (
            "inventory lacks an enforceable nonnegative/reserved-within-on-hand invariant"
        )
        assert all(word in reservations for word in ("active", "consumed", "released", "expired")), (
            "reservation lifecycle cannot represent release, expiry, and consumption"
        )
        active_unique = any(
            "unique index" in idx and "where" in idx and "active" in idx
            and _col(idx, ("order_id",)) and _col(idx, ("line_number", "line_no", "order_line_id"))
            and _col(idx, ("warehouse_id", "fulfillment_center_id"))
            for idx in indexes
        )
        active_unique = active_unique or _has_key_group(
            reservations,
            [("tenant_id", "organization_id", "account_id"), ("order_id",),
             ("line_number", "line_no", "order_line_id"), ("warehouse_id", "fulfillment_center_id")],
        )
        active_unique = active_unique or (
            _col(reservations, ("idempotency_key", "reservation_key", "request_key"))
            and _has_key_group(reservations, [("tenant_id", "organization_id", "account_id"), ("idempotency_key", "reservation_key", "request_key")])
        )
        assert active_unique, "retries can create duplicate active reservations for an order line and warehouse"

    elif case == "status_history":
        events = _body(tables, "status_events")
        order = _body(tables, "orders")
        assert _col(events, ("order_id",)) and _col(events, ("occurred_at", "event_time")) and _col(events, ("status", "new_status")), (
            "status history lacks order, state, or event-time fields"
        )
        assert all(state in order for state in ("pending", "confirmed", "allocating", "cancelled", "completed")), (
            "order status does not constrain the stated lifecycle"
        )
        append_only = "append-only" in combined or "append only" in combined or (
            "before update or delete" in combined and "status" in combined
        )
        progression = "status transition" in combined and ("regression" in combined or "invalid order status" in combined or "out-of-order" in combined)
        assert append_only and progression, "status events are not append-only or current status can regress on out-of-order input"

    elif case == "webhook_idempotency":
        keys = _body(tables, "webhook_keys")
        assert all(_col(keys, group) for group in (("tenant_id", "organization_id", "account_id"), ("provider", "source"), ("provider_event_id", "external_event_id", "event_key"))), (
            "webhook idempotency key does not include tenant, provider, and provider event ID"
        )
        assert _has_key_group(
            keys,
            [("tenant_id", "organization_id", "account_id"), ("provider", "source"), ("provider_event_id", "external_event_id", "event_key")],
        ), (
            "webhook idempotency tuple is not database-enforced"
        )
        assert "120" in combined and ("retain" in combined or "retention" in combined or "interval" in combined), (
            "the 120-day replay/deduplication window is not preserved"
        )

    elif case == "shipment_identity_and_outbox_audit":
        shipments = _body(tables, "shipments")
        outbox = _body(tables, "outbox")
        audit = _body(tables, "audit")
        assert _has_key_group(shipments, [("carrier", "carrier_code"), ("tracking_number", "tracking_no")]), (
            "carrier-scoped tracking identity is not enforced"
        )
        assert all(_col(outbox, group) for group in (("outbox_event_id", "event_id"), ("aggregate_id", "subject_id"), ("payload", "event_payload"), ("published_at", "delivered_at"))), (
            "transactional outbox lacks stable identity, aggregate, payload, or publication state"
        )
        assert all(_col(audit, group) for group in (("tenant_id", "organization_id", "account_id"), ("actor_id", "principal_id"), ("action",), ("subject_id", "resource_id"), ("occurred_at", "event_time"))), (
            "audit history lacks tenant, actor, action, subject, or time"
        )


@pytest.mark.parametrize(
    "case",
    [
        "customer_history",
        "warehouse_queue",
        "stalled_orders",
        "outbox_claim",
        "status_timeline_partition",
        "webhook_payload_lifecycle",
    ],
)
def test_access_and_lifecycle(case: str):
    sql, architecture, tables, indexes = _schema_bundle()
    with (DATA / "workload.csv").open(encoding="utf-8", newline="") as handle:
        operations = {row["operation"] for row in csv.DictReader(handle)}
    all_text = _norm(sql + "\n" + architecture)

    if case == "customer_history":
        assert "customer_order_history" in operations
        assert _contains_column_group(
            indexes, ALIASES["orders"],
            [("tenant_id", "organization_id", "account_id"), ("customer_id", "buyer_id"), ("created_at", "ordered_at"), ("order_id",)],
        ), "no order index supports tenant/customer history with stable recency pagination"

    elif case == "warehouse_queue":
        assert "warehouse_pick_queue" in operations
        assert any(
            re.search(r"\bon\s+[\w.]*?(?:orders|sales_orders|customer_orders)\s*\(", idx)
            and _col(idx, ("tenant_id", "organization_id", "account_id"))
            and _col(idx, ("warehouse_id", "assigned_warehouse_id", "fulfillment_center_id"))
            and _col(idx, ("confirmed_at", "status_changed_at", "created_at"))
            and "where" in idx and "confirmed" in idx and "allocating" in idx
            for idx in indexes
        ), "warehouse pick queue lacks a tenant/warehouse partial index ordered for live work"

    elif case == "stalled_orders":
        assert "stalled_orders" in operations
        assert any(
            re.search(r"\bon\s+[\w.]*?(?:orders|sales_orders|customer_orders)\s*\(", idx)
            and _col(idx, ("tenant_id", "organization_id", "account_id"))
            and _col(idx, ("status_changed_at", "updated_at", "confirmed_at"))
            and "where" in idx and ("confirmed" in idx or "allocating" in idx)
            for idx in indexes
        ), "stalled-order sweep would scan unbounded historical orders"

    elif case == "outbox_claim":
        assert "claim_outbox_batch" in operations
        assert any(
            re.search(r"\bon\s+[\w.]*?(?:outbox_events|outbox|transactional_outbox)\s*\(", idx)
            and _col(idx, ("tenant_id", "organization_id", "account_id"))
            and _col(idx, ("created_at", "available_at"))
            and "where" in idx and ("published_at is null" in idx or "delivered_at is null" in idx)
            for idx in indexes
        ), "outbox workers lack a narrow unpublished-row claim index"

    elif case == "status_timeline_partition":
        assert "order_status_timeline" in operations
        event_match = _find_table(tables, "status_events")
        assert event_match is not None
        name, body = event_match
        planned_time_partitioning = (
            ("partition by range" in body and _col(body, ("occurred_at", "event_time")))
            or (
                any(term in _norm(architecture) for term in ("monthly partition", "monthly range partition", "time-based partition"))
                and any(term in _norm(architecture) for term in ("status event", "status history", "status timeline"))
            )
        )
        assert planned_time_partitioning, (
            "multi-billion status history is not range-partitioned by event time"
        )
        assert _contains_column_group(
            indexes, (name,),
            [("tenant_id", "organization_id", "account_id"), ("order_id",), ("occurred_at", "event_time"), ("event_id",)],
        ), "status timeline lacks a tenant/order/time index with a stable tie-breaker"

    elif case == "webhook_payload_lifecycle":
        assert "expire_webhook_payloads" in operations and "ingest_provider_webhook" in operations
        payload_match = _find_table(tables, "webhook_payloads")
        assert payload_match is not None, "no lifecycle-managed webhook payload table is present"
        _, payload_body = payload_match
        payload_partitioned = "partition by range" in payload_body and _col(payload_body, ("first_received_at", "received_at", "processed_at"))
        alternative = "webhook" in all_text and "120" in all_text and any(term in all_text for term in ("drop partition", "detach partition", "payload purge", "payload partitions"))
        assert payload_partitioned or alternative, "webhook bodies cannot be expired in bounded 120-day lifecycle batches"
        assert "legal hold" in all_text or "legal_hold" in all_text, "lifecycle design does not protect legal-hold records"
