from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import pytest


OUTPUT = Path(os.environ.get("SUBMISSION_PATH", "/root/results/performance_assessment.json"))
FAIL_WORDS = ("breach", "fail", "violat", "not met", "noncompliant", "non-compliant", "missed")
PASS_WORDS = ("pass", "met", "compliant", "satisfied", "within target")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?")

EXPECTED = {
    "REQ-BROWSE-P95": (False, 322.0),
    "REQ-BROWSE-ERROR": (True, 0.8),
    "REQ-BROWSE-COMPLETION": (True, 98.2),
    "REQ-CHECKOUT-P95": (False, 920.0),
    "REQ-CHECKOUT-ERROR": (False, 2.8),
    "REQ-CHECKOUT-COMPLETION": (False, 93.0),
    "REQ-INVENTORY-QUEUE": (False, 12.4),
    "REQ-BURST-CHECKOUT": (False, 1480.0),
    "REQ-FAILOVER-CHECKOUT": (False, 1180.0),
}


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _flatten(value: object) -> str:
    parts: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                parts.append(str(key))
                visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)
        elif node is not None:
            parts.append(str(node))

    visit(value)
    return _norm(" ".join(parts))


def _scalar_count(value: object) -> int:
    if isinstance(value, dict):
        return len(value) + sum(_scalar_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_scalar_count(item) for item in value)
    return 1


def _containers(value: object, path: tuple[str, ...] = ()):
    if isinstance(value, (dict, list)):
        yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _containers(item, path + (_norm(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _containers(item, path + (str(index),))


def _contexts_for_id(payload: object, requirement_id: str) -> list[tuple[tuple[str, ...], object]]:
    wanted = _norm(requirement_id)
    matches = [
        (path, node)
        for path, node in _containers(payload)
        if wanted in _flatten(node) or wanted in path
    ]
    return sorted(matches, key=lambda item: _scalar_count(item[1]))


def _numbers(value: object) -> list[float]:
    found: list[float] = []

    def visit(node: object) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            found.append(float(node))
        elif isinstance(node, str):
            found.extend(float(match.group()) for match in NUMBER_RE.finditer(node))
        elif isinstance(node, dict):
            for item in node.values():
                visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    return found


@pytest.fixture(scope="session")
def submission():
    if not OUTPUT.is_file():
        return None, f"missing requested artifact: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"requested artifact is not readable JSON: {exc}"
    if not isinstance(payload, (dict, list)) or not payload:
        return None, "requested artifact must be a non-empty JSON object or array"
    return payload, None


def _usable_payload(submission):
    payload, error = submission
    if error:
        pytest.skip("artifact readability is scored only by test_artifact_usability")
    return payload


@pytest.mark.parametrize("requirement_id", list(EXPECTED))
def test_requirement_outcomes(submission, requirement_id):
    """All true breaches are identified, and met requirements are not called breaches."""
    payload = _usable_payload(submission)
    is_met, _ = EXPECTED[requirement_id]
    contexts = _contexts_for_id(payload, requirement_id)
    if not contexts:
        assert is_met, f"breached requirement {requirement_id} is missing from the assessment"
        return
    focused = [(path, node) for path, node in contexts if _scalar_count(node) <= 80]
    assert focused, f"{requirement_id} appears only in an undifferentiated top-level block"
    context_texts = [_flatten(node) for _, node in focused]
    explicit_statuses = []
    for _, node in focused:
        if isinstance(node, dict):
            for key in ("status", "outcome", "result", "classification"):
                if key in node:
                    explicit_statuses.append(_norm(node[key]))
    called_failed = any(any(word in status for word in FAIL_WORDS) for status in explicit_statuses)
    called_passed = any(any(word in status for word in PASS_WORDS) for status in explicit_statuses)
    if not explicit_statuses:
        called_failed = any(any(word in context for word in FAIL_WORDS) for context in context_texts)
        called_passed = any(any(word in context for word in PASS_WORDS) for context in context_texts)
    if is_met:
        assert not called_failed, f"met requirement {requirement_id} is incorrectly classified as breached"
    else:
        assert called_failed, (
            f"{requirement_id} appears but is not clearly classified as breached"
        )


@pytest.mark.parametrize(
    "requirement_id,expected_actual",
    [(req_id, actual) for req_id, (is_met, actual) in EXPECTED.items() if not is_met],
)
def test_breach_quantitative_evidence(submission, requirement_id, expected_actual):
    """Each breach carries the measured value that supports the decision."""
    payload = _usable_payload(submission)
    contexts = _contexts_for_id(payload, requirement_id)
    assert contexts, f"no evidence context found for {requirement_id}"
    candidate_contexts = [node for _, node in contexts if _scalar_count(node) <= 80]
    assert candidate_contexts, f"{requirement_id} is mentioned only in an undifferentiated top-level block"
    assert any(
        any(math.isclose(number, expected_actual, rel_tol=0, abs_tol=0.11) for number in _numbers(node))
        for node in candidate_contexts
    ), f"{requirement_id} does not include its measured value {expected_actual}"


@pytest.mark.parametrize(
    "terms,expected_ranges,label",
    [
        (("checkout-api", "order-db"), ((9.5, 10.5), (292.0, 300.5)), "checkout/database saturation"),
        (("inventory-worker",), ((45.5, 50.5), (11.7, 13.1)), "queue-age scaling blind spot"),
        (("catalog-api",), ((89.5, 94.5), (13.5, 18.5)), "catalog capacity/cache pressure"),
    ],
)
def test_bottleneck_evidence(submission, terms, expected_ranges, label):
    """The main bottlenecks are tied to the decisive service-level telemetry."""
    payload = _usable_payload(submission)
    candidates = []
    for _, node in _containers(payload):
        if _scalar_count(node) > 100:
            continue
        text = _flatten(node)
        if all(term in text for term in terms):
            candidates.append(node)
    assert candidates, f"no focused evidence block found for {label}"
    assert any(
        all(
            any(lower <= number <= upper for number in _numbers(node))
            for lower, upper in expected_ranges
        )
        for node in candidates
    ), f"{label} is not supported by telemetry in the expected observed ranges {expected_ranges}"
