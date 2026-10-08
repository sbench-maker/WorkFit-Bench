from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_FILE", "/root/results/tech_debt_audit.json"))
MISSING = object()


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _field(row: dict, aliases: tuple[str, ...], default=MISSING):
    wanted = {_token(alias) for alias in aliases}
    for key, value in row.items():
        if _token(key) in wanted:
            return value
    if default is MISSING:
        raise KeyError(f"none of {aliases!r} is present")
    return default


def _deep_field(row: object, aliases: tuple[str, ...], default=None):
    wanted = {_token(alias) for alias in aliases}
    queue = [row]
    while queue:
        current = queue.pop(0)
        if not isinstance(current, dict):
            continue
        for key, value in current.items():
            if _token(key) in wanted:
                return value
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return default


def _section(root: object, aliases: tuple[str, ...]):
    wanted = {_token(alias) for alias in aliases}
    queue = [root]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        if not isinstance(current, dict) or id(current) in seen:
            continue
        seen.add(id(current))
        for key, value in current.items():
            if _token(key) in wanted:
                return value
        for value in current.values():
            if isinstance(value, dict):
                queue.append(value)
    return None


def _records(section: object, *, keyed_label: str | None = None) -> list[dict]:
    rows: list[dict] = []
    if isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                rows.append(dict(item))
    elif isinstance(section, dict):
        looks_like_record = any(
            _token(key) in {
                "title", "name", "finding", "category", "debttype", "impact", "phase", "horizon"
            }
            for key in section
        )
        if looks_like_record:
            rows.append(dict(section))
        else:
            for key, value in section.items():
                if isinstance(value, dict):
                    row = dict(value)
                    if keyed_label and _field(row, (keyed_label,), None) is None:
                        row[keyed_label] = key
                    rows.append(row)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            row = dict(item)
                            if keyed_label and _field(row, (keyed_label,), None) is None:
                                row[keyed_label] = key
                            rows.append(row)
    return rows


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if match:
            return float(match.group())
    return None


def _flatten_text(value: object) -> str:
    parts: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            parts.append(str(key))
            parts.append(_flatten_text(item))
    elif isinstance(value, list):
        parts.extend(_flatten_text(item) for item in value)
    elif value is not None:
        parts.append(str(value))
    return " ".join(parts).casefold().replace("\\", "/")


def _normalized_phase(value: object) -> str | None:
    text = _token(value)
    aliases = {
        "now": {"now", "immediate", "nextsprint", "phase1", "p1", "sprint"},
        "next": {"next", "following30days", "next30days", "phase2", "p2", "month"},
        "later": {"later", "quarterbacklog", "quarter", "phase3", "p3", "backlog"},
    }
    for canonical, values in aliases.items():
        if text in values:
            return canonical
    if "sprint" in text or "immediate" in text:
        return "now"
    if "30day" in text or "month" in text:
        return "next"
    if "quarter" in text or "later" in text or "backlog" in text:
        return "later"
    return None


def _identity(row: dict, index: int) -> str:
    value = _field(row, ("id", "finding_id", "debt_id", "item_id"), None)
    if value is None:
        value = _field(row, ("title", "name", "finding", "issue"), f"finding-{index}")
    return str(value)


def _submission() -> dict:
    if not OUTPUT.is_file():
        return {"error": f"missing {OUTPUT}"}
    try:
        root = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"unreadable JSON: {exc}"}
    if not isinstance(root, dict):
        return {"error": "top-level JSON value is not an object"}
    finding_section = _section(
        root,
        ("findings", "debt_findings", "technical_debt", "technical_debt_items", "audit_items", "items"),
    )
    plan_section = _section(
        root,
        ("phased_remediation_plan", "remediation_plan", "phased_plan", "roadmap", "plan", "phases"),
    )
    findings = _records(finding_section, keyed_label="id")
    plans = _records(plan_section, keyed_label="phase")
    return {"root": root, "findings": findings, "plans": plans}


def _require_submission(state: dict, *, first_case: bool = True) -> None:
    if state.get("error"):
        if first_case:
            pytest.fail(state["error"])
        pytest.skip("artifact parser failure is represented once in this criterion")
    if not state.get("findings"):
        if first_case:
            pytest.fail("no recognizable debt findings")
        pytest.skip("missing finding collection is represented once in this criterion")


