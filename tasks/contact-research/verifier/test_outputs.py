from __future__ import annotations

import re
import os
from datetime import date, datetime
from pathlib import Path


OUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/maya_chen_brief.md"))


def read_output() -> str:
    try:
        return OUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def contains(value: str, phrase: str) -> bool:
    return normalized(phrase) in normalized(value)


def date_forms(iso_value: str) -> set[str]:
    parsed = datetime.strptime(iso_value, "%Y-%m-%d")
    month = parsed.strftime("%B")
    short = parsed.strftime("%b")
    day = parsed.day
    year = parsed.year
    return {
        iso_value,
        f"{month} {day}, {year}",
        f"{month} {day} {year}",
        f"{short} {day}, {year}",
        f"{short} {day} {year}",
        f"{day} {month} {year}",
        f"{day} {short} {year}",
    }


def has_date(value: str, iso_value: str) -> bool:
    lowered = value.casefold()
    return any(form.casefold() in lowered for form in date_forms(iso_value))


def has_month_day(value: str, iso_value: str) -> bool:
    parsed = datetime.strptime(iso_value, "%Y-%m-%d")
    lowered = value.casefold()
    return has_date(value, iso_value) or any(
        form.casefold() in lowered
        for form in (f"{parsed.strftime('%B')} {parsed.day}", f"{parsed.strftime('%b')} {parsed.day}")
    )


def lines_with_date(value: str, iso_value: str) -> list[str]:
    return [
        line.casefold() for line in value.splitlines()
        if any(form.casefold() in line.casefold() for form in date_forms(iso_value))
    ]


def assert_exclusion_if_mentioned(value: str, iso_value: str, allowed_markers: tuple[str, ...]) -> None:
    lines = value.splitlines()
    matching = []
    for index, line in enumerate(lines):
        if any(form.casefold() in line.casefold() for form in date_forms(iso_value)):
            matching.append(" ".join(lines[max(0, index - 5):index + 2]).casefold())
    if matching:
        assert any(any(marker in line for marker in allowed_markers) for line in matching), (
            f"{iso_value} appears without context showing why it is not Maya's in-window initiated activity"
        )


def test_identity_resolution():
    text = read_output()
    required = [
        "Maya Chen",
        "Northstar Grid",
        "Director of Platform Engineering",
        "maya.chen@northstargrid.example",
    ]
    missing = [item for item in required if not contains(text, item)]
    assert not missing, f"the resolved Northstar contact is missing identity facts: {missing}"
    profile_refs = ["C-0043", "maya-chen-ng", "@mayacodes", "CRM-C-0043"]
    assert sum(contains(text, item) for item in profile_refs) >= 2, (
        "the brief lacks enough returned profile references to make the resolved contact actionable"
    )
    assert "maya.chen@astercloud.example" not in text.casefold(), (
        "the Aster Cloud same-name contact was mixed into the target profile"
    )
    assert "maya.chen@bluemeridian.example" not in text.casefold(), (
        "the Blue Meridian same-name contact was mixed into the target profile"
    )


def test_contact_initiated_activity():
    text = read_output()
    count_is_explicit = re.search(
        r"(?:\b(3|three)\b.{0,45}\b(contact[- ]initiated|direct)\b.{0,30}\b(actions|activities)\b"
        r"|\b(contact[- ]initiated|direct)\b.{0,45}\b(actions|activities)\b.{0,30}\b(3|three)\b)",
        text,
        re.I | re.S,
    )
    section = re.search(r"(?ims)^##\s+[^\n]*contact[- ]initiated[^\n]*\n(.*?)(?=^##\s+|\Z)", text)
    dated_rows = set(re.findall(r"\b2026-07-(?:31|24|03)\b", section.group(1) if section else ""))
    assert count_is_explicit or len(dated_rows) == 3, (
        "the brief does not make the three in-window contact-initiated actions clear"
    )
    expected = [
        ("2026-07-31", ("scim", "nested group")),
        ("2026-07-24", ("identity governance", "audit")),
        ("2026-07-03", ("sso", "three subsidiaries")),
    ]
    for iso_value, terms in expected:
        assert has_date(text, iso_value), f"missing in-window activity date {iso_value}"
        assert all(contains(text, term) for term in terms), f"missing material activity detail for {iso_value}"
    assert re.search(r"\b32\b.{0,30}\b(days?|day)\b|\b(more than|over) 30 days\b", text, re.I), (
        "the 32-day gap since Maya's latest initiated action is not called out"
    )
    assert contains(text, "cooling") or contains(text, "stale"), (
        "the practical staleness of direct engagement is not made clear"
    )
    assert_exclusion_if_mentioned(text, "2026-08-30", ("team", "our", "outbound", "excluded", "not maya"))
    assert_exclusion_if_mentioned(text, "2026-08-31", ("team", "our", "outbound", "excluded", "not maya"))
    assert_exclusion_if_mentioned(text, "2026-06-30", ("older", "outside", "excluded", "out of window"))


