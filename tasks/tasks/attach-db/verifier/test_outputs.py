from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

try:
    import duckdb
except ImportError:  # Authoring-only fallback; DuckDB is required in the task image.
    duckdb = None


ROOT = Path(os.environ.get("TASK_ROOT", "/root")).resolve()
DATA = ROOT / "data"
OUT = ROOT / "results"
TARGET_PATH = "/root/data/project/support_ops.duckdb"
REFERENCE_PATH = "/root/data/project/reference/customer_history.duckdb"
TARGET_ALIAS = "support_ops_snapshot"


def first(mapping: dict, aliases: tuple[str, ...]):
    for key in aliases:
        if key in mapping:
            return mapping[key]
    return None


def normalize_identifier(value) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'", "`"}:
        text = text[1:-1]
    return text.strip().lower()


def normalize_type(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().upper())
    aliases = {
        "INT": "INTEGER",
        "INT4": "INTEGER",
        "INT8": "BIGINT",
        "STRING": "VARCHAR",
        "TEXT": "VARCHAR",
        "DATETIME": "TIMESTAMP",
        "BOOL": "BOOLEAN",
    }
    return aliases.get(text, text)


def load_report_raw() -> dict:
    path = OUT / "attach_report.json"
    assert path.is_file(), "attach_report.json is missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"attach_report.json is not readable JSON: {exc}") from exc
    assert isinstance(payload, dict), "attach_report.json must contain a JSON object"
    return payload


def normalize_report() -> dict:
    payload = load_report_raw()
    identity = payload.get("database") if isinstance(payload.get("database"), dict) else payload
    path = first(identity, ("database_path", "resolved_path", "resolved_source", "source_path", "path", "source"))
    alias = first(identity, ("alias", "database_alias", "name"))
    raw_tables = first(payload, ("tables", "table_overview", "schema", "relations"))
    if isinstance(raw_tables, dict):
        table_rows = []
        for name, details in raw_tables.items():
            if isinstance(details, dict):
                table_rows.append({"name": name, **details})
            else:
                table_rows.append({"name": name, "row_count": details})
    elif isinstance(raw_tables, list):
        table_rows = raw_tables
    else:
        raise AssertionError("report does not expose a recognizable table collection")

    tables = {}
    for item in table_rows:
        if not isinstance(item, dict):
            raise AssertionError("each reported table must be an object or keyed mapping")
        name = normalize_identifier(first(item, ("name", "table_name", "table")))
        if not name:
            raise AssertionError("a reported table is missing its name")
        if name in tables:
            raise AssertionError(f"table {name} is reported more than once")
        raw_columns = first(item, ("columns", "column_definitions", "fields"))
        if not isinstance(raw_columns, list):
            raise AssertionError(f"table {name} has no recognizable column list")
        columns = []
        for column in raw_columns:
            if isinstance(column, dict):
                column_name = first(column, ("name", "column_name", "field"))
                column_type = first(column, ("type", "data_type", "column_type"))
            elif isinstance(column, (list, tuple)) and len(column) >= 2:
                column_name, column_type = column[0], column[1]
            elif isinstance(column, str) and ":" in column:
                column_name, column_type = column.split(":", 1)
            else:
                raise AssertionError(f"table {name} contains an unusable column definition")
            columns.append((normalize_identifier(column_name), normalize_type(column_type)))
        row_count = first(item, ("row_count", "rows", "count", "estimated_size"))
        if isinstance(row_count, str) and row_count.strip().isdigit():
            row_count = int(row_count.strip())
        tables[name] = {"row_count": row_count, "columns": columns}
    return {
        "path": str(path or "").strip(),
        "alias": normalize_identifier(alias),
        "tables": tables,
    }


def expected_schema() -> dict:
    database = DATA / "project" / "support_ops.duckdb"
    if duckdb is not None and database.is_file():
        connection = duckdb.connect(str(database), read_only=True)
        try:
            names = [
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM duckdb_tables() ORDER BY table_name"
                ).fetchall()
            ]
            tables = {}
            for name in names:
                quoted = '"' + name.replace('"', '""') + '"'
                columns = [
                    (normalize_identifier(row[0]), normalize_type(row[1]))
                    for row in connection.execute(f"DESCRIBE {quoted}").fetchall()
                ]
                count = connection.execute(f"SELECT count(*) FROM {quoted}").fetchone()[0]
                tables[normalize_identifier(name)] = {"columns": columns, "row_count": count}
            return {"path": TARGET_PATH, "alias": TARGET_ALIAS, "tables": tables}
        finally:
            connection.close()

    contract_path = os.environ.get("TASK_EXPECTED_SCHEMA")
    if not contract_path:
        raise AssertionError("DuckDB fixture is unavailable to the verifier")
    payload = json.loads(Path(contract_path).resolve().read_text(encoding="utf-8"))
    return {
        "path": payload["database_path"],
        "alias": payload["alias"],
        "tables": {
            normalize_identifier(table["name"]): {
                "columns": [(normalize_identifier(col[0]), normalize_type(col[1])) for col in table["columns"]],
                "row_count": table["row_count"],
            }
            for table in payload["tables"]
        },
    }


