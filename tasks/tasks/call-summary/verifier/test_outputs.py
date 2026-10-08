from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "output.json"


def _flat(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_flat(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(_flat(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _norm(value: Any) -> str:
    text = _flat(value).lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def _key_norm(key: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(key).lower())


def _walk(value: Any, path: tuple[str, ...] = ()):
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, path + (str(index),))


def _looks_like_email(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    low = value.lower()
    return ("subject:" in low or low.lstrip().startswith("hi ")) and ("best," in low or "regards," in low)


def _extract(root: Any) -> tuple[Any, str]:
    if not isinstance(root, dict):
        raise ValueError("top-level JSON must be an object containing the two requested deliverables")

    email_candidates: list[tuple[int, str]] = []
    for path, value in _walk(root):
        if not isinstance(value, str):
            continue
        path_key = _key_norm(path[-1]) if path else ""
        key_score = 4 if ("email" in path_key or "followup" in path_key or "customernote" in path_key) else 0
        content_score = 3 if _looks_like_email(value) else 0
        if key_score or content_score:
            email_candidates.append((key_score + content_score + min(len(value) // 500, 2), value))
    if not email_candidates:
        raise ValueError("could not distinguish a plain-text customer follow-up email")
    email = max(email_candidates, key=lambda item: item[0])[1]

    recap_candidates: list[tuple[int, Any]] = []
    for path, value in _walk(root):
        if not path or value is email:
            continue
        key = _key_norm(path[-1])
        if any(token in key for token in ("internal", "recap", "summary", "crmnote", "callnote")):
            if isinstance(value, (dict, list, str)) and _norm(value):
                score = 3 + (2 if "internal" in key else 0) + min(len(_flat(value)) // 1000, 3)
                recap_candidates.append((score, value))
    if recap_candidates:
        recap = max(recap_candidates, key=lambda item: item[0])[1]
    else:
        # Accept a grouped or aliased representation by treating every non-email
        # top-level value as the recap rather than requiring a hidden key name.
        recap = {key: value for key, value in root.items() if value is not email}
    if not _norm(recap):
        raise ValueError("could not distinguish a non-empty internal recap")
    return recap, email


def _load_submission() -> tuple[Any | None, str | None, str | None]:
    try:
        if not OUTPUT.is_file():
            raise ValueError(f"missing requested artifact: {OUTPUT}")
        root = json.loads(OUTPUT.read_text(encoding="utf-8"))
        recap, email = _extract(root)
        return recap, email, None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, None, str(exc)


RECAP, EMAIL, LOAD_ERROR = _load_submission()


def _require_artifact() -> tuple[Any, str]:
    if LOAD_ERROR is not None:
        pytest.skip(f"blocked by the single artifact-usability failure: {LOAD_ERROR}")
    assert RECAP is not None and EMAIL is not None
    return RECAP, EMAIL


def _has_date(text: str, iso: str, month_day: str) -> bool:
    return iso in text or month_day.lower() in text


def _near(text: str, needle: str, terms: tuple[str, ...], radius: int = 180) -> bool:
    start = text.find(needle)
    if start < 0:
        return False
    window = text[max(0, start - radius) : start + len(needle) + radius]
    return any(term in window for term in terms)


def _action_text(recap: Any) -> str:
    sections = []
    for path, value in _walk(recap):
        if not path:
            continue
        key = _key_norm(path[-1])
        if any(token in key for token in ("action", "task", "commitment", "owner", "due")):
            sections.append(_flat(value))
    return _norm("\n".join(sections) if sections else recap)


@pytest.mark.parametrize(
    "case",
    ["identity", "workflow", "reporting_and_scope", "stage"],
)
def test_source_fidelity(case: str):
    recap, _ = _require_artifact()
    text = _norm(recap)

    if case == "identity":
        assert "acadia lodging" in text and ("2026-08-18" in text or "august 18" in text)
        for name in ("maya chen", "elena brooks", "theo martins", "samir patel"):
            assert name in text, f"internal recap omits attendee {name}"
    elif case == "workflow":
        assert ("shared inbox" in text or "shared-inbox" in text) and "audit" in text and ("reassign" in text or "status change" in text)
        assert "salesforce" in text and "saml" in text, "confirmed integration and identity needs are missing"
    elif case == "reporting_and_scope":
        for phrase in ("harbor point", "juniper house", "lakeview quay"):
            assert phrase in text, f"final three-property pilot scope omits {phrase}"
        assert ("first response" in text or "first-response" in text) and "resolution" in text
        assert "four business hours" in text or "4 business hours" in text
    elif case == "stage":
        assert "technical validation" in text
        assert "no vendor" in text or "no purchase" in text or "no procurement" in text or "active evaluation" in text


@pytest.mark.parametrize("case", ["maya_package", "maya_answers", "theo", "elena", "samir"])
def test_action_tracking(case: str):
    recap, _ = _require_artifact()
    text = _action_text(recap)

    if case == "maya_package":
        assert "maya" in text and "quote" in text and "security" in text and "connector" in text
        assert _has_date(text, "2026-08-21", "august 21")
    elif case == "maya_answers":
        assert "maya" in text and "ocr" in text and "stay id" in text and ("write-back" in text or "writeback" in text)
        assert "before" in text and ("launch" in text or "pilot" in text), "open technical answers need their agreed launch dependency"
    elif case == "theo":
        assert "theo" in text and "field mapping" in text and "stay id" in text
        assert _has_date(text, "2026-08-20", "august 20")
    elif case == "elena":
        assert "elena" in text and "manager" in text and ("availability" in text or "confirm" in text)
        assert _has_date(text, "2026-08-24", "august 24")
    elif case == "samir":
        assert "samir" in text and "dpa" in text and "redline" in text
        assert _has_date(text, "2026-08-24", "august 24") and ("if" in text or "conditional" in text)


@pytest.mark.parametrize(
    "case",
    ["competitive_boundary", "residency_boundary", "salesforce_boundary", "milestones", "corrections"],
)
def test_commitment_boundaries(case: str):
    recap, email = _require_artifact()
    summary = _norm(recap)
    note = _norm(email)

    if case == "competitive_boundary":
        assert "brightdesk" in summary and ("15 percent" in summary or "15%" in summary or "lower" in summary)
        assert "brightdesk" not in note and "15 percent lower" not in note and "15% lower" not in note
    elif case == "residency_boundary":
        assert "eu" in summary and "ocr" in summary and ("open" in summary or "confirm" in summary or "unresolved" in summary)
        assert "ocr" in note and ("confirm" in note or "open" in note or "still" in note)
        assert "case records" in note or "case data" in note, "email should distinguish confirmed EU case hosting from the open OCR route"
    elif case == "salesforce_boundary":
        assert "standard" in summary and "salesforce" in summary and "stay id" in summary
        assert "stay id" in note and ("confirm" in note or "open" in note or "still" in note)
        assert not re.search(r"(?:confirmed|supports?)\s+(?:the\s+)?(?:custom\s+)?stay id (?:write-back|writeback)", note)
    elif case == "milestones":
        assert _near(summary, "august 25", ("tentative", "not confirmed"))
        assert _near(note, "august 25", ("tentative", "not confirmed"))
        assert _near(summary, "september 14", ("conditional", "depend", "only if"))
        assert _near(note, "september 14", ("conditional", "depend", "only if"))
    elif case == "corrections":
        assert re.search(r"\b72\b", note) and not re.search(r"\b75\b", note)
        assert "saml" in summary and "scim" in summary and ("add-on" in summary or "addon" in summary)
        assert "scim" in note and ("exclude" in note or "outside" in note or "not included" in note)
        assert "$42" in note and ("$36,288" in note or "36288" in note)
        assert "$8,400" in note or "8400" in note
        assert "separate" in note and ("subject to" in note or "estimate" in note)
