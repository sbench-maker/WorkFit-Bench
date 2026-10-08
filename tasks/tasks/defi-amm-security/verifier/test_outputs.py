from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


RESULTS = Path(os.environ.get("RESULTS_DIR", "/root/results"))
DATA = Path(os.environ.get("DATA_DIR", "/root/data"))
OUTPUT = RESULTS / "amm_security_review.json"
ENTRYPOINT_RE = re.compile(r"^(POOL|VAULT|ORACLE|ADMIN)-\d+$", re.I)
FINDING_RE = re.compile(r"^[A-Z]{1,8}-\d+$")


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if value is None:
        return ""
    return _norm(value)


def _direct_value(row: dict, aliases: set[str]):
    for key, value in row.items():
        if _norm(key).replace(" ", "_") in aliases:
            return value
    return None


@pytest.fixture(scope="session")
def report() -> dict:
    assert OUTPUT.is_file(), (
        f"missing {OUTPUT}; the deployment team has no audit artifact to review"
    )
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        pytest.fail(f"audit artifact is not readable UTF-8 JSON: {exc}")
    assert isinstance(payload, dict), "the report contract requires one top-level JSON object"
    return payload


def _findings(report: dict) -> list[dict]:
    rows = []
    seen = set()
    id_aliases = {"finding_id", "issue_id", "finding", "code", "id"}
    severity_aliases = {"severity", "risk", "risk_rating", "rating", "priority"}
    for row in _walk(report):
        direct_id = _direct_value(row, id_aliases)
        direct_severity = _direct_value(row, severity_aliases)
        looks_like_id = isinstance(direct_id, str) and bool(FINDING_RE.fullmatch(direct_id.strip()))
        if direct_severity is not None or looks_like_id:
            marker = id(row)
            if marker not in seen:
                seen.add(marker)
                rows.append(row)
    return rows


def _reviewed(report: dict) -> dict[str, dict]:
    aliases = {"entrypoint_id", "scope_id", "entrypoint", "id"}
    rows: dict[str, dict] = {}
    for row in _walk(report):
        raw = _direct_value(row, aliases)
        if isinstance(raw, str) and ENTRYPOINT_RE.fullmatch(raw.strip()):
            rows.setdefault(raw.strip().upper(), row)
    return rows


def _gate_text(report: dict) -> str:
    aliases = {"gate", "gate_decision", "release_gate", "deployment_gate", "decision"}
    for row in _walk(report):
        value = _direct_value(row, aliases)
        if value is not None and not isinstance(value, (dict, list)):
            return _norm(value)
    return ""


def _severity(row: dict) -> int | None:
    raw = _direct_value(row, {"severity", "risk", "risk_rating", "rating", "priority"})
    if raw is None:
        return None
    text = _norm(raw)
    levels = {"informational": 0, "info": 0, "low": 1, "medium": 2, "moderate": 2, "high": 3, "critical": 4}
    for label, score in levels.items():
        if re.search(rf"\b{label}\b", text):
            return score
    return None


