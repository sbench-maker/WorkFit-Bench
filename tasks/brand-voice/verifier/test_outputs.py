from __future__ import annotations

import re
from pathlib import Path

import pytest


OUTPUT = Path("/root/results/voice_launch_kit.md")


def _read_submission() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _label(line: str) -> str:
    line = re.sub(r"^[\s#>*_`-]+", "", line.strip())
    line = re.sub(r"[\s:_-]+$", "", line)
    return re.sub(r"\s+", " ", line).casefold()


def _section_kind(line: str) -> str | None:
    label = _label(line)
    if label == "voice profile" or label.startswith("voice profile "):
        return "profile"
    if label in {"x", "x post", "x draft", "x launch post", "social post"}:
        return "x"
    if len(label) <= 60 and (label.startswith("x ") or ("social" in label and "copy" in label)):
        return "x"
    if label in {"email", "email draft", "customer email", "customer email draft"}:
        return "email"
    if len(label) <= 60 and "email" in label and not label.startswith("channel"):
        return "email"
    return None


def _sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    markers: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        kind = _section_kind(line)
        if kind and kind not in seen:
            markers.append((index, kind))
            seen.add(kind)
    result: dict[str, str] = {}
    for offset, (start, kind) in enumerate(markers):
        end = markers[offset + 1][0] if offset + 1 < len(markers) else len(lines)
        result[kind] = "\n".join(lines[start + 1 : end]).strip()
    return result


def _drafts_or_skip() -> dict[str, str]:
    text = _read_submission()
    sections = _sections(text)
    if not text or not {"x", "email"}.issubset(sections):
        pytest.skip("draft sections are unavailable; the root artifact/component failure is scored once")
    return sections


def _numbers(text: str) -> set[int]:
    return {int(token.replace(",", "")) for token in re.findall(r"(?<![A-Za-z])\d[\d,]*(?![A-Za-z])", text)}


def test_artifact_components():
    """The requested artifact and its three distinct deliverables are present."""
    text = _read_submission()
    assert text, "voice_launch_kit.md is missing, empty, or not UTF-8 readable"
    assert len(text.split()) >= 120, "the launch kit is too thin to contain a reusable profile and two drafts"
    sections = _sections(text)
    missing = {"profile", "x", "email"} - set(sections)
    assert not missing, f"the launch kit has no distinct section for: {', '.join(sorted(missing))}"
    for name in ("profile", "x", "email"):
        assert sections[name].strip(), f"the {name} section is empty"


def test_product_identity_in_both_drafts():
    """Each standalone launch draft names the correct product."""
    sections = _drafts_or_skip()
    for channel in ("x", "email"):
        normalized = re.sub(r"\s+", " ", sections[channel]).casefold()
        assert "driftline replay" in normalized, (
            f"the {channel} draft does not identify Driftline Replay; it is not usable as standalone launch copy"
        )


def test_quantitative_claims_match_brief():
    """Any numbers used in launch copy preserve the brief's values and boundaries."""
    sections = _drafts_or_skip()
    draft_text = "\n".join((sections["x"], sections["email"]))
    observed = _numbers(draft_text)
    allowed = {15, 37, 41, 84, 200, 620, 2026}
    unsupported = observed - allowed
    assert not unsupported, (
        f"the drafts introduce unsupported numeric claims {sorted(unsupported)}; campaign numbers must come from the brief"
    )
    if observed & {37, 41}:
        assert {37, 41}.issubset(observed), "the 37-of-41 benchmark was quoted without its denominator or numerator"
    if observed & {84, 620}:
        assert {84, 620}.issubset(observed), "the median replay time was detached from its 620-workflow scope"


def test_availability_and_limit_claims_match_brief():
    """Drafts do not contradict launch availability or the human-approval boundary."""
    sections = _drafts_or_skip()
    draft_text = "\n".join((sections["x"], sections["email"]))
    normalized = re.sub(r"[’']", "'", draft_text.casefold())

    for line in normalized.splitlines():
        if "plan" in line and any(word in line for word in ("available", "included", "launch")):
            assert "team" in line and "scale" in line, (
                "a plan-specific availability statement must preserve both Team and Scale from the brief"
            )
        if "add-on" in line or "addon" in line:
            assert not re.search(r"(?:paid|separate|extra|requires?)\s+(?:an?\s+)?(?:add-on|addon)", line), (
                "the brief says no separate add-on is required"
            )

    without_valid_negations = normalized
    for phrase in (
        "does not verify third-party side effects",
        "doesn't verify third-party side effects",
        "cannot verify third-party side effects",
        "does not replace staging",
        "doesn't replace staging",
        "cannot replace staging",
    ):
        without_valid_negations = without_valid_negations.replace(phrase, "")
    contradictions = [
        r"verif(?:y|ies) third-party side effects",
        r"replace(?:s)? staging",
        r"production-connected workflows? (?:need|require)[s]? no (?:human )?approval",
        r"no (?:human )?approval (?:is )?(?:needed|required) for production-connected workflows?",
        r"run[s]? production-connected workflows? without (?:human )?approval",
    ]
    found = [pattern for pattern in contradictions if re.search(pattern, without_valid_negations)]
    assert not found, "the drafts contradict the brief's staging, side-effect, or human-approval limits"
