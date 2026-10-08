from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


OUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/heliofleet_escalation_response.md"))


def read_output() -> str:
    try:
        return OUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def has_all(value: str, terms: tuple[str, ...]) -> bool:
    haystack = normalized(value)
    return all(normalized(term) in haystack for term in terms)


def split_public_internal(value: str) -> tuple[str, str]:
    """Accept common Markdown or plain-text labels for the requested separation."""
    offset = 0
    for line in value.splitlines(keepends=True):
        label = normalized(line.lstrip("#*-_ "))
        is_internal_label = (
            ("internal" in label and ("note" in label or "review" in label))
            or "notes for you" in label
            or ("do not send" in label and len(label.split()) <= 12)
        )
        if is_internal_label:
            return value[:offset].strip(), value[offset:].strip()
        offset += len(line)
    return value.strip(), ""


def explicit_threshold(value: str) -> bool:
    return bool(
        re.search(r"(?:more than|over|greater than|above)\s+250\s+stops", value, re.I)
        or re.search(r"(?:>|&gt;)\s*250\s+stops", value, re.I)
    )


def sep9_update(value: str) -> bool:
    time_ok = bool(re.search(r"\b17(?::?00)?\s*(?:UTC|Z)\b|\b5(?::00)?\s*p\.?m\.\s*(?:UTC)?", value, re.I))
    date_ok = bool(re.search(r"(?:September|Sep\.?)[ ]+9(?:,?[ ]+2026)?|2026-09-09|today", value, re.I))
    update_ok = bool(re.search(r"\b(update|hear from|follow[- ]?up)\b", value, re.I))
    return time_ok and date_ok and update_ok


def checkpoint_is_communication(value: str) -> bool:
    time_pattern = r"\b17(?::?00)?\s*(?:UTC|Z)\b|\b5(?::00)?\s*p\.?m\.\s*(?:UTC)?"
    lines = [line for line in value.splitlines() if re.search(time_pattern, line, re.I)]
    if not lines:
        return False
    return any(re.search(r"\b(update|hear from|follow[- ]?up)\b", line, re.I) for line in lines) and not any(
        re.search(r"\b(?:fix(?:ed)?|resolv(?:e|ed|ution))\s+(?:by|at)\s+17(?::?00)?\b", line, re.I)
        for line in lines
    )


@pytest.mark.parametrize(
    ("case", "check"),
    [
        ("recipient_and_product", lambda text: has_all(text, ("Elena Marquez", "RouteSync"))),
        (
            "service_and_status",
            lambda text: "routesync" in text.casefold() and bool(re.search(r"\binvestigat(?:e|es|ed|ing|ion)\b", text, re.I)),
        ),
        ("operational_impact", lambda text: has_all(text, ("62", "dispatchers", "480", "routes"))),
        ("failure_scope", lambda text: "502" in text and explicit_threshold(text)),
        (
            "validated_workaround",
            lambda text: has_all(text, ("split", "batches", "250", "stops"))
            and bool(
                re.search(r"250\s+stops\s+or\s+(?:fewer|less)", text, re.I)
                or re.search(r"(?:at most|no more than)\s+250\s+stops", text, re.I)
                or re.search(r"(?:<=|≤)\s*250\s+stops", text, re.I)
            ),
        ),
        ("unaffected_functions", lambda text: has_all(text, ("route editing", "live vehicle tracking", "unaffected"))),
        (
            "missed_prior_commitment",
            lambda text: bool(re.search(r"12(?::?00)?\s*(?:UTC|Z)", text, re.I))
            and bool(re.search(r"\b(miss(?:ed)?|late|overdue|sorry|apolog)\w*\b", text, re.I)),
        ),
        ("incident_owner", lambda text: has_all(text, ("Priya Nair", "engineering"))),
        ("next_update", sep9_update),
    ],
)
def test_customer_specific_facts(case, check):
    public, _ = split_public_internal(read_output())
    assert check(public), f"the sendable email is missing or misstates the source-backed fact: {case}"


@pytest.mark.parametrize(
    ("case", "check"),
    [
        (
            "confidential_details",
            lambda text: not re.search(r"\b(Mercury|Project Relay|queue saturation)\b", text, re.I),
        ),
        (
            "no_resolution_promise",
            lambda text: not re.search(
                r"(?:will|should|expect(?:ed)? to)\s+(?:be\s+)?(?:fully\s+)?(?:fix(?:ed)?|resolv(?:e|ed))"
                r"|(?:fix|resolution)\s+(?:is\s+)?(?:due|expected|scheduled)\s+(?:by|on|at)",
                text,
                re.I,
            ),
        ),
        (
            "credit_handling",
            lambda text: "credit" in text.casefold()
            and bool(re.search(r"credit.{0,80}\b(under (?:separate )?review|pending|not (?:yet )?approved|no decision|cannot approve|can't approve)\b", text, re.I | re.S))
            and not re.search(r"\b(approved?|grant(?:ed)?|issue(?:d)?)\b.{0,35}\bcredit\b|\bcredit\b.{0,20}\bof\s*\$", text, re.I),
        ),
        (
            "roadmap_handling",
            lambda text: bool(re.search(r"automatic\s+retr(?:y|ies)", text, re.I))
            and bool(re.search(r"(?:automatic\s+retr(?:y|ies).{0,90}(?:no|not|cannot|can't|without).{0,30}(?:commit|approv|plan))|(?:(?:no|not|cannot|can't).{0,40}(?:commit|approv|plan).{0,90}automatic\s+retr(?:y|ies))", text, re.I | re.S))
            and not re.search(r"automatic\s+retr(?:y|ies).{0,40}\b(will ship|will launch|is scheduled|is on the roadmap)\b", text, re.I | re.S),
        ),
        (
            "update_not_resolution",
            lambda text: sep9_update(text) and checkpoint_is_communication(text),
        ),
    ],
)
def test_authorization_and_confidentiality_boundaries(case, check):
    public, _ = split_public_internal(read_output())
    assert check(public), f"the sendable email crosses or fails to state the required boundary: {case}"
