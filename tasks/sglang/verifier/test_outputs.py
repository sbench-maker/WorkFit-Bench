from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pytest


RESULTS_DIR = Path(os.environ.get("SUBMISSION_DIR", "/root/results"))
DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = RESULTS_DIR / "output.json"
ROUTER = RESULTS_DIR / "router.py"


ALIASES = {
    "ticket_id": ("ticket_id", "ticket", "id"),
    "rule_id": ("rule_id", "rule", "matched_rule"),
    "category": ("category", "queue", "route"),
    "priority": ("priority", "severity"),
    "team": ("team", "assignment_team", "owner_team"),
    "requires_human": ("requires_human", "human_review", "manual_review"),
    "action": ("action", "next_action", "recommended_action"),
    "reason": ("reason", "rationale", "explanation"),
}


EDGE_SUBJECTS = {
    "Mixed billing and security",
    "Mixed outage and feature",
    "Unicode access request",
    "Privacy request",
    "Export request",
    "MFA recovery",
    "Ordinary feedback",
}


def _fold(value: Any) -> str:
    return " ".join(str(value).split()).casefold()


def _mapping_value(mapping: dict[str, Any], aliases: tuple[str, ...], default: Any = None) -> Any:
    by_key = {_fold(key).replace(" ", "_"): value for key, value in mapping.items()}
    for alias in aliases:
        if alias in by_key:
            return by_key[alias]
    return default


