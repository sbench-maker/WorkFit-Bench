#!/usr/bin/env python3
"""Build the frozen DuckDB databases from local CSV files during image creation."""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb


HERE = Path(__file__).resolve().parent
PROJECT = HERE / "project"
SOURCE = PROJECT / "source"
TARGET = PROJECT / "support_ops.duckdb"
REFERENCE = PROJECT / "reference" / "customer_history.duckdb"


TABLES = {
    "teams": "team_id INTEGER, team_name VARCHAR, region VARCHAR, active BOOLEAN",
    "agents": "agent_id INTEGER, team_id INTEGER, display_name VARCHAR, hired_on DATE, status VARCHAR",
    "sla_policies": "policy_id INTEGER, priority VARCHAR, first_response_minutes INTEGER, resolution_minutes INTEGER, business_hours_only BOOLEAN",
    "tickets": "ticket_id BIGINT, customer_id VARCHAR, opened_at TIMESTAMP, closed_at TIMESTAMP, team_id INTEGER, policy_id INTEGER, priority VARCHAR, channel VARCHAR, status VARCHAR, subject VARCHAR, tags VARCHAR",
    "ticket_events": "event_id BIGINT, ticket_id BIGINT, event_at TIMESTAMP, event_type VARCHAR, actor_agent_id INTEGER, detail VARCHAR",
    "satisfaction_surveys": "ticket_id BIGINT, submitted_at TIMESTAMP, score TINYINT, resolved_first_contact BOOLEAN, comment VARCHAR",
    "import_rejects": "batch_id VARCHAR, source_row INTEGER, reason VARCHAR, captured_at TIMESTAMP",
}


def load_csv(connection: duckdb.DuckDBPyConnection, table: str) -> None:
    path = SOURCE / f"{table}.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    if not rows:
        return
    placeholders = ", ".join("?" for _ in header)
    normalized = [[None if value == "" else value for value in row] for row in rows]
    connection.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', normalized)


def build_target() -> None:
    TARGET.unlink(missing_ok=True)
    connection = duckdb.connect(str(TARGET))
    try:
        for table, definition in TABLES.items():
            connection.execute(f'CREATE TABLE "{table}" ({definition})')
            load_csv(connection, table)
        connection.execute("CREATE INDEX ticket_events_ticket_idx ON ticket_events(ticket_id)")
        connection.execute("CHECKPOINT")
    finally:
        connection.close()


def build_reference() -> None:
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.unlink(missing_ok=True)
    connection = duckdb.connect(str(REFERENCE))
    try:
        connection.execute("CREATE TABLE customer_tiers(customer_id VARCHAR, tier VARCHAR, renewed_on DATE)")
        rows = [
            (f"CUST-{idx:04d}", ("standard", "plus", "priority")[idx % 3], f"2026-{((idx - 1) % 6) + 1:02d}-{((idx * 3) % 27) + 1:02d}")
            for idx in range(1, 73)
        ]
        connection.executemany("INSERT INTO customer_tiers VALUES (?, ?, ?)", rows)
        connection.execute("CREATE TABLE service_plans(plan_code VARCHAR, monthly_fee DECIMAL(10,2))")
        connection.executemany("INSERT INTO service_plans VALUES (?, ?)", [("STD", 49), ("PLUS", 99), ("PRIO", 199), ("TRIAL", 0)])
        connection.execute("CHECKPOINT")
    finally:
        connection.close()


if __name__ == "__main__":
    build_target()
    build_reference()
