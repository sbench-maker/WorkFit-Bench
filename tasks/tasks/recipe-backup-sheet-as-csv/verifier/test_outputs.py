from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import pytest


OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/recipe_catalog_backup.csv"))
DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


def expected_rows() -> list[list[str]]:
    snapshot = json.loads((DATA_DIR / "sheet_cells.json").read_text(encoding="utf-8"))
    active_id = snapshot["activeSheetId"]
    active = [sheet for sheet in snapshot["sheets"] if sheet["properties"]["sheetId"] == active_id]
    assert len(active) == 1, "fixture must identify exactly one active sheet"
    assert active[0]["properties"]["title"] == "Recipe Catalog", "fixture active sheet unexpectedly changed"
    return active[0]["values"]


def canonical_cell(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def load_submission() -> tuple[list[list[str]] | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"missing requested CSV backup: {OUTPUT}"
    try:
        raw = OUTPUT.read_bytes()
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"backup is not a readable UTF-8 CSV: {exc}"
    if b"\x00" in raw:
        return None, "backup contains NUL bytes and is not interoperable CSV text"
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as exc:
        return None, f"backup is malformed CSV: {exc}"
    if not rows:
        return None, "backup is empty"
    widths = {len(row) for row in rows}
    if len(widths) != 1 or next(iter(widths)) == 0:
        return None, f"backup is not a rectangular CSV table; parsed row widths are {sorted(widths)}"
    return rows, None


def require_parseable() -> list[list[str]]:
    rows, error = load_submission()
    if error is not None:
        pytest.skip(f"root CSV readability problem already reported by test_csv_artifact_usability: {error}")
    assert rows is not None
    return rows


def test_csv_artifact_usability():
    """The requested backup exists and is valid rectangular UTF-8 CSV."""
    rows, error = load_submission()
    assert error is None, error
    assert rows is not None
    assert len(rows) >= 2, "backup contains a header but no recipe records"


def test_header_fidelity():
    """The exported schema and column order match the active sheet header."""
    rows = require_parseable()
    expected = expected_rows()
    actual_header = [canonical_cell(cell) for cell in rows[0]]
    assert actual_header == expected[0], (
        f"CSV header is {actual_header!r}, expected {expected[0]!r}; a changed or reordered schema "
        "would make the backup unsafe to re-import"
    )


def test_recipe_record_coverage_and_order():
    """Every active-sheet recipe appears exactly once and in source row order."""
    rows = require_parseable()
    expected = expected_rows()
    actual_codes = [canonical_cell(row[0]) for row in rows[1:]]
    expected_codes = [row[0] for row in expected[1:]]
    assert actual_codes == expected_codes, (
        "recipe-code sequence differs from the active sheet; records are missing, duplicated, "
        "taken from another tab, or reordered"
    )


def test_recipe_cell_content_fidelity():
    """All non-key cells round-trip exactly, including blank and quoted/multiline text."""
    rows = require_parseable()
    expected = expected_rows()
    expected_width = len(expected[0])
    if any(len(row) != expected_width for row in rows):
        pytest.skip("column-count defect is already localized by header/usability checks")

    expected_by_code = {row[0]: row for row in expected[1:]}
    actual_by_code: dict[str, list[list[str]]] = {}
    for row in rows[1:]:
        actual_by_code.setdefault(canonical_cell(row[0]), []).append(row)

    comparable = sum(len(actual_by_code.get(code, [])) == 1 for code in expected_by_code)
    assert comparable >= int(len(expected_by_code) * 0.9), (
        f"only {comparable} of {len(expected_by_code)} source recipes can be matched for cell comparison; "
        "the backup appears to contain a different sheet or an extensively altered key column"
    )

    mismatches = []
    for code, source_row in expected_by_code.items():
        matches = actual_by_code.get(code, [])
        if len(matches) != 1:
            continue  # Missing/duplicate IDs are scoped to the coverage criterion.
        actual_values = [canonical_cell(cell) for cell in matches[0][1:]]
        expected_values = [canonical_cell(cell) for cell in source_row[1:]]
        if actual_values != expected_values:
            differing_columns = [
                expected[0][index + 1]
                for index, (actual, wanted) in enumerate(zip(actual_values, expected_values))
                if actual != wanted
            ]
            mismatches.append(f"{code} ({', '.join(differing_columns)})")
    assert not mismatches, (
        "cell text changed for " + ", ".join(mismatches[:12])
        + (f" and {len(mismatches) - 12} more" if len(mismatches) > 12 else "")
    )
