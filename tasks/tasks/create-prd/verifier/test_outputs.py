from __future__ import annotations

import csv
import os
import re
import statistics
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "PRD-batch-triage.md"


def _read_submission() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _submission_or_skip() -> str:
    text = _read_submission()
    if not text:
        pytest.skip("the root artifact is unavailable; readability is scored once")
    return text


def _normalize(text: str) -> str:
    text = text.casefold().replace("–", "-").replace("—", "-").replace("≤", "<=")
    text = text.replace(",", "")
    text = re.sub(r"\b(\d+(?:\.\d+)?)\s+percent\b", r"\1%", text)
    return re.sub(r"\s+", " ", text).strip()


def _heading_texts(text: str) -> list[str]:
    headings = []
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            heading = re.sub(r"[*_`]", "", match.group(1))
            heading = re.sub(r"^\d+(?:\.\d+)*[.)]?\s*", "", heading)
            headings.append(_normalize(heading))
    return headings


def _has_heading(headings: list[str], aliases: tuple[str, ...]) -> bool:
    return any(any(alias in heading for alias in aliases) for heading in headings)


def _load_expected_baseline() -> dict[str, float]:
    rows = list(csv.DictReader((DATA / "triage_sessions.csv").open(encoding="utf-8")))
    numeric = (
        "queue_size",
        "completion_minutes",
        "first_action_minutes",
        "misroutes",
        "permission_blocks",
    )
    for row in rows:
        for key in numeric:
            row[key] = int(row[key])
    eligible = [row for row in rows if 10 <= row["queue_size"] <= 50 and row["permission_blocks"] == 0]
    ticket_count = sum(row["queue_size"] for row in eligible)
    misroutes = sum(row["misroutes"] for row in eligible)
    return {
        "session_count": len(eligible),
        "ticket_count": ticket_count,
        "median_completion": statistics.median(row["completion_minutes"] for row in eligible),
        "median_first_action": statistics.median(row["first_action_minutes"] for row in eligible),
        "misroutes": misroutes,
        "misroute_rate": 100 * misroutes / ticket_count,
    }


def _line_with(text: str, *groups: tuple[str, ...]) -> bool:
    for line in text.splitlines():
        normalized = _normalize(line)
        if all(any(term in normalized for term in group) for group in groups):
            return True
    return False


def test_markdown_prd_is_readable_and_complete():
    """The requested Markdown PRD exists and exposes its core decision areas."""
    text = _read_submission()
    assert text, "PRD-batch-triage.md is missing, empty, or not UTF-8 readable"
    words = re.findall(r"\b[\w'-]+\b", text)
    assert 650 <= len(words) <= 5000, (
        f"the PRD contains {len(words)} words; it is too thin for engineering use or too long for the requested concise review"
    )
    normalized = _normalize(text)
    assert "batch triage" in normalized and "relaydesk" in normalized, "the artifact does not identify the requested initiative"
    headings = _heading_texts(text)
    required_areas = {
        "summary": ("summary", "overview", "executive brief"),
        "contacts": ("contact", "stakeholder", "owner"),
        "background": ("background", "problem", "context"),
        "objective": ("objective", "key result", "success", "outcome", "metric"),
        "segments": ("segment", "user", "job to be done", "audience"),
        "value": ("value proposition", "customer value", "benefit"),
        "solution": ("solution", "experience", "requirement", "feature"),
        "release": ("release", "roadmap", "rollout", "delivery plan", "milestone"),
    }
    missing = [name for name, aliases in required_areas.items() if not _has_heading(headings, aliases)]
    assert not missing, f"the engineering PRD has no identifiable content area for: {', '.join(missing)}"
    assert _has_heading(headings, ("assumption", "open question", "decision needed", "risk")), (
        "the PRD does not expose assumptions or unresolved review decisions"
    )


def test_baseline_evidence_matches_sessions():
    """The reported manual baseline matches the task's defined eligible cohort."""
    text = _read_submission()
    assert text, "the evidence criterion cannot be evaluated because the requested PRD is unavailable"
    expected = _load_expected_baseline()
    normalized = _normalize(text)
    assert re.search(rf"\b{int(expected['session_count'])}\b[^\n.]{{0,45}}session", normalized) or re.search(
        rf"session[^\n.]{{0,45}}\b{int(expected['session_count'])}\b", normalized
    ), "the PRD does not report the eligible-session denominator from the supplied workflow data"
    assert re.search(rf"\b{int(expected['ticket_count'])}\b[^\n.]{{0,45}}ticket", normalized) or re.search(
        rf"ticket[^\n.]{{0,45}}\b{int(expected['ticket_count'])}\b", normalized
    ), "the PRD does not report the ticket denominator for its manual baseline"
    assert _line_with(
        text,
        ("median",),
        ("completion", "complete"),
        (f"{expected['median_completion']:.0f}",),
        ("minute", "min"),
    ), "the eligible cohort's median completion baseline is missing or wrong"
    observed_rates = []
    for line in text.splitlines():
        normalized_line = _normalize(line)
        if "misrout" in normalized_line:
            observed_rates.extend(float(value) for value in re.findall(r"(\d+(?:\.\d+)?)%", normalized_line))
    assert any(abs(value - expected["misroute_rate"]) <= 0.02 for value in observed_rates), (
        "the baseline misroute rate is missing or differs materially from the frozen session calculation"
    )