def test_website_interest():
    text = read_output()
    assert re.search(r"\b(6|six)\b.{0,35}\b(visits?|page views?)\b", text, re.I | re.S), (
        "the six website visits in the snapshot's 12-week window are not reported"
    )
    assert contains(text, "12 weeks") or contains(text, "84 day"), "the website time window is unclear"
    for page in [
        "/pricing/enterprise",
        "/security/compliance",
        "/docs/sso/scim",
        "/integrations/idp",
        "/customers/finops",
    ]:
        assert page.casefold() in text.casefold(), f"missing material in-window page {page}"
    assert has_date(text, "2026-08-29"), "the date of the most recent concentrated site interest is missing"
    assert_exclusion_if_mentioned(text, "2026-06-08", ("older", "outside", "excluded", "out of window"))


def test_enrichment_evolution():
    text = read_output()
    patterns = [
        r"product\s+engagement(?:\s+score)?\s*[:=\-]?\s*73(?:\.5)?",
        r"community(?:\s+score)?\s*[:=\-]?\s*41\b",
        r"fit(?:\s+(?:score|percentile))?\s*[:=\-]?\s*92(?:nd)?(?:\s+percentile|\s*%)?",
    ]
    for pattern in patterns:
        assert re.search(pattern, text, re.I), f"missing or unlabeled raw score matching {pattern}"
    for iso_value, persona in [
        ("2026-03-15", "End User"),
        ("2026-06-20", "Technical Evaluator"),
        ("2026-08-22", "Champion"),
    ]:
        assert has_date(text, iso_value), f"missing Spark date {iso_value}"
        assert contains(text, persona), f"missing Spark persona {persona}"
    assert contains(text, "promotion") or contains(text, "promoted"), (
        "the returned job/promotion evolution is omitted"
    )


def test_account_context():
    text = read_output()
    required = [
        "Expansion",
        "Open",
        "Technical Validation",
        "Identity rollout across three teams",
        "Rina Patel",
        "Theo Barnes",
    ]
    missing = [item for item in required if not contains(text, item)]
    if not (contains(text, "Low churn risk") or re.search(r"churn\s+risk\s*[:=\-]?\s*low\b", text, re.I)):
        missing.append("Low churn risk")
    assert not missing, f"the account or buying-group context is missing facts: {missing}"
    assert re.search(r"\$?180[ ,]?000\b", text), "the open expansion amount of $180,000 is missing"
    explicit_colleague_count = re.search(
        r"\b(2|two)\b.{0,70}(?:\bactive\b.{0,35}\b(colleagues?|contacts?)\b|\b(colleagues?|contacts?)\b.{0,35}\b(contact[- ]initiated|active)\b)",
        text,
        re.I | re.S,
    )
    colleague_section = re.search(r"(?ims)^\*\*active colleagues[^\n]*\n(.*?)(?=^---|^##\s+|\Z)", text)
    recent_colleague_rows = [
        line for line in (colleague_section.group(1).splitlines() if colleague_section else [])
        if "maya chen" not in line.casefold()
        and re.search(r"\bactivities?\b", line, re.I)
        and re.search(r"\b(?:jul|aug)\b", line, re.I)
    ]
    assert explicit_colleague_count or len(recent_colleague_rows) == 2, (
        "the brief does not identify that exactly two colleagues have recent initiated activity"
    )
    assert has_month_day(text, "2026-08-27") and has_month_day(text, "2026-07-18"), (
        "the active-colleague comparison lacks their latest initiated-action dates"
    )
    luca_lines = [line.casefold() for line in text.splitlines() if "luca owens" in line.casefold()]
    if luca_lines:
        assert all(any(marker in line for marker in ("not active", "not counted", "team", "no contact", "stale", "no recent")) for line in luca_lines), (
            "Luca Owens is presented as contact-active even though his recent record is only team initiated"
        )
