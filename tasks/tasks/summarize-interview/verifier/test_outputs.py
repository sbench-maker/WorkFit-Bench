from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", "/root/results"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/root/data"))
OUTPUT = RESULTS_DIR / "interview_summary.md"


def _read_output_or_none() -> str | None:
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _plain(text: str) -> str:
    text = re.sub(r"[`*_#>|]", " ", text.casefold())
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_dates(text: str) -> str:
    value = text.casefold()
    replacements = {
        r"(?:august|aug\.?)[\s-]+25(?:st)?(?:,?[\s-]+2026)?": "2026-08-25",
        r"(?:august|aug\.?)[\s-]+27(?:th)?(?:,?[\s-]+2026)?": "2026-08-27",
        r"(?:august|aug\.?)[\s-]+28(?:th)?(?:,?[\s-]+2026)?": "2026-08-28",
        r"(?:september|sept?\.?)[\s-]+4(?:th)?(?:,?[\s-]+2026)?": "2026-09-04",
        r"25(?:th)?[\s-]+(?:august|aug\.?)\s+2026": "2026-08-25",
        r"27(?:th)?[\s-]+(?:august|aug\.?)\s+2026": "2026-08-27",
        r"28(?:th)?[\s-]+(?:august|aug\.?)\s+2026": "2026-08-28",
        r"4(?:th)?[\s-]+(?:september|sept?\.?)\s+2026": "2026-09-04",
    }
    for pattern, canonical in replacements.items():
        value = re.sub(pattern, canonical, value)
    return value


def _action_section(text: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        is_heading = bool(
            re.match(r"^#{1,6}\s+", stripped)
            or re.match(r"^\*\*[^*]+\*\*\s*:?\s*$", stripped)
            or (len(stripped) <= 80 and stripped.endswith(":"))
        )
        if not is_heading:
            continue
        label = _plain(line)
        if re.search(r"\b(action items?|follow[- ]?ups?|next steps?|commitments?)\b", label):
            start = index + 1
            break
    if start is None:
        return ""
    selected = []
    for line in lines[start:]:
        if re.match(r"^\s{0,3}#{1,6}\s+", line) and selected:
            break
        if re.match(r"^\s*\*\*[^*]+\*\*\s*:?\s*$", line) and selected:
            break
        selected.append(line)
    return "\n".join(selected)


def _window_around(text: str, needle: str, radius: int = 240) -> str:
    index = text.find(needle)
    if index < 0:
        return ""
    return text[max(0, index - radius) : index + len(needle) + radius]


def test_artifact_is_readable_and_structured():
    """Rule criterion: artifact_and_context."""
    text = _read_output_or_none()
    assert text is not None, (
        "interview_summary.md is missing or not readable UTF-8; the roadmap team has no usable brief"
    )
    assert len(text.strip()) >= 500, (
        "the brief is too short to contain the requested interview context, solution evaluation, insights, and follow-ups"
    )
    labels = [_plain(line) for line in text.splitlines() if line.lstrip().startswith(("#", "**"))]
    concepts = {
        "people": ("participant", "attendee", "interviewee"),
        "context": ("background", "context", "customer profile"),
        "solution": ("current solution", "current workflow", "today s tools", "today s process"),
        "evaluation": ("works", "like", "strength", "problem", "pain", "fail", "challenge"),
        "insights": ("insight", "finding", "takeaway"),
        "actions": ("action", "follow-up", "follow up", "next step", "commitment"),
    }
    represented = sum(any(alias in label for label in labels for alias in aliases) for aliases in concepts.values())
    assert represented >= 5, (
        f"only {represented} of 6 requested content areas are visibly structured; readers cannot scan the brief reliably"
    )


def test_interview_context_matches_transcript():
    """Rule criterion: artifact_and_context."""
    text = _read_output_or_none()
    if text is None:
        pytest.skip("root artifact problem is reported by the readability test")
    normalized = _plain(_normalize_dates(text))
    required = {
        "interview date": ("2026-08-21", "august 21 2026", "21 august 2026"),
        "Elena Ruiz": ("elena ruiz",),
        "Elena role": ("revenue operations manager", "revops manager"),
        "Maya Chen": ("maya chen",),
        "Maya role": ("product manager",),
        "Dev Shah": ("dev shah",),
        "Dev role": ("customer researcher", "researcher"),
        "customer company": ("cedar finch home services",),
        "corrected active seller count": ("14 active seller", "fourteen active seller"),
        "primary CRM": ("trackspring",),
        "spreadsheet workaround": ("renewals board",),
    }
    missing = [name for name, aliases in required.items() if not any(alias in normalized for alias in aliases)]
    assert not missing, (
        f"the brief omits or misstates objective interview context: {missing}; planning may use the wrong customer facts"
    )
    assert not re.search(r"(?<!not )(?<!not the )\b18\s+(?:active\s+)?(?:sales\s+)?reps?\b", normalized), (
        "the brief repeats the interviewee's corrected 18-rep statement instead of the authoritative 14 active sellers"
    )


ACTION_CASES = [
    ("2026-08-25", "maya chen", (("routing", "route"), ("mock", "prototype"))),
    ("2026-08-27", "dev shah", (("mobile",), ("test", "session"), ("two", "2"), ("rep", "seller"))),
    ("2026-08-28", "elena ruiz", (("duplicate",), ("five", "5"), ("anonym", "redact"))),
    ("2026-09-04", "maya chen", (("offline",), ("feasib", "engineering", "confirm"))),
]


@pytest.mark.parametrize("date,owner,concept_groups", ACTION_CASES)
def test_committed_action_present(date: str, owner: str, concept_groups: tuple[tuple[str, ...], ...]):
    """Rule criterion: committed_followups."""
    text = _read_output_or_none()
    if text is None:
        pytest.skip("root artifact problem is reported by the readability test")
    section = _plain(_normalize_dates(_action_section(text)))
    assert section, "no action or follow-up section could be located in the structured brief"
    window = _window_around(section, date)
    assert window and owner in window, (
        f"the {date} commitment is missing its agreed owner {owner}; the follow-up cannot be assigned reliably"
    )
    missing_groups = [group for group in concept_groups if not any(token in window for token in group)]
    assert not missing_groups, (
        f"the {date} action loses material agreed scope {missing_groups}; the owner may execute the wrong follow-up"
    )


def test_deferred_ideas_are_not_actions():
    """Rule criterion: committed_followups."""
    text = _read_output_or_none()
    if text is None:
        pytest.skip("root artifact problem is reported by the readability test")
    section = _plain(_action_section(text))
    forbidden = {
        "annual pricing": r"annual\s+pric",
        "training webinar": r"training\s+webinar|webinar",
        "duplicate-merging FAQ": r"(?:duplicate|merg\w*)[^.\n]{0,50}\bfaq\b|\bfaq\b",
        "quarterly customer council": r"customer\s+council|quarterly\s+council",
    }
    promoted = [name for name, pattern in forbidden.items() if re.search(pattern, section)]
    assert not promoted, (
        f"explicitly deferred brainstorms appear in the action list: {promoted}; this creates false commitments"
    )