def state_text() -> str:
    path = OUT / "state.sql"
    assert path.is_file(), "state.sql is missing"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(f"state.sql is unreadable: {exc}") from exc
    assert text.strip(), "state.sql is empty"
    return text


def normalized_sql(text: str) -> str:
    without_comments = re.sub(r"--[^\n]*", " ", text)
    return re.sub(r"\s+", " ", without_comments).strip().lower()


def attachment_rows(text: str) -> list[dict]:
    pattern = re.compile(
        r"\battach(?:\s+if\s+not\s+exists)?\s+'((?:''|[^'])+)'\s+as\s+((?:\"(?:\"\"|[^\"])+\")|(?:[a-zA-Z_][\w$]*))\s*(?:\(([^;)]*)\))?\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    rows = []
    for match in pattern.finditer(text):
        rows.append(
            {
                "path": match.group(1).replace("''", "'"),
                "alias": normalize_identifier(match.group(2).replace('""', '"')),
                "options": (match.group(3) or "").lower(),
            }
        )
    return rows


def test_state_preserves_shared_setup():
    """The staged state must retain the project's existing reusable definitions."""
    text = state_text()
    compact = normalized_sql(text)
    assert re.search(r"\bset\s+timezone\s*=\s*'utc'\s*;", compact), "UTC project setting was discarded"
    assert re.search(r"\bcreate\s+or\s+replace\s+macro\s+safe_ratio\s*\(", compact), "safe_ratio macro was discarded"
    assert "denominator = 0 then null" in compact, "safe_ratio zero-denominator behavior changed"
    reference = [row for row in attachment_rows(text) if row["path"] == REFERENCE_PATH]
    assert len(reference) == 1, "the historical customer database attachment was lost or duplicated"
    assert reference[0]["alias"] == "support_ops", "the historical attachment alias changed"
    assert "read_only" in reference[0]["options"] or "read only" in reference[0]["options"], "the historical attachment is no longer read-only"

    if duckdb is not None and (DATA / "project" / "reference" / "customer_history.duckdb").is_file():
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(text)
            count = connection.execute("SELECT count(*) FROM support_ops.customer_tiers").fetchone()[0]
            assert count == 72, "the preserved historical attachment is not queryable"
        finally:
            connection.close()


def test_state_initializes_target_read_only_and_active():
    """The saved state must reproduce the intended attachment and selected database."""
    text = state_text()
    compact = normalized_sql(text)
    target = [row for row in attachment_rows(text) if row["path"] == TARGET_PATH]
    assert len(target) == 1, "the support snapshot must be attached exactly once"
    assert target[0]["alias"] == TARGET_ALIAS, "the alias collision was not resolved as requested"
    assert "read_only" in target[0]["options"] or "read only" in target[0]["options"], "the support snapshot is not declared read-only"
    assert re.search(r"\buse\s+(?:\"?support_ops_snapshot\"?)\s*;", compact), "the snapshot is not selected for follow-up queries"
    assert not re.search(r"\b(drop|delete|update|insert|truncate)\b", compact), "the reusable init state contains a destructive data command"

    report = normalize_report()
    assert report["path"] == TARGET_PATH, "report and saved state identify different source databases"
    assert report["alias"] == TARGET_ALIAS, "report and saved state identify different aliases"

    if duckdb is not None and (DATA / "project" / "support_ops.duckdb").is_file():
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(text)
            assert connection.execute("SELECT current_database()").fetchone()[0] == TARGET_ALIAS
            assert connection.execute("SELECT count(*) FROM tickets").fetchone()[0] == 288
            with pytest.raises(Exception):
                connection.execute(f"CREATE TABLE {TARGET_ALIAS}.__write_probe(value INTEGER)")
        finally:
            connection.close()


def test_report_identity_and_table_scope():
    """The handoff must identify the snapshot and cover every physical table once."""
    actual = normalize_report()
    expected = expected_schema()
    assert actual["path"] == expected["path"], "report does not use the resolved absolute snapshot path"
    assert actual["alias"] == expected["alias"], "report does not record the requested collision-free alias"
    assert set(actual["tables"]) == set(expected["tables"]), "report omits a physical table or invents one"
    assert "import_rejects" in actual["tables"], "the empty import_rejects table must remain visible in the handoff"


def test_report_row_counts():
    """Every reported table count must equal the frozen snapshot count."""
    actual = normalize_report()["tables"]
    expected = expected_schema()["tables"]
    mismatches = {
        name: (actual.get(name, {}).get("row_count"), details["row_count"])
        for name, details in expected.items()
        if actual.get(name, {}).get("row_count") != details["row_count"]
    }
    assert not mismatches, f"row counts differ from the snapshot: {mismatches}"


def test_report_column_definitions():
    """Column names, types, and order must match each table definition."""
    actual = normalize_report()["tables"]
    expected = expected_schema()["tables"]
    mismatches = {
        name: {"actual": actual.get(name, {}).get("columns"), "expected": details["columns"]}
        for name, details in expected.items()
        if actual.get(name, {}).get("columns") != details["columns"]
    }
    assert not mismatches, f"column definitions differ from the snapshot: {mismatches}"