def _contains_group(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(_norm(term) in text for term in alternatives)


ISSUES = [
    {
        "name": "swap slippage and expiry",
        "locator": ("swapexactinput",),
        "groups": (("slippage", "amountoutmin", "minimum output", "min output"), ("deadline", "expiry", "expired", "stale")),
        "minimum_severity": 3,
    },
    {
        "name": "fee setter authorization",
        "locator": ("setswapfee",),
        "groups": (("access control", "authorization", "unprivileged", "any account", "only governor"),),
        "minimum_severity": 3,
    },
    {
        "name": "overflow-prone quote arithmetic",
        "locator": ("quoteout",),
        "groups": (("overflow", "intermediate product"), ("muldiv", "full precision", "safe math")),
        "minimum_severity": 2,
    },
    {
        "name": "raw-balance deposit pricing",
        "locator": ("deposit",),
        "groups": (("donation", "inflation", "unsolicited"), ("raw balance", "balanceof", "share denominator", "share price")),
        "minimum_severity": 3,
    },
    {
        "name": "actual-receipt token accounting",
        "locator": ("deposit",),
        "groups": (("fee on transfer", "transfer fee", "actual received", "balance delta", "requested assets"), ("safe transfer", "safeerc20", "return is ignored", "unchecked return", "false return")),
        "minimum_severity": 3,
    },
    {
        "name": "deposit callback reentrancy",
        "locator": ("deposit",),
        "groups": (("reentrancy", "reenter", "callback"), ("guard", "lock", "cei", "half updated", "state transition")),
        "minimum_severity": 3,
    },
    {
        "name": "redeem interaction before effects",
        "locator": ("redeem",),
        "groups": (("reentrancy", "reenter", "cei"), ("before", "stale", "burn", "state")),
        "minimum_severity": 3,
    },
    {
        "name": "public donation synchronization",
        "locator": ("syncassets",),
        "groups": (("donation", "donated", "unsolicited", "raw balance"), ("public", "any caller", "permissionless", "govern")),
        "minimum_severity": 3,
    },
    {
        "name": "spot-price oracle manipulation",
        "locator": ("harbororacle",),
        "groups": (("spot", "single block", "reserve snapshot"), ("manipulation", "flash loan", "flash borrower"), ("twap", "30 minute", "cumulative observation")),
        "minimum_severity": 3,
    },
]


def _matching_findings(report: dict, spec: dict) -> list[dict]:
    candidates = []
    for row in _findings(report):
        text = _text(row)
        if any(_norm(locator) in text for locator in spec["locator"]):
            candidates.append(row)
    return candidates


def test_reviewed_entrypoint_coverage(report: dict):
    expected_rows = json.loads((DATA / "scope_inventory.json").read_text(encoding="utf-8"))
    expected = {row["entrypoint_id"].upper() for row in expected_rows}
    actual = _reviewed(report)
    missing = sorted(expected - set(actual))
    assert not missing, f"scoped entrypoints are missing from the review ledger: {missing}"
    incomplete = []
    for entrypoint_id in expected:
        text = _text(actual[entrypoint_id])
        has_outcome = any(term in text for term in ("finding", "issue", "no material", "no issue", "secure", "verified", "pass", "clean", "acceptable"))
        if not has_outcome:
            incomplete.append(entrypoint_id)
    assert not incomplete, f"entrypoints lack a finding link or explicit no-issue outcome: {sorted(incomplete)}"


@pytest.mark.parametrize("spec", ISSUES, ids=lambda spec: spec["name"])
def test_material_vulnerability_detection(report: dict, spec: dict):
    candidates = _matching_findings(report, spec)
    combined = " ".join(_text(row) for row in candidates)
    assert candidates, f"no finding is tied to the affected path for {spec['name']}"
    missing_groups = [group for group in spec["groups"] if not _contains_group(combined, group)]
    assert not missing_groups, (
        f"the finding for {spec['name']} does not identify the material mechanism and required safety property; "
        f"unmatched concept groups: {missing_groups}"
    )


def test_gate_and_risk_consistency(report: dict):
    gate = _gate_text(report)
    assert any(term in gate for term in ("block", "no go", "do not ship", "stop", "fail")), (
        f"gate is {gate!r}; reachable high/critical paths in the configured launch must block deployment"
    )

    understated = []
    ungraded = []
    for spec in ISSUES:
        candidates = [
            row for row in _matching_findings(report, spec)
            if all(_contains_group(_text(row), group) for group in spec["groups"])
        ]
        if not candidates:
            continue  # Missing or fragmented coverage belongs to detection/reasoning, not severity.
        levels = [_severity(row) for row in candidates]
        levels = [level for level in levels if level is not None]
        if not levels:
            ungraded.append(spec["name"])
        elif max(levels) < spec["minimum_severity"]:
            understated.append(spec["name"])
    assert not ungraded, f"detected risks lack a recognizable severity: {ungraded}"
    assert not understated, f"material risks are understated relative to their configured impact: {understated}"


SAFE_ENTRYPOINTS = [
    "POOL-01", "POOL-02", "POOL-05", "POOL-06", "POOL-07",
    "VAULT-04", "VAULT-05", "VAULT-06", "VAULT-07",
    "ORACLE-02", "ADMIN-01", "ADMIN-02", "ADMIN-03",
]


@pytest.mark.parametrize("entrypoint_id", SAFE_ENTRYPOINTS)
def test_safe_path_discrimination(report: dict, entrypoint_id: str):
    reviewed = _reviewed(report)
    if entrypoint_id not in reviewed:
        return  # Missing scope is scored only by test_reviewed_entrypoint_coverage.
    text = _text(reviewed[entrypoint_id])
    no_issue = any(term in text for term in ("no material", "no issue", "secure", "verified", "pass", "clean", "acceptable"))
    issue_ids = re.findall(r"\b[A-Z]{1,8}-\d+\b", str(reviewed[entrypoint_id]).upper())
    issue_ids = [item for item in issue_ids if not ENTRYPOINT_RE.fullmatch(item)]
    assert no_issue and not issue_ids, (
        f"{entrypoint_id} is a confirmed control in this snapshot but is reported as vulnerable or left ambiguous"
    )
