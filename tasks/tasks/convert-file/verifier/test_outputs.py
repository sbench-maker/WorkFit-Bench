from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import unquote

import pyarrow as pa
import pyarrow.parquet as pq


SOURCE = Path("/root/data/campaign_events.jsonl")
OUTPUT = Path("/root/results/campaign_events.parquet")
SOURCE_COLUMNS = (
    "event_id",
    "campaign_id",
    "campaign_name",
    "occurred_at",
    "campaign_month",
    "channel",
    "event_type",
    "contact_id",
    "revenue_usd",
    "is_test",
    "landing_page",
    "notes",
    "touch_count",
)
STRING_COLUMNS = {
    "event_id",
    "campaign_id",
    "campaign_name",
    "campaign_month",
    "channel",
    "event_type",
    "contact_id",
    "landing_page",
    "notes",
}


def _parquet_files() -> list[Path]:
    if OUTPUT.is_file():
        return [OUTPUT]
    if OUTPUT.is_dir():
        return sorted(path for path in OUTPUT.rglob("*") if path.is_file() and path.suffix.lower() in {".parquet", ".pq"})
    return []


def _source_rows() -> list[dict]:
    return [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _month_from_path(path: Path) -> str | None:
    if not OUTPUT.is_dir():
        return None
    expected = {row["campaign_month"] for row in _source_rows()}
    for part in path.relative_to(OUTPUT).parts[:-1]:
        decoded = unquote(part)
        if decoded.startswith("campaign_month="):
            return decoded.split("=", 1)[1]
        if decoded in expected:
            return decoded
    return None


def _physical_rows() -> tuple[list[dict], dict[str, set[pa.DataType]]]:
    rows: list[dict] = []
    types: dict[str, set[pa.DataType]] = {}
    for path in _parquet_files():
        table = pq.ParquetFile(path).read()
        month = _month_from_path(path)
        for field in table.schema:
            types.setdefault(field.name, set()).add(field.type)
        if month is not None and "campaign_month" not in table.column_names:
            table = table.append_column("campaign_month", pa.array([month] * table.num_rows, type=pa.string()))
            types.setdefault("campaign_month", set()).add(pa.string())
        for row in table.to_pylist():
            if month is not None and row.get("campaign_month") is None:
                row["campaign_month"] = month
            rows.append(row)
    return rows, types


def _canonical_timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_row(row: dict) -> tuple:
    missing = [column for column in SOURCE_COLUMNS if column not in row]
    assert not missing, f"converted records are missing source columns: {missing}"
    revenue = row["revenue_usd"]
    normalized_revenue = None if revenue is None else str(Decimal(str(revenue)).quantize(Decimal("0.01")))
    return (
        str(row["event_id"]),
        None if row["campaign_id"] is None else str(row["campaign_id"]),
        None if row["campaign_name"] is None else str(row["campaign_name"]),
        _canonical_timestamp(row["occurred_at"]),
        None if row["campaign_month"] is None else str(row["campaign_month"]),
        None if row["channel"] is None else str(row["channel"]),
        None if row["event_type"] is None else str(row["event_type"]),
        None if row["contact_id"] is None else str(row["contact_id"]),
        normalized_revenue,
        None if row["is_test"] is None else bool(row["is_test"]),
        None if row["landing_page"] is None else str(row["landing_page"]),
        None if row["notes"] is None else str(row["notes"]),
        None if row["touch_count"] is None else int(row["touch_count"]),
    )


def _is_string_like(data_type: pa.DataType) -> bool:
    if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
        return True
    return pa.types.is_dictionary(data_type) and _is_string_like(data_type.value_type)


def test_record_fidelity():
    """The complete semantic row multiset equals the JSONL source."""
    actual_rows, _ = _physical_rows()
    expected_rows = _source_rows()
    assert len(actual_rows) == len(expected_rows), (
        f"converted row count is {len(actual_rows)}, expected {len(expected_rows)}; "
        "missing or duplicated events would distort attribution"
    )
    actual = Counter(_canonical_row(row) for row in actual_rows)
    expected = Counter(_canonical_row(row) for row in expected_rows)
    assert actual == expected, "one or more converted records changed, disappeared, or were duplicated"


def test_schema_preservation():
    """Column membership and logical type families remain usable downstream."""
    _, types = _physical_rows()
    assert set(types) == set(SOURCE_COLUMNS), (
        f"converted columns are {sorted(types)}, expected exactly {sorted(SOURCE_COLUMNS)}"
    )
    for column in STRING_COLUMNS:
        assert all(_is_string_like(kind) for kind in types[column]), f"{column} is not stored as text"
    assert all(pa.types.is_boolean(kind) for kind in types["is_test"]), "is_test is not stored as boolean"
    assert all(pa.types.is_integer(kind) for kind in types["touch_count"]), "touch_count is not stored as an integer"
    assert all(pa.types.is_floating(kind) or pa.types.is_decimal(kind) for kind in types["revenue_usd"]), (
        "revenue_usd is not stored as a numeric field"
    )
    assert all(pa.types.is_timestamp(kind) or _is_string_like(kind) for kind in types["occurred_at"]), (
        "occurred_at is neither a timestamp nor its lossless text representation"
    )


def test_month_partitioning():
    """All months have physical partitions and every file belongs to one month."""
    assert OUTPUT.is_dir(), "a month-partitioned dataset must be a directory containing partition files"
    expected_months = {row["campaign_month"] for row in _source_rows()}
    observed_months: set[str] = set()
    for path in _parquet_files():
        partition_month = _month_from_path(path)
        assert partition_month is not None, f"{path.relative_to(OUTPUT)} is not inside a campaign_month partition"
        observed_months.add(partition_month)
        table = pq.ParquetFile(path).read()
        if "campaign_month" in table.column_names:
            stored_months = {str(value) for value in table["campaign_month"].to_pylist() if value is not None}
            assert stored_months <= {partition_month}, (
                f"{path.relative_to(OUTPUT)} contains rows for {sorted(stored_months)} but is in {partition_month}"
            )
    assert observed_months == expected_months, (
        f"month partitions are {sorted(observed_months)}, expected {sorted(expected_months)}"
    )


def test_zstd_compression():
    """Every populated Parquet column chunk records the requested codec."""
    files = _parquet_files()
    assert files, "no Parquet files are available for compression inspection"
    codecs: set[str] = set()
    for path in files:
        metadata = pq.ParquetFile(path).metadata
        for row_group_index in range(metadata.num_row_groups):
            row_group = metadata.row_group(row_group_index)
            for column_index in range(row_group.num_columns):
                codecs.add(str(row_group.column(column_index).compression).upper())
    assert codecs == {"ZSTD"}, f"found Parquet compression codecs {sorted(codecs)}, expected only ZSTD"