@pytest.mark.parametrize(
    "outcome",
    ("speed", "quality", "adoption", "control"),
)
def test_approved_smart_outcomes(outcome: str):
    """Each approved pilot outcome keeps its target, measure, and time or safety boundary."""
    text = _submission_or_skip()
    normalized = _normalize(text)
    if outcome == "speed":
        assert "35%" in normalized and re.search(r"(?:six|6)[ -]?week", normalized), (
            "the speed outcome must retain the approved 35% improvement and six-week readout"
        )
        assert _line_with(text, ("35%",), ("median",), ("completion", "complete")), (
            "the 35% target is not tied to median completion time"
        )
    elif outcome == "quality":
        assert _line_with(text, ("2.0%", "2%"), ("misroute", "misrout")), (
            "the approved 2.0% misroute ceiling is missing"
        )
        assert re.search(r"(?:week[^.\n]{0,30}(?:six|6)|(?:six|6)[ -]?week)", normalized), (
            "the quality outcome has no six-week readout"
        )
    elif outcome == "adoption":
        assert _line_with(text, ("75%",), ("three", "3"), ("day",), ("week",)), (
            "the adoption outcome must retain 75% of eligible agents on at least three days per week"
        )
    else:
        audit_complete = _line_with(text, ("100%", "every", "all"), ("audit",), ("applied", "change"))
        unauthorized_zero = _line_with(text, ("zero", "no "), ("unauthorized",), ("applied", "change", "edit"))
        assert audit_complete and unauthorized_zero, (
            "the pilot outcomes must require complete per-ticket audit coverage and zero applied unauthorized changes"
        )


def test_v1_limits_and_safeguards():
    """The v1 workflow preserves the committed operating and safety contract."""
    text = _read_submission()
    assert text, "the v1 criterion cannot be evaluated because the requested PRD is unavailable"
    normalized = _normalize(text)
    required_concepts = {
        "single queue": bool(re.search(r"(?:one|single)[ -]queue|within one queue", normalized)),
        "50-ticket maximum": bool(re.search(r"(?:maximum|max(?:imum)?|up to|limit|cap|no more than|hard maximum)[^.;\n]{0,35}\b50\b|\b50\b[^.;\n]{0,35}(?:ticket|limit|cap|maximum)", normalized)),
        "supported routing edits": all(term in normalized for term in ("owner", "priority", "tag")),
        "preview before confirmation": "preview" in normalized and "confirm" in normalized,
        "stale and permission recheck": "stale" in normalized and ("permission" in normalized or "authoriz" in normalized),
        "partial outcome detail": all(term in normalized for term in ("changed", "skipped", "failed")),
        "idempotent retry": "idempot" in normalized and ("retry" in normalized or "duplicate" in normalized),
        "per-ticket audit": bool(re.search(r"(?:per[ -]ticket|ticket[ -]level)[^.;\n]{0,35}audit|audit[^.;\n]{0,35}(?:per[ -]ticket|ticket[ -]level)", normalized)),
        "accessible flow": "keyboard" in normalized and ("screen reader" in normalized or "assistive" in normalized),
    }
    missing = [name for name, present in required_concepts.items() if not present]
    assert not missing, f"the v1 contract omits material behavior or safeguards: {', '.join(missing)}"


@pytest.mark.parametrize(
    ("capability", "patterns"),
    (
        ("larger batches", (r"more than 50", r"over 50", r"above 50", r">\s*50", r"500[ -]?ticket")),
        ("cross-queue selection", (r"cross[ -]?queue", r"multiple queues", r"multi[ -]?queue")),
        ("automatic routing", (r"automatic routing", r"automated routing", r"auto[ -]?routing", r"routing rules?", r"suggested routing")),
        ("bulk status changes", (r"bulk status", r"status changes?", r"status edit")),
        ("undo", (r"one[ -]?click undo", r"\bundo\b", r"reversal")),
    ),
)
def test_deferred_capabilities_stay_out_of_v1(capability: str, patterns: tuple[str, ...]):
    """Riskier or dependency-heavy requests are clearly deferred rather than promised in v1."""
    text = _submission_or_skip()
    defer_cues = re.compile(
        r"(?:later|future|defer|out of scope|not (?:in|include|part)|does not include|excluded|wait|after v1|beyond v1|post[ -]?v1|phase 2|non-goal|not safe|separate)"
    )
    relevant = []
    for line in text.splitlines():
        normalized = _normalize(line)
        if any(re.search(pattern, normalized) for pattern in patterns):
            relevant.append(normalized)
    assert relevant, f"the PRD does not resolve the {capability} request"
    assert any(defer_cues.search(line) for line in relevant), (
        f"{capability} appears without a clear later/out-of-scope decision and could be read as a v1 commitment"
    )
