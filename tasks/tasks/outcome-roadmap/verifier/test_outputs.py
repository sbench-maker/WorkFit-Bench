from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest


OUTPUT = Path("/root/results/Outcome-Roadmap-2027.md")
ROADMAP = Path("/root/data/roadmap_items.csv")


def _read_output() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _source_items() -> list[dict[str, str]]:
    with ROADMAP.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _quarter_token(value: str) -> str:
    match = re.search(r"\bQ\s*([1-4])\b", value, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"no quarter token in {value!r}")
    return f"q{match.group(1)}"


def _heading_quarter_positions(text: str) -> list[tuple[int, str]]:
    positions: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        heading_like = stripped.startswith("#") or (
            not re.search(r"FN-\d{3}", stripped, re.IGNORECASE)
            and bool(re.search(r"\b(?:quarter|planning\s+window|phase|period|roadmap)\b", stripped, re.IGNORECASE))
        )
        match = re.search(r"\bQ\s*([1-4])\b", stripped, flags=re.IGNORECASE)
        if heading_like and match:
            positions.append((offset, f"q{match.group(1)}"))
        offset += len(line)
    return positions


def _occurrence_has_quarter(text: str, initiative_id: str, expected_quarter: str) -> bool:
    id_pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(initiative_id)}(?![A-Z0-9])", re.IGNORECASE)
    quarter_pattern = re.compile(rf"\bQ\s*{expected_quarter[-1]}\b", re.IGNORECASE)
    headings = _heading_quarter_positions(text)
    for match in id_pattern.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end]
        if quarter_pattern.search(line):
            return True
        preceding = [quarter for position, quarter in headings if position < match.start()]
        if preceding and preceding[-1] == expected_quarter:
            return True
    return False


def test_artifact_is_usable():
    """The requested Markdown roadmap exists and contains enough content for the planning decision."""
    text = _read_output()
    assert text, "Outcome-Roadmap-2027.md is missing, empty, or not UTF-8 readable"
    assert len(re.findall(r"\b[\w'-]+\b", text)) >= 250, (
        "the roadmap is too thin to carry outcomes, measures, traceability, and decision notes"
    )
    assert re.search(r"outcome", text, flags=re.IGNORECASE), (
        "the artifact does not identify outcome-focused roadmap content"
    )


def test_four_quarter_windows_present():
    """All four planning windows remain visible without requiring a particular heading style."""
    text = _read_output()
    if not text:
        pytest.skip("the root artifact failure is scored once under artifact structure")
    found = {f"q{number}" for number in re.findall(r"\bQ\s*([1-4])\b", text, flags=re.IGNORECASE)}
    assert found == {"q1", "q2", "q3", "q4"}, (
        f"expected visible Q1-Q4 planning windows, found {sorted(found)}"
    )


def test_all_initiative_ids_are_traceable():
    """Every original initiative can be found in the transformed roadmap."""
    text = _read_output()
    if not text:
        pytest.skip("the root artifact failure is scored once under artifact structure")
    expected = {row["initiative_id"].upper() for row in _source_items()}
    observed = {token.upper() for token in re.findall(r"\bFN-\d{3}\b", text, flags=re.IGNORECASE)}
    missing = sorted(expected - observed)
    assert not missing, (
        f"source initiatives are not traceable in the roadmap: {missing}; teams could lose work during regrouping"
    )


@pytest.mark.parametrize(
    "initiative_id,expected_quarter",
    [(row["initiative_id"], _quarter_token(row["quarter"])) for row in _source_items()],
)
def test_initiatives_remain_associated_with_original_quarter(initiative_id: str, expected_quarter: str):
    """Each retained ID stays tied to its original planning window, including table-based appendices."""
    text = _read_output()
    if not text:
        pytest.skip("the root artifact failure is scored once under artifact structure")
    assert _occurrence_has_quarter(text, initiative_id, expected_quarter), (
        f"{initiative_id} is not associated with {expected_quarter.upper()}; the quarter-by-quarter trace is misleading"
    )
