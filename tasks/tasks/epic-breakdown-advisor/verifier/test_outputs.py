from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Optional

import pytest


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "epic_breakdown.md"


def _read_output() -> tuple[str, Optional[str]]:
    if not OUTPUT.is_file():
        return "", f"missing requested artifact: {OUTPUT}"
    try:
        return OUTPUT.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return "", f"cannot read {OUTPUT} as UTF-8 Markdown: {exc}"


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    replacements = {
        "≤": " <= ",
        "≥": " >= ",
        "<": " < ",
        ">": " > ",
        "–": "-",
        "—": "-",
        "_": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[`*#|()[\]{}:,;/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _has_any(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(_normalize(item) in text for item in alternatives)


def _missing(text: str, concepts: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    return [name for name, alternatives in concepts if not _has_any(text, alternatives)]


def _story_estimates(raw: str) -> list[int]:
    estimates: list[int] = []
    for line in raw.splitlines():
        normalized = _normalize(line)
        if not normalized:
            continue
        if any(term in normalized for term in ("epic", "original", "current estimate", "ceiling", "none exceeds", "sprint", "total")):
            continue
        if not re.search(r"\b(?:estimate|effort|size|sizing|points?|sp)\b", normalized):
            continue
        matches = re.findall(r"\b(\d{1,2})\s*(?:story\s*)?(?:points?|pts?|sp)\b", normalized)
        if not matches:
            matches = re.findall(r"\b(?:estimate|effort|size|sizing)\D{0,12}(\d{1,2})\b", normalized)
        estimates.extend(int(value) for value in matches)
    return estimates


SCOPE_CASES = [
    pytest.param(
        "complete basic journey",
        (
            ("basic entry", ("basic form", "simple form", "minimal form")),
            ("standard domestic case", ("standard domestic", "domestic standard")),
            ("automatic authorization", ("automatically authorized", "automatic authorization", "auto-approved", "auto approved")),
            ("pickup", ("pickup", "collection window")),
            ("credit confirmation", ("credit confirmation", "credit confirmed", "credit memo")),
            ("visible closure status", ("visible status", "track status", "status is visible", "visible closure")),
        ),
        id="basic_journey",
    ),
    pytest.param(
        "policy route variations",
        (
            ("high-value manager route", ("high-value", "high value", "manager approval")),
            ("regulated route", ("regulated", "compliance approval")),
            ("specialist carrier", ("specialist carrier", "specialized carrier")),
            ("international route", ("international", "non-domestic", "non domestic")),
            ("customs declaration", ("customs declaration", "customs document")),
        ),
        id="route_variations",
    ),
    pytest.param(
        "entry-method variations",
        (
            ("bulk CSV", ("bulk csv", "csv upload", "upload csv")),
            ("row-level result", ("row-level", "row level", "per-row", "per row")),
            ("drag-and-drop attachments", ("drag-and-drop", "drag and drop")),
            ("attachment preview", ("attachment preview", "preview multiple attachments", "preview each file", "preview thumbnail")),
        ),
        id="entry_methods",
    ),
    pytest.param(
        "operational enhancements",
        (
            ("automatic carrier booking", ("automatic carrier booking", "automatically book", "carrier adapter")),
            ("stage SLA dashboard", ("sla dashboard", "stage sla", "service target")),
            ("peak performance", ("peak response", "peak-load performance", "peak load", "95th percentile", "p95")),
        ),
        id="operations",
    ),
]


POLICY_CASES = [
    pytest.param(
        "value boundary",
        (
            ("USD 500 boundary", ("usd 500", "$500", "500 or less", "above 500", "> 500", "<= 500")),
            ("automatic lower-value route", ("automatically authorized", "automatic authorization", "auto-approved", "auto approved")),
            ("manager approval above boundary", ("manager approval", "manager approves", "procurement manager")),
            ("approval before pickup", ("before pickup", "pickup is blocked before approval", "pickup booking is blocked before approval", "prior to pickup")),
        ),
        id="value_boundary",
    ),
    pytest.param(
        "regulated override",
        (
            ("regulated at any value", ("regulated item at any", "regulated goods at any", "including usd 500 or less", "regardless of value")),
            ("compliance approval", ("compliance approval", "compliance approves")),
            ("override", ("overrides automatic", "override automatic", "are overridden", "compliance override", "not auto-approved", "not automatically approved")),
            ("specialist carrier", ("specialist carrier", "specialized carrier")),
        ),
        id="regulated_override",
    ),
    pytest.param(
        "international customs gate",
        (
            ("non-domestic scope", ("non-domestic", "non domestic", "international return")),
            ("accepted customs declaration", ("accepted customs declaration", "customs declaration is accepted", "validated customs declaration", "complete and valid customs data", "customs cleared")),
            ("before pickup", ("before pickup", "prior to pickup", "pickup booking becomes available")),
        ),
        id="customs_gate",
    ),
    pytest.param(
        "bulk threshold and partial acceptance",
        (
            ("10-line threshold", ("at least 10", "10 or more", ">= 10", "ten or more")),
            ("valid rows accepted", ("valid rows are accepted", "accept valid rows", "valid lines are accepted", "returns are created")),
            ("invalid rows rejected", ("invalid rows remain rejected", "reject invalid rows", "invalid lines remain rejected", "errors are displayed")),
            ("row reasons", ("row-level reason", "row level reason", "per-row reason", "per row reason")),
        ),
        id="bulk_partial_acceptance",
    ),
    pytest.param(
        "carrier eligibility",
        (
            ("authorized standard domestic", ("authorized standard domestic", "standard domestic return")),
            ("automatic booking", ("automatic carrier booking", "automatically book", "carrier adapter")),
            ("regulated manual", ("regulated and international cases remain", "regulated cases remain manual", "regulated remains manually", "regulated or international", "arranged manually")),
            ("international manual", ("regulated and international cases remain", "international cases remain manual", "international remains manually", "regulated or international", "booking remains manual for international")),
        ),
        id="carrier_eligibility",
    ),
    pytest.param(
        "SLA thresholds",
        (
            ("authorization after 24 hours", ("authorization waits beyond 24 hours", "authorization after 24 hours", "24-hour authorization", "24 hour authorization", "authorization pending or granted for 24+ hours")),
            ("pickup after 48 hours", ("pickup-scheduling waits beyond 48 hours", "pickup scheduling after 48 hours", "48-hour pickup", "48 hour pickup", "pickup scheduled for 48+ hours", "for 48+ hours")),
        ),
        id="sla_thresholds",
    ),
    pytest.param(
        "performance target",
        (
            ("200 concurrent sessions", ("200 concurrent", "concurrency of 200")),
            ("95th percentile", ("95th percentile", "p95")),
            ("two seconds", ("2 seconds", "two seconds", "2s")),
        ),
        id="performance_target",
    ),
]


def test_artifact_and_story_usability() -> None:
    raw, error = _read_output()
    assert error is None, error
    normalized = _normalize(raw)
    issues: list[str] = []
    if len(raw.strip()) < 1500:
        issues.append("the plan is too thin for a 35-point, nine-capability epic")
    counts = {
        "persona statements ('As a/an')": len(re.findall(r"(?im)^\s*[-*]?\s*(?:\*\*)?as\s+an?\b", raw)),
        "actions ('I want to')": len(re.findall(r"(?i)\bi\s+want\s+to\b", raw)),
        "outcomes ('so that')": len(re.findall(r"(?i)\bso\s+that\b", raw)),
        "Given criteria": len(re.findall(r"(?im)^\s*[-*]?\s*(?:\*\*)?given\b", raw)),
        "When criteria": len(re.findall(r"(?im)^\s*[-*]?\s*(?:\*\*)?when\b", raw)) + sum(bool(re.search(r"(?i)\bwhen\b", line)) for line in raw.splitlines() if re.match(r"(?i)^\s*[-*]?\s*(?:\*\*)?given\b", line)),
        "Then criteria": len(re.findall(r"(?im)^\s*[-*]?\s*(?:\*\*)?then\b", raw)) + sum(bool(re.search(r"(?i)\bthen\b", line)) for line in raw.splitlines() if re.match(r"(?i)^\s*[-*]?\s*(?:\*\*)?given\b", line)),
    }
    gwt_tables = len(re.findall(r"(?im)^\s*\|[^\n]*\bgiven\b[^\n]*\bwhen\b[^\n]*\bthen\b[^\n]*\|\s*$", raw))
    for label in ("Given criteria", "When criteria", "Then criteria"):
        counts[label] = max(counts[label], gwt_tables)
    for label, count in counts.items():
        if count < 7:
            issues.append(f"only {count} {label}; the breakdown does not expose at least seven complete, testable stories")
    placeholder = re.search(r"(?i)(lorem ipsum|insert .* here|tbd acceptance|\[persona\]|\[action\]|\[outcome\])", raw)
    if placeholder:
        issues.append(f"the artifact still contains an authoring placeholder: {placeholder.group(0)!r}")
    if "ret-410" not in normalized and "supplier return" not in normalized:
        issues.append("the plan is not clearly tied to the supplied RET-410 supplier-returns epic")
    assert not issues, "\n".join(issues)


def test_story_estimates_respect_ceiling() -> None:
    raw, error = _read_output()
    assert error is None, error
    estimates = _story_estimates(raw)
    assert len(estimates) >= 7, (
        f"found only {len(estimates)} story-level point estimates; the requested story set cannot be planned against the supplied sizing ceiling"
    )
    oversized = [value for value in estimates if value > 5]
    assert not oversized, (
        f"story-level estimates exceed the frozen five-point ceiling: {oversized}; these items remain too large for sprint refinement"
    )


@pytest.mark.parametrize(("case_name", "concepts"), SCOPE_CASES)
def test_material_scope_is_accounted_for(
    case_name: str, concepts: tuple[tuple[str, tuple[str, ...]], ...]
) -> None:
    raw, error = _read_output()
    assert error is None, error
    missing = _missing(_normalize(raw), concepts)
    assert not missing, (
        f"{case_name} is not fully accounted for; missing: {', '.join(missing)}. "
        "A capability may be shipped, deferred, validated, or removed, but silently dropping it leaves the epic breakdown incomplete."
    )


@pytest.mark.parametrize(("case_name", "concepts"), POLICY_CASES)
def test_policy_rules_are_preserved(
    case_name: str, concepts: tuple[tuple[str, tuple[str, ...]], ...]
) -> None:
    raw, error = _read_output()
    assert error is None, error
    missing = _missing(_normalize(raw), concepts)
    assert not missing, (
        f"{case_name} is misstated or incomplete; missing: {', '.join(missing)}. "
        "These frozen policy boundaries materially affect acceptance behavior and unsafe routing."
    )
