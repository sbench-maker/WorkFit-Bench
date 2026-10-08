from __future__ import annotations

import os
import re
from pathlib import Path


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
OUTPUT = RESULTS_DIR / "weekly_3p.md"


def read_output() -> str:
    assert OUTPUT.is_file(), (
        f"missing {OUTPUT}; leadership cannot use the requested weekly update"
    )
    try:
        text = OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AssertionError(f"{OUTPUT} is not readable UTF-8 Markdown: {exc}") from exc
    assert text.strip(), "weekly_3p.md is empty"
    return text


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-")).strip().lower()


def has_number_near_terms(text: str, number: int, terms: list[str], radius: int = 90) -> bool:
    value = f"{number:,}"
    variants = {str(number), value}
    lower = normalized(text)
    for variant in variants:
        for match in re.finditer(rf"(?<!\d){re.escape(variant)}(?!\d)", lower):
            window = lower[max(0, match.start() - radius) : match.end() + radius]
            if any(term in window for term in terms):
                return True
    return False


def test_artifact_is_readable_and_scoped() -> None:
    text = normalized(read_output())
    assert len(text) >= 120, "the artifact is too short to convey a usable weekly incident update"
    assert "workplace systems reliability" in text, "the update does not identify the requested team"
    date_range = re.search(
        r"sep(?:tember)?\s+0?1\s*(?:-|to|through)\s*(?:sep(?:tember)?\s+)?0?7",
        text,
    )
    assert date_range and "2026" in text, (
        "the update does not identify the requested September 1-7, 2026 reporting week"
    )


def test_three_p_sections_are_present() -> None:
    lines = read_output().splitlines()
    labels = set()
    for line in lines:
        clean = re.sub(r"^[\s#>*+\-]+", "", line).strip()
        clean = clean.replace("**", "").replace("__", "").replace("–", "-").replace("—", "-")
        for label in ("progress", "plans", "problems"):
            if re.match(rf"(?i)^{label}\s*(?::|-|$)", clean):
                labels.add(label)
    missing = [label for label in ("progress", "plans", "problems") if label not in labels]
    assert not missing, (
        f"missing distinguishable 3P content for {missing}; readers cannot scan progress, plans, and problems"
    )


def test_sso_impact_and_recovery_facts() -> None:
    text = read_output()
    assert has_number_near_terms(text, 184, ["employee", "user", "staff", "people"]), (
        "the update must accurately state that 184 employees were affected"
    )
    assert has_number_near_terms(text, 11, ["app", "application", "saas"]), (
        "the update must accurately state that 11 applications were affected"
    )
    lower = normalized(text)
    has_duration = bool(re.search(r"(?<!\d)54(?!\d)\s*-?\s*(?:minute|min\b)", lower))
    has_endpoints = "09:08" in lower and "10:02" in lower
    assert has_duration or has_endpoints, (
        "the update must accurately convey the 54-minute recovery window, either directly or by its endpoints"
    )


def test_linked_ticket_disposition_facts() -> None:
    text = normalized(read_output())
    assert has_number_near_terms(text, 72, ["ticket", "case"]), (
        "the update does not accurately identify the 72 tickets linked to the SSO incident"
    )
    finished_explicit = has_number_near_terms(text, 69, ["resolved", "closed", "finished", "completed"])
    all_but_three = bool(
        re.search(r"(?:all\s+but|except(?:\s+for)?)\s+(?:3|three).{0,70}(?:ticket|case)", text)
        or re.search(r"(?:ticket|case).{0,70}(?:all\s+but|except(?:\s+for)?)\s+(?:3|three)", text)
    )
    assert finished_explicit or all_but_three, (
        "the update must convey that 69 of 72 linked tickets were resolved or closed"
    )
    pending_three = bool(
        re.search(r"(?:3|three).{0,90}(?:ticket|case).{0,90}(?:await|pending|confirm)", text)
        or re.search(r"(?:ticket|case).{0,90}(?:3|three).{0,90}(?:await|pending|confirm)", text)
        or re.search(r"(?:await|pending).{0,90}(?:3|three).{0,90}(?:ticket|case)", text)
    )
    assert pending_three, (
        "the update must distinguish the three tickets still awaiting user confirmation from completed work"
    )
