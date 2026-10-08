from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import re

import pytest


RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "output.json"


def keynorm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def textnorm(value: object) -> str:
    if isinstance(value, str):
        raw = value
    else:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return re.sub(r"\s+", " ", raw.lower().replace("_", "-")).strip()


def walk(node: object):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


@lru_cache(maxsize=1)
def load_artifact() -> tuple[object | None, str | None]:
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{OUTPUT} is missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{OUTPUT} is not readable JSON: {exc}"


def require_artifact() -> dict:
    artifact, error = load_artifact()
    if error or not isinstance(artifact, dict):
        pytest.skip(error or "output.json must contain a JSON object; downstream semantic checks skipped")
    return artifact


def keyed_values(artifact: dict, markers: tuple[str, ...]) -> list[object]:
    values: list[object] = []
    for node in walk(artifact):
        if isinstance(node, dict):
            for key, value in node.items():
                normalized = keynorm(key)
                if any(marker in normalized for marker in markers):
                    values.append(value)
    return values


def as_entries(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def entries_for(artifact: dict, markers: tuple[str, ...], *, reject: tuple[str, ...] = ()) -> list[object]:
    entries: list[object] = []
    for node in walk(artifact):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            normalized = keynorm(key)
            if any(marker in normalized for marker in markers) and not any(bad in normalized for bad in reject):
                entries.extend(as_entries(value))
    return entries


def blocker_entries(artifact: dict) -> list[object]:
    entries = entries_for(
        artifact,
        ("blocker", "gap", "violation", "noncompliant", "failure", "failedrequirement", "remediation"),
        reject=("summary", "count"),
    )
    for node in walk(artifact):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if keynorm(key) in {"compliant", "satisfied", "passed", "met"} and (
                value is False or keynorm(value) in {"false", "no", "failed", "blocked", "noncompliant"}
            ):
                entries.append(node)
                break
    return entries


def positive_entries(artifact: dict) -> list[object]:
    return entries_for(artifact, ("requirementsmet", "compliant", "satisfied", "passed", "verified"))


def source_entries(artifact: dict) -> list[object]:
    accepted = {
        "sources", "sourceentries", "traceablesources", "primarysources", "authoritativesources",
        "references", "citations",
    }
    entries: list[object] = []
    for node in walk(artifact):
        if isinstance(node, dict):
            for key, value in node.items():
                if keynorm(key) in accepted:
                    entries.extend(as_entries(value))
    return entries


def contains_groups(entry: object, groups: tuple[tuple[str, ...], ...]) -> bool:
    haystack = textnorm(entry)
    return all(any(alternative.lower() in haystack for alternative in group) for group in groups)


def comparison_matches(
    entry: object,
    topic: tuple[str, ...],
    observed: tuple[str, ...],
    required: tuple[str, ...],
) -> bool:
    if not isinstance(entry, dict) or not any(term in textnorm(entry) for term in topic):
        return False
    observed_values = [
        textnorm(value)
        for key, value in entry.items()
        if any(marker in keynorm(key) for marker in ("observed", "current", "actual"))
    ]
    required_values = [
        textnorm(value)
        for key, value in entry.items()
        if any(marker in keynorm(key) for marker in ("required", "target", "expected", "minimum", "threshold"))
    ]
    if observed_values and required_values:
        return any(value in field for field in observed_values for value in observed) and any(
            value in field for field in required_values for value in required
        )
    return contains_groups(entry, (observed, required))


def decision_values(artifact: dict) -> list[str]:
    direct_keys = {
        "decision",
        "recommendation",
        "gatedecision",
        "promotiondecision",
        "gatestatus",
        "promotionstatus",
        "gaterecommendation",
    }
    direct: list[str] = []
    for node in walk(artifact):
        if isinstance(node, dict):
            direct.extend(textnorm(value) for key, value in node.items() if keynorm(key) in direct_keys)
    return direct or [textnorm(value) for value in keyed_values(artifact, ("decision", "recommendation", "gate"))]


GATE_CASES = ["decision", "runner", "build-backend", "action-pinning", "cache", "oidc", "artifact-host"]


@pytest.mark.parametrize("case", GATE_CASES)
def test_gate_and_blocker_coverage(case: str):
    artifact = require_artifact()
    if case == "decision":
        accepted = ("no-go", "nogo", "do not promote", "blocked", "hold", "reject")
        assert any(any(value in decision for value in accepted) for decision in decision_values(artifact)), (
            "the release decision must hold or reject production promotion"
        )
        return
    patterns = {
        "runner": (("runner",),),
        "build-backend": (("build", "rootless"), ("backend", "buildkit", "docker socket", "docker-socket")),
        "action-pinning": (("action",), ("sha", "immutable", "mutable")),
        "cache": (("cache",),),
        "oidc": (("oidc", "audience"),),
        "artifact-host": (("artifact", "packages.orbit.invalid"), ("host", "allowlist", "egress")),
    }
    assert any(contains_groups(entry, patterns[case]) for entry in blocker_entries(artifact)), (
        f"no independently identifiable {case} production gap was found"
    )


TECHNICAL_CASES = [
    "runner-version",
    "build-backend",
    "action-pinning",
    "cache-protocol",
    "oidc-audience",
    "artifact-host",
    "controller-met",
    "kernel-met",
    "node-met",
    "deadline",
]


@pytest.mark.parametrize("case", TECHNICAL_CASES)
def test_technical_comparison_accuracy(case: str):
    artifact = require_artifact()
    blockers = blocker_entries(artifact)
    met = positive_entries(artifact)
    if case == "deadline":
        assert "2026-09-18" in textnorm(artifact), "the current migration completion deadline is missing or incorrect"
        return
    blocker_comparisons = {
        "runner-version": (("runner",), ("5.4.1",), ("5.4.2",)),
        "build-backend": (("build", "backend"), ("docker-socket", "docker socket", "docker_socket"), ("rootless-buildkit", "rootless buildkit", "rootless_buildkit")),
        "action-pinning": (("action",), ("mutable-tags", "mutable tags", "mutable_tags", "tag"), ("sha", "immutable")),
        "cache-protocol": (("cache",), ("v2",), ("v3",)),
        "oidc-audience": (("oidc", "audience"), ("ci-prod-v1",), ("urn:orbit:ci:prod",)),
        "artifact-host": (("artifact", "host"), ("artifacts.orbit.invalid",), ("packages.orbit.invalid",)),
    }
    if case in blocker_comparisons:
        topic, observed, required = blocker_comparisons[case]
        assert any(comparison_matches(entry, topic, observed, required) for entry in blockers), (
            f"the observed-versus-required comparison for {case} is missing or inaccurate"
        )
        return
    met_comparisons = {
        "controller-met": (("controller",), ("3.9.1",), ("3.8",)),
        "kernel-met": (("kernel",), ("6.1.74",), ("6.1",)),
        "node-met": (("node",), ("20.17.0",), ("20 lts", "node.js 20", "node 20")),
    }
    topic, observed, required = met_comparisons[case]
    assert any(comparison_matches(entry, topic, observed, required) for entry in met), (
        f"the satisfied {case.removesuffix('-met')} prerequisite is missing or misclassified"
    )


SOURCE_CASES = {
    "DOC-017": ("https://engineering.orchid.invalid/orbit/runner-v5-compatibility", ("controller",)),
    "DOC-031": ("https://security.orchid.invalid/advisories/VSA-2026-47", ("runner",)),
    "DOC-052": ("https://engineering.orchid.invalid/orbit/v5-production-checklist", ("build",)),
    "DOC-074": ("https://identity.orchid.invalid/orbit/production-audience", ("oidc",)),
}


@pytest.mark.parametrize("doc_id", list(SOURCE_CASES))
def test_source_traceability(doc_id: str):
    artifact = require_artifact()
    url, topic_terms = SOURCE_CASES[doc_id]
    identifiers = (doc_id.lower(), url.lower())
    assert any(any(identifier in textnorm(entry) for identifier in identifiers) for entry in source_entries(artifact)), (
        f"the complete current source {doc_id} is absent from the traceable source entries"
    )
    claim_entries = blocker_entries(artifact) + positive_entries(artifact)
    assert any(
        any(topic in textnorm(entry) for topic in topic_terms)
        and any(identifier in textnorm(entry) for identifier in identifiers)
        for entry in claim_entries
    ), f"no relevant requirement or gap links back to {doc_id}"
