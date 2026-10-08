from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


DATA = Path(os.environ.get("PROMPT_REVIEW_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("PROMPT_REVIEW_OUTPUT_PATH", "/root/results/prompt_review.md"))


def _read_report() -> tuple[str, str | None]:
    if not OUTPUT.is_file():
        return "", f"requested report is missing: {OUTPUT}"
    try:
        text = OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "", f"prompt_review.md is not readable UTF-8 text: {exc}"
    return text, None


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _has_any(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in alternatives)


def _largest_prompt_block(text: str) -> str:
    blocks = re.findall(r"```(?:text|prompt|markdown|md)?\s*\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates = [block for block in blocks if _has_any(block, (r"customer[_ ]message", r"retrieved[_ ]notes"))]
    if candidates:
        return max(candidates, key=len)

    start_patterns = (
        r"(?im)^#{1,6}\s+.*(?:replacement|improved|enhanced|proposed|production[- ]ready).*prompt.*$",
        r"(?im)^#{1,6}\s+.*deployment prompt.*$",
        r"(?im)^.*(?:replacement|improved|enhanced)\s+(?:version|prompt)\s*:\s*$",
    )
    starts = []
    for pattern in start_patterns:
        match = re.search(pattern, text)
        if match:
            starts.append(match.end())
    if not starts:
        return ""
    start = min(starts)
    tail = text[start:]
    end = re.search(r"(?im)^#{1,6}\s+.*(?:tests?|validation|release gate|rollout).*$", tail)
    return tail[: end.start()] if end else tail


def _without_fenced_blocks_and_test_sections(text: str) -> str:
    """Keep diagnostic prose while excluding controls/tests that could mimic a finding."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    lines = text.splitlines()
    kept: list[str] = []
    skipping_level: int | None = None
    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).casefold()
            if skipping_level is not None and level <= skipping_level:
                skipping_level = None
            if re.search(r"\b(?:tests?|validation|release gate|rollout)\b", title):
                skipping_level = level
                continue
        if skipping_level is None:
            kept.append(line)
    return "\n".join(kept)


def test_artifact_usability() -> None:
    """The requested Markdown report is readable and contains its three requested deliverables."""
    text, error = _read_report()
    assert error is None, error
    assert len(text.strip()) >= 1200, "report is too short to contain findings, a replacement prompt, and focused tests"
    normalized = _normalized(text)
    assert _has_any(normalized, (r"risk[- ]rank", r"priority", r"severity", r"critical.*finding")), (
        "the report does not expose risk ranking or severity, so release blockers are not identifiable"
    )
    assert len(_largest_prompt_block(text)) >= 700, (
        "no substantial replacement prompt could be identified; recommendations alone are not deployment-ready"
    )
    assert _has_any(normalized, (r"test recommendations?", r"pre[- ]release tests?", r"test cases?", r"validation (?:plan|exercises|suite)", r"regression (?:tests?|set)")), (
        "focused test recommendations are not identifiable in the report"
    )


RISK_CASES = [
    (
        "injection_trust_boundary",
        "prompt_injection",
        (r"prompt injection", r"untrusted.*(?:instruction|authority)", r"override.*instruction"),
        (r"retrieved[_ ]notes?", r"customer[_ ]message", r"ticket text"),
    ),
    (
        "unauthorized_actions",
        "high_impact_action",
        (r"(?:execute|call).*(?:refund|close[_ ]account|disable[_ ]login)", r"high[- ]impact action", r"account action"),
        (r"human approval", r"authorization", r"recommend[- ]only"),
    ),
    (
        "privacy_and_leakage",
        "privacy_exfiltration",
        (r"privacy", r"sensitive.*(?:data|profile)", r"data (?:exposure|leak)", r"personal data"),
        (r"email", r"phone", r"internal (?:notes|policy)", r"payment"),
    ),
    (
        "biased_urgency",
        "bias_consistency",
        (r"bias", r"fairness", r"discriminat", r"unequal"),
        (r"vip", r"grammar", r"language", r"non[- ]native"),
    ),
    (
        "imminent_harm_handling",
        "safety_escalation",
        (r"self[- ]harm", r"violence", r"imminent harm", r"safety escalation"),
        (r"critical", r"trained.*human", r"immediate.*review", r"under[- ]escalat"),
    ),
    (
        "invalid_input_and_output_contract",
        "malformed_input",
        (r"malformed", r"oversized", r"input validation", r"output.*(?:nondetermin|unstable|contract)"),
        (r"json", r"needs[_ ]review", r"invent", r"guess", r"length"),
    ),
]


@pytest.mark.parametrize("label,kind,concepts,impact_terms", RISK_CASES, ids=[row[0] for row in RISK_CASES])
def test_risk_diagnosis(label: str, kind: str, concepts: tuple[str, ...], impact_terms: tuple[str, ...]) -> None:
    """Each material, fixture-grounded failure mode is explicitly diagnosed with relevant evidence."""
    text, error = _read_report()
    assert error is None, error
    diagnostic_text = _without_fenced_blocks_and_test_sections(text)
    normalized = _normalized(diagnostic_text)
    assert _has_any(normalized, concepts), f"{label} is not identified as a risk"
    assert _has_any(normalized, impact_terms), f"{label} lacks the task-specific impact or control needed to make the diagnosis useful"


SAFEGUARD_CASES = [
    (
        "fixed_trust_boundary",
        (r"customer[_ ]message.*untrusted", r"untrusted.*customer[_ ]message"),
        (r"retrieved[_ ]notes.*untrusted", r"untrusted.*retrieved[_ ]notes"),
    ),
    (
        "injection_resistance",
        (r"(?:ignore|do not follow|never follow).*(?:instruction|command).*(?:inside|in|from)",),
        (r"(?:reveal|quote|expose).*(?:system|internal policy|hidden)", r"(?:system|internal policy|hidden).*(?:reveal|quote|expose)"),
    ),
    (
        "privacy_minimization",
        (r"never output.*(?:email|phone|address|payment)", r"(?:email|phone|address|payment).*(?:redact|never output|do not output)"),
        (r"(?:minimum|minimiz|redact).*(?:facts|data|summary)", r"output only.*fields"),
    ),
    (
        "fair_classification",
        (r"do not use.*(?:vip|language|grammar)", r"(?:vip|language|grammar).*(?:not|never).*(?:urgency|queue|classification)"),
        (r"(?:safety|time sensitivity|scope|compromise).*(?:urgency|classif)", r"urgency.*(?:safety|time sensitivity|scope|compromise)"),
    ),
    (
        "human_action_gate",
        (r"(?:never|cannot|do not).*(?:execute|authorize).*(?:refund|account|financial|identity|login)", r"recommend[- ]only"),
        (r"requires[_ ]human[_ ]approval", r"human approval"),
    ),
    (
        "safety_escalation_precision",
        (r"(?:self[- ]harm|violence).*(?:critical|immediate|safety_escalation)", r"critical.*(?:self[- ]harm|violence)"),
        (r"(?:fictional|negated|merely angry|false).*(?:not|without|avoid).*(?:escalat|imminent)", r"do not escalate.*(?:fictional|negated|angry)"),
    ),
    (
        "structured_output",
        (r"exactly one.*json", r"one valid json", r"json object.*no.*prose"),
        (r"ticket_id", r"queue.*urgency.*summary"),
    ),
    (
        "invalid_input_behavior",
        (r"(?:missing|blank|malformed|over[- ]limit|oversized).*(?:invalid|needs[_ ]review|do not guess)",),
        (r"needs[_ ]review", r"do not (?:guess|invent)"),
    ),
]


@pytest.mark.parametrize("label,first,second", SAFEGUARD_CASES, ids=[row[0] for row in SAFEGUARD_CASES])
def test_replacement_safeguards(label: str, first: tuple[str, ...], second: tuple[str, ...]) -> None:
    """The replacement prompt contains the controls needed for safe, deterministic production behavior."""
    text, error = _read_report()
    assert error is None, error
    replacement = _normalized(_largest_prompt_block(text))
    assert replacement, "replacement prompt could not be located"
    assert _has_any(replacement, first), f"replacement prompt is missing the first part of the {label} control"
    assert _has_any(replacement, second), f"replacement prompt is missing the second part of the {label} control"