def _boolean(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    folded = _fold(value)
    if folded in {"true", "yes", "1", "required"}:
        return True
    if folded in {"false", "no", "0", "not required"}:
        return False
    return None


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _root_list(payload: Any) -> Optional[list[Any]]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("decisions", "routes", "results", "tickets"):
        value = _mapping_value(payload, (key,))
        if isinstance(value, list):
            return value
    return None


def _root_mapping(payload: Any, aliases: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    value = _mapping_value(payload, aliases, {})
    return value if isinstance(value, dict) else {}


@lru_cache(maxsize=1)
def raw_submission() -> tuple[Optional[Any], Optional[str]]:
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"cannot read primary JSON result: {exc}"


@lru_cache(maxsize=1)
def normalized_decisions() -> tuple[list[dict[str, Any]], Optional[str]]:
    payload, error = raw_submission()
    if error:
        return [], error
    rows = _root_list(payload)
    if rows is None:
        return [], "result has no recognizable decision collection"
    normalized = []
    recognized: Counter[str] = Counter()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            return [], f"decision at index {index} is not an object"
        item = {}
        for field, names in ALIASES.items():
            value = _mapping_value(row, names)
            if value is not None:
                recognized[field] += 1
            item[field] = value
        item["ticket_id"] = str(item["ticket_id"] or "").strip().upper()
        item["rule_id"] = _fold(item["rule_id"]).replace(" ", "_")
        item["category"] = _fold(item["category"])
        item["priority"] = str(item["priority"] or "").strip().upper()
        item["team"] = _fold(item["team"]).replace(" ", "-")
        item["requires_human"] = _boolean(item["requires_human"])
        item["action"] = " ".join(str(item["action"] or "").split())
        item["reason"] = " ".join(str(item["reason"] or "").split())
        normalized.append(item)
    missing_schema = [field for field in ALIASES if recognized[field] == 0]
    if missing_schema:
        return [], f"decision collection has no recognizable fields for: {', '.join(missing_schema)}"
    return normalized, None


def decisions_or_skip() -> list[dict[str, Any]]:
    rows, error = normalized_decisions()
    if error or not rows:
        pytest.skip("semantic checks skipped because artifact usability reports the single parse/structure failure")
    return rows


@lru_cache(maxsize=1)
def source_tickets() -> list[dict[str, Any]]:
    with (DATA_DIR / "tickets.jsonl").open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


@lru_cache(maxsize=1)
def policy() -> dict[str, Any]:
    return json.loads((DATA_DIR / "routing_policy.json").read_text(encoding="utf-8"))


def expected_for(ticket: dict[str, Any]) -> dict[str, Any]:
    text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".casefold()
    selected = None
    for rule in policy()["rules"]:
        if any(str(phrase).casefold() in text for phrase in rule["any_phrases"]):
            selected = rule
            break
    if selected is None:
        selected = dict(policy()["fallback"])
        selected.setdefault("id", selected.get("rule_id", "fallback"))
    return {
        "ticket_id": ticket["ticket_id"].upper(),
        "rule_id": _fold(selected.get("id", selected.get("rule_id", "fallback"))).replace(" ", "_"),
        "category": _fold(selected["category"]),
        "priority": str(selected["priority"]).upper(),
        "team": _fold(selected["team"]).replace(" ", "-"),
        "requires_human": bool(selected["requires_human"]),
        "action": " ".join(str(selected["action"]).split()),
    }


def decision_index() -> dict[str, dict[str, Any]]:
    return {row["ticket_id"]: row for row in decisions_or_skip() if row["ticket_id"]}


def test_artifact_usability() -> None:
    """Both requested artifacts must be readable and expose the documented reusable surface."""
    rows, error = normalized_decisions()
    assert error is None, error
    assert rows and all(row["ticket_id"] for row in rows), "result contains no usable ticket decisions"
    assert ROUTER.is_file(), "the reusable /root/results/router.py implementation is missing"
    run = subprocess.run([sys.executable, str(ROUTER), "--help"], capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, f"router CLI does not start successfully: {run.stderr[-500:]}"
    help_text = (run.stdout + run.stderr).casefold()
    for flag in ("--input", "--policy", "--contract", "--output"):
        assert flag in help_text, f"router CLI help is missing documented flag {flag}"


def test_primary_coverage() -> None:
    """Every primary source ticket must appear once, without invented IDs."""
    rows = decisions_or_skip()
    actual = [row["ticket_id"] for row in rows]
    expected = [ticket["ticket_id"].upper() for ticket in source_tickets()]
    duplicates = sorted(ticket_id for ticket_id, count in Counter(actual).items() if count > 1)
    assert not duplicates, f"ticket decisions are duplicated: {duplicates[:12]}"
    assert set(actual) == set(expected), (
        f"primary coverage differs: missing={sorted(set(expected) - set(actual))[:12]}, "
        f"unexpected={sorted(set(actual) - set(expected))[:12]}"
    )


@pytest.mark.parametrize(
    "category",
    ["security", "reliability", "billing", "general"],
)
def test_standard_routing(category: str) -> None:
    """Standard first-match outcomes must agree with all deterministic policy fields."""
    submitted = decision_index()
    tickets = [
        ticket
        for ticket in source_tickets()
        if ticket["subject"] not in EDGE_SUBJECTS and expected_for(ticket)["category"] == category
    ]
    assert tickets, f"fixture does not contain a standard {category} case"
    mismatches = []
    fields = ("rule_id", "category", "priority", "team", "requires_human", "action")
    for ticket in tickets:
        actual = submitted.get(ticket["ticket_id"].upper())
        if actual is None:
            continue  # missing scope is scored only by primary_coverage
        expected = expected_for(ticket)
        wrong = {field: (actual[field], expected[field]) for field in fields if actual[field] != expected[field]}
        if wrong:
            mismatches.append((ticket["ticket_id"], wrong))
    assert not mismatches, f"standard {category} routes contradict the policy: {mismatches[:8]}"


@pytest.mark.parametrize(
    "subject",
    [
        "Mixed billing and security",
        "Mixed outage and feature",
        "Unicode access request",
        "Privacy request",
        "Export request",
        "MFA recovery",
        "Ordinary feedback",
    ],
)
def test_precedence_and_review_edges(subject: str) -> None:
    """Mixed, verification, Unicode, and fallback records must keep their policy-safe outcome."""
    submitted = decision_index()
    tickets = [ticket for ticket in source_tickets() if ticket["subject"] == subject]
    assert tickets, f"fixture does not contain edge subject {subject}"
    mismatches = []
    fields = ("rule_id", "category", "priority", "team", "requires_human", "action")
    for ticket in tickets:
        actual = submitted.get(ticket["ticket_id"].upper())
        if actual is None:
            continue  # missing scope is scored only by primary_coverage
        expected = expected_for(ticket)
        wrong = {field: (actual[field], expected[field]) for field in fields if actual[field] != expected[field]}
        if wrong:
            mismatches.append((ticket["ticket_id"], wrong))
    assert not mismatches, f"edge routes for {subject} are unsafe or inconsistent: {mismatches[:8]}"


def test_summary_consistency() -> None:
    """Submitted summary totals must reconcile with the normalized detail decisions."""
    rows = decisions_or_skip()
    payload, _ = raw_submission()
    summary = _root_mapping(payload, ("summary", "stats", "totals"))
    assert summary, "result is missing a recognizable summary object"
    expected_category = Counter(row["category"] for row in rows)
    expected_priority = Counter(row["priority"] for row in rows)
    expected_human = sum(row["requires_human"] is True for row in rows)
    processed = _number(_mapping_value(summary, ("processed", "count", "total")))
    human = _number(_mapping_value(summary, ("human_review_count", "manual_review_count", "requires_human")))
    categories = _mapping_value(summary, ("by_category", "categories", "category_counts"), {})
    priorities = _mapping_value(summary, ("by_priority", "priorities", "priority_counts"), {})
    norm_categories = {_fold(key): int(value) for key, value in categories.items()} if isinstance(categories, dict) else {}
    norm_priorities = {str(key).upper(): int(value) for key, value in priorities.items()} if isinstance(priorities, dict) else {}
    assert processed == len(rows), f"summary processed={processed}, but detail contains {len(rows)} decisions"
    assert norm_categories == dict(expected_category), "category summary does not reconcile with decisions"
    assert norm_priorities == dict(expected_priority), "priority summary does not reconcile with decisions"
    assert human == expected_human, f"human-review summary is {human}, expected {expected_human} from detail"


def test_constrained_batch_and_prefix_reuse(tmp_path: Path) -> None:
    """The delivered CLI must actually execute constrained batching with shared-prefix reuse."""
    if not ROUTER.is_file():
        pytest.skip("runtime check skipped because artifact usability reports the missing router once")
    rerun_output = tmp_path / "rerun.json"
    trace = tmp_path / "runtime_trace.json"
    env = dict(os.environ)
    env["SGLANG_TRACE_PATH"] = str(trace)
    run = subprocess.run(
        [
            sys.executable,
            str(ROUTER),
            "--input",
            str(DATA_DIR / "holdout_tickets.jsonl"),
            "--policy",
            str(DATA_DIR / "routing_policy.json"),
            "--contract",
            str(DATA_DIR / "output_contract.json"),
            "--output",
            str(rerun_output),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, f"router failed on the supplied rerun batch: {run.stderr[-800:]}"
    assert trace.is_file(), "offline runtime produced no batch trace; constrained run evidence is unavailable"
    observed = json.loads(trace.read_text(encoding="utf-8"))
    expected_count = sum(1 for line in (DATA_DIR / "holdout_tickets.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
    assert observed.get("requests") == expected_count, "runtime trace request count does not match the rerun batch"
    assert observed.get("constrained_requests") == expected_count, "not every rerun request used a JSON schema constraint"
    assert observed.get("schema_validation_failures") == 0, "the constrained rerun recorded schema validation failures"
    assert set(observed.get("constraint_kinds", [])) == {"json_schema"}, "rerun used an unconstrained generation path"
    assert observed.get("cache_hit_chars", 0) > 0, "rerun did not reuse any shared prompt prefix"
    assert observed.get("cache_hit_rate", 0.0) >= 0.70, (
        f"observed cache-hit rate {observed.get('cache_hit_rate')} is too low for the shared policy-first batch"
    )
    rerun = json.loads(rerun_output.read_text(encoding="utf-8"))
    rerun_rows = _root_list(rerun)
    assert isinstance(rerun_rows, list) and len(rerun_rows) == expected_count, "rerun output does not cover its input batch"
