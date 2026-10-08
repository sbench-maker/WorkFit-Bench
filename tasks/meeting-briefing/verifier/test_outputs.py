from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "meeting_brief.md"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip()


def brief_text() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return normalize(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return ""


def all_terms(text: str, *groups: tuple[str, ...]) -> bool:
    """Each group is satisfied when any normalized alternative occurs."""
    return all(any(normalize(option) in text for option in group) for group in groups)


def number_present(text: str, full: str, short: str | None = None) -> bool:
    compact = text.replace(",", "").replace(" ", "")
    return full in compact or (short is not None and short in compact)


def require_submission() -> str:
    text = brief_text()
    if not text:
        pytest.skip("semantic checks skipped because the requested Markdown artifact is unavailable")
    return text


def test_meeting_and_participant_grounding():
    text = require_submission()
    calendar = json.loads((DATA_DIR / "calendar_events.json").read_text(encoding="utf-8"))
    event = next(row for row in calendar if row["event_id"] == "cal-ns-0911")
    names = [normalize(row["name"]) for row in event["attendees"]]
    missing_names = [name for name in names if name not in text]
    checks = {
        "meeting title": normalize(event["title"]) in text,
        "date": any(token in text for token in ("11 september 2026", "september 11, 2026", "2026-09-11", "sep 11, 2026", "11 sep 2026")),
        "start time": bool(re.search(r"\b15[:.]?00\b|\b3[:.]?00\s*p\.?m\.?", text)),
        "duration/end": "75 minute" in text or "16:15" in text or "4:15 pm" in text,
        "timezone": "asia/shanghai" in text or "china standard time" in text or "cst (utc+8" in text,
        "Ava role": "ava chen" in text and ("negotiator" in text or "lead legal" in text or "legal terms" in text),
        "all attendees": not missing_names,
    }
    failed = [label for label, ok in checks.items() if not ok]
    assert not failed, f"meeting grounding is incomplete or inaccurate: {failed}; missing attendees={missing_names}"


ISSUE_CASES = [
    "commercial_baseline_and_offer",
    "superseded_budget_ceiling",
    "term_and_notice_deadline",
    "incident_notice_positions",
    "audit_positions",
    "subprocessor_positions",
    "ai_data_use_conflict",
    "liability_positions",
    "sla_and_credit",
    "transition_positions",
    "approval_state",
]


@pytest.mark.parametrize("case", ISSUE_CASES)
def test_negotiation_facts(case):
    text = require_submission()
    if case == "commercial_baseline_and_offer":
        ok = number_present(text, "480000", "480k") and number_present(text, "547200", "547.2k") and "14%" in text
    elif case == "superseded_budget_ceiling":
        ok = number_present(text, "513600", "513.6k") and "7%" in text and "520000" in text.replace(",", "") and all_terms(text, ("superseded", "replaced", "outdated", "not current"))
    elif case == "term_and_notice_deadline":
        ok = all_terms(text, ("24-month", "24 month", "two-year", "two year"), ("16 september", "september 16", "2026-09-16", "sep 16"), ("non-renewal", "nonrenewal", "notice"))
    elif case == "incident_notice_positions":
        ok = all_terms(text, ("72 hour", "72-hour", "72 hr", "72-hr"), ("24 hour", "24-hour", "24 hr", "24-hr"), ("incident", "breach"))
    elif case == "audit_positions":
        ok = all_terms(text, ("every two year", "once every two year", "biennial"), ("annual audit", "audit annually"), ("10 business day", "ten business day"))
    elif case == "subprocessor_positions":
        ok = all_terms(text, ("15 day", "fifteen day"), ("30 day", "thirty day"), ("subprocessor", "sub-processor"))
    elif case == "ai_data_use_conflict":
        ok = all_terms(text, ("deidentified", "de-identified"), ("train", "training", "tuning", "model improvement"), ("no training", "may not train", "prohibit", "remove", "not use"))
    elif case == "liability_positions":
        ok = all_terms(text, ("prior 12 month", "preceding 12 month", "12-mo", "12 month", "one times", "1x", "1×"), ("uncapped",), ("2x", "2×", "two times"), ("liability", "cap"))
    elif case == "sla_and_credit":
        ok = all_terms(text, ("99.7%",), ("99.9%",), ("7h40m", "7h 40m", "7 h 40", "7 hours 40")) and number_present(text, "8400", "8.4k") and all_terms(text, ("pending", "not confirmed", "not accepted"))
    elif case == "transition_positions":
        ok = all_terms(text, ("45 day", "forty-five day"), ("90 day", "ninety day"), ("transition",))
    elif case == "approval_state":
        ok = all_terms(text, ("no approval", "none recorded", "not yet approved"), ("procurement",), ("finance",), ("security",), ("legal",))
    else:
        raise AssertionError(f"unknown case {case}")
    assert ok, f"the brief does not accurately reconcile the material issue: {case}"


FOLLOWUP_CASES = [
    "dpa_owner_and_status",
    "scc_owner_and_status",
    "completed_internal_actions",
    "service_credit_status",
    "assurance_gap",
    "unscheduled_followup_and_missing_approvals",
    "source_limitation",
]


@pytest.mark.parametrize("case", FOLLOWUP_CASES)
def test_followups_and_preparation_gaps(case):
    text = require_submission()
    if case == "dpa_owner_and_status":
        ok = all_terms(text, ("elliot brooks",), ("28 aug", "aug 28", "28 august"), ("overdue",), ("dpa",), ("not received", "missing", "not available"))
    elif case == "scc_owner_and_status":
        ok = all_terms(text, ("nadia kline",), ("2 sep", "sep 2", "2 september"), ("overdue",), ("annex iii", "annex 3"), ("not received", "missing", "incomplete"))
    elif case == "completed_internal_actions":
        ok = all_terms(text, ("lena ortiz",), ("martin shaw",), ("ava chen",), ("completed", "complete"))
    elif case == "service_credit_status":
        ok = all_terms(text, ("priya nair",), ("calculation complete", "calculation reconciled", "reconciled"), ("vendor acceptance pending", "northstar acceptance pending", "not accepted", "not confirmed"))
    elif case == "assurance_gap":
        ok = all_terms(text, ("soc 2", "soc2"), ("bridge letter",), ("no ", "missing", "not found", "not available"), ("2026",))
    elif case == "unscheduled_followup_and_missing_approvals":
        ok = all_terms(text, ("follow-up", "follow up"), ("not on the calendar", "not scheduled", "no follow-up", "unscheduled"), ("approval",), ("not recorded", "none recorded", "no approval", "not yet approved"))
    elif case == "source_limitation":
        ok = all_terms(text, ("deleted message",), ("unavailable", "exclude", "not reviewed", "not included"))
    else:
        raise AssertionError(f"unknown case {case}")
    assert ok, f"the brief misses or misstates a material prior follow-up/preparation gap: {case}"