def _finding_metrics(row: dict) -> dict[str, float | None]:
    return {
        "impact": _number(_deep_field(row, ("impact", "impact_score"))),
        "risk": _number(_deep_field(row, ("risk", "risk_score"))),
        "effort": _number(_deep_field(row, ("effort", "effort_score", "complexity"))),
        "priority": _number(_deep_field(row, ("priority_score", "priority", "score", "priority_value"))),
        "days": _number(_deep_field(row, ("estimated_engineer_days", "engineer_days", "estimated_days", "days"))),
        "rank": _number(_deep_field(row, ("priority_rank", "rank"))),
    }


def _reference_tokens(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.extend(part.strip() for part in re.split(r"[,;]", value) if part.strip())
    elif isinstance(value, list):
        for item in value:
            values.extend(_reference_tokens(item))
    elif isinstance(value, dict):
        identifier = _field(value, ("id", "finding_id", "debt_id", "item_id", "title", "name"), None)
        if identifier is not None:
            values.append(str(identifier))
        else:
            for key, item in value.items():
                if isinstance(item, bool) and item:
                    values.append(str(key))
                elif isinstance(item, (dict, list)):
                    values.extend(_reference_tokens(item))
    return values


def _plan_assignments(state: dict) -> tuple[dict[str, set[str]], list[str]]:
    findings = state["findings"]
    identities = {_token(_identity(row, index)): _identity(row, index) for index, row in enumerate(findings)}
    titles = {}
    for index, row in enumerate(findings):
        title = _field(row, ("title", "name", "finding", "issue"), None)
        if title:
            titles[_token(title)] = _identity(row, index)
    assignments = {phase: set() for phase in ("now", "next", "later")}
    invalid: list[str] = []
    for index, row in enumerate(findings):
        phase = _normalized_phase(_field(row, ("phase", "target_phase", "timeframe", "horizon"), ""))
        if phase:
            assignments[phase].add(_identity(row, index))
    for plan in state["plans"]:
        phase = _normalized_phase(_field(plan, ("phase", "name", "window", "horizon"), ""))
        if not phase:
            continue
        refs = _field(
            plan,
            ("finding_ids", "findings", "items", "debt_ids", "work_items", "actions", "included_findings"),
            [],
        )
        for raw in _reference_tokens(refs):
            key = _token(raw)
            matched = identities.get(key) or titles.get(key)
            if matched is None:
                invalid.append(raw)
            else:
                assignments[phase].add(matched)
    return assignments, invalid


SCOPE_CASES = [
    (
        "pricing divergence",
        (("service/app/checkout.py", "checkout.py"), ("quote",), ("capture",), ("round", "threshold", "cent")),
    ),
    (
        "unsafe manual release",
        (("service/ops/deploy.sh", "deploy.sh"), ("rollback", "reversible"), ("migration", "health", "fail-fast", "fail safe")),
    ),
    (
        "flaky dispatcher test",
        (("service/tests/test_dispatcher.py", "test_dispatcher.py"), ("random", "flaky", "nondetermin"), ("sleep", "retry")),
    ),
    (
        "unsupported HTTP dependency",
        (("legacy-http", "legacy http"), ("unsupported", "support ended", "end of support"), ("dependency", "client")),
    ),
    (
        "runbook drift",
        (("runbook.md", "operations runbook"), ("8080", "/health"), ("9090", "/ready", "config")),
    ),
    (
        "non-durable dispatch queue",
        (("service/app/dispatcher.py", "dispatcher.py"), ("queue",), ("restart", "durable", "process-local", "global list", "lost")),
    ),
]


@pytest.mark.parametrize("case_index,case", list(enumerate(SCOPE_CASES)), ids=[case[0] for case in SCOPE_CASES])
def test_material_debt_coverage(case_index: int, case):
    state = _submission()
    _require_submission(state, first_case=case_index == 0)
    label, groups = case
    matched = []
    for row in state["findings"]:
        text = _flatten_text(row)
        if all(any(option.casefold() in text for option in group) for group in groups):
            matched.append(row)
    assert matched, f"no single evidence-linked finding covers the material condition: {label}"


def test_score_formula_and_bounds():
    state = _submission()
    _require_submission(state)
    incomplete = []
    wrong = []
    for index, row in enumerate(state["findings"]):
        identity = _identity(row, index)
        metrics = _finding_metrics(row)
        if any(metrics[name] is None for name in ("impact", "risk", "effort", "priority")):
            incomplete.append(identity)
            continue
        impact, risk, effort, priority = (metrics[name] for name in ("impact", "risk", "effort", "priority"))
        if not all(value is not None and 1 <= value <= 5 and float(value).is_integer() for value in (impact, risk, effort)):
            wrong.append(f"{identity}: score outside integer 1..5")
            continue
        expected = (impact + risk) * (6 - effort)
        if abs(priority - expected) > 1e-9:
            wrong.append(f"{identity}: priority {priority:g}, expected {expected:g}")
    assert not incomplete, f"findings missing requested scores: {incomplete}"
    assert not wrong, "; ".join(wrong)


def test_priority_order_is_coherent():
    state = _submission()
    _require_submission(state)
    scored = [(row, _finding_metrics(row)) for row in state["findings"]]
    priorities = [metrics["priority"] for _, metrics in scored]
    assert all(value is not None for value in priorities), "priority order cannot be checked because scores are missing"
    if priorities == sorted(priorities, reverse=True):
        return
    ranks = [metrics["rank"] for _, metrics in scored]
    if all(rank is not None for rank in ranks):
        ordered = [priority for _, priority in sorted(zip(ranks, priorities))]
        assert ordered == sorted(ordered, reverse=True), "explicit priority ranks contradict the calculated scores"
        return
    summary_ids = _deep_field(
        state["root"],
        ("highest_priority_ids", "top_priority_ids", "highest_priorities", "top_priorities"),
        None,
    )
    references = _reference_tokens(summary_ids)
    id_to_priority = {_token(_identity(row, index)): priorities[index] for index, row in enumerate(state["findings"])}
    assert references, "findings are not score-sorted and no explicit rank or top-priority list is provided"
    first = id_to_priority.get(_token(references[0]))
    assert first == max(priorities), "the declared top priority does not have the maximum calculated score"


def test_plan_references_and_coverage():
    state = _submission()
    _require_submission(state)
    assignments, invalid = _plan_assignments(state)
    assert not invalid, f"plan references findings that do not exist: {invalid}"
    assigned = [item for values in assignments.values() for item in values]
    expected = {_identity(row, index) for index, row in enumerate(state["findings"])}
    assert set(assigned) == expected, f"plan does not account for every finding; missing={sorted(expected - set(assigned))}"
    duplicates = sorted(item for item in set(assigned) if assigned.count(item) > 1)
    assert not duplicates, f"findings assigned to multiple phases: {duplicates}"


def test_phase_capacity_limits():
    state = _submission()
    _require_submission(state)
    brief = json.loads((DATA / "audit_brief.json").read_text(encoding="utf-8"))
    capacities = {row["phase"]: float(row["capacity_engineer_days"]) for row in brief["capacity_windows"]}
    assignments, _ = _plan_assignments(state)
    row_by_identity = {_identity(row, index): row for index, row in enumerate(state["findings"])}
    plan_by_phase = {}
    for plan in state["plans"]:
        phase = _normalized_phase(_field(plan, ("phase", "name", "window", "horizon"), ""))
        if phase:
            plan_by_phase[phase] = plan
    failures = []
    for phase, capacity in capacities.items():
        plan = plan_by_phase.get(phase, {})
        declared = _number(_deep_field(plan, ("planned_engineer_days", "total_engineer_days", "planned_days", "total_days")))
        item_days = [_finding_metrics(row_by_identity[item])["days"] for item in assignments[phase] if item in row_by_identity]
        if item_days and all(value is not None for value in item_days):
            computed = sum(value for value in item_days if value is not None)
            if declared is not None and abs(declared - computed) > 1e-9:
                failures.append(f"{phase}: declared {declared:g} days but item estimates sum to {computed:g}")
            used = computed
        else:
            used = declared
        if used is None:
            failures.append(f"{phase}: no reconciliable engineer-day estimate")
        elif used > capacity + 1e-9:
            failures.append(f"{phase}: {used:g} days exceeds {capacity:g}-day debt capacity")
    assert not failures, "; ".join(failures)
