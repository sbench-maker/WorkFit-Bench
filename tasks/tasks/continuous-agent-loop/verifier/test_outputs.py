from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


DATA = Path(os.environ.get("LOOP_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("LOOP_OUTPUT_PATH", "/root/results/recovery_plan.json"))
_MISSING = object()


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _lookup(mapping: Any, aliases: list[str] | tuple[str, ...], default: Any = _MISSING) -> Any:
    if not isinstance(mapping, dict):
        if default is not _MISSING:
            return default
        raise KeyError(aliases)
    normalized = {_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        if _key(alias) in normalized:
            return normalized[_key(alias)]
    if default is not _MISSING:
        return default
    raise KeyError(aliases)


def _find_value(node: Any, aliases: tuple[str, ...]) -> Any:
    wanted = {_key(alias) for alias in aliases}
    if isinstance(node, dict):
        for key, value in node.items():
            if _key(key) in wanted:
                return value
        for value in node.values():
            found = _find_value(value, aliases)
            if found is not _MISSING:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_value(value, aliases)
            if found is not _MISSING:
                return found
    return _MISSING


def _as_list(value: Any, *, id_alias: str = "work_item_id") -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                if _lookup(row, ["work_item_id", "item_id", "unit_id", "id"], default=None) is None:
                    row[id_alias] = key
                rows.append(row)
            elif isinstance(item, (str, int, float, bool)):
                rows.append({id_alias: key, "value": item})
        return rows
    return []


def _split(value: Any) -> list[str]:
    if value is _MISSING or value is None:
        return []
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                scalar = _lookup(item, ["gate_id", "gate", "name", "id", "work_item_id", "item_id"], default=None)
                if scalar is not None:
                    result.append(str(scalar).strip())
            elif str(item).strip():
                result.append(str(item).strip())
        return result
    if isinstance(value, dict):
        return [str(key).strip() for key, enabled in value.items() if enabled not in {False, None, "false", "disabled"}]
    return [part.strip() for part in re.split(r"[,;\n]", str(value)) if part.strip()]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load() -> dict:
    assert OUTPUT.is_file(), f"missing requested recovery plan: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"recovery plan is not readable JSON: {exc}") from exc
    assert isinstance(payload, dict), "recovery plan must be a JSON object"
    return payload


def _item_id(row: Any) -> str | None:
    if isinstance(row, str):
        return row.strip().upper()
    value = _lookup(row, ["work_item_id", "item_id", "unit_id", "card_id", "id"], default=None)
    return None if value is None else str(value).strip().upper()


def _normalize_action(value: Any) -> str:
    token = _key(value)
    if ("isolate" in token or "reducescope" in token) and ("replay" in token or "retry" in token):
        return "isolate_then_replay"
    aliases = {
        "preservemerged": "preserve_merged", "preserve": "preserve_merged", "merged": "preserve_merged",
        "complete": "preserve_merged", "completed": "preserve_merged", "noop": "preserve_merged",
        "resumequeue": "resume_queue", "resume": "resume_queue", "requeue": "resume_queue",
        "continuemergequeue": "resume_queue", "restartqueue": "resume_queue",
        "replayscoped": "replay_scoped", "scopedreplay": "replay_scoped", "replay": "replay_scoped",
        "retry": "replay_scoped", "retryfailingunit": "replay_scoped",
        "humanreview": "human_review", "escalate": "human_review", "manualreview": "human_review",
        "approvalrequired": "human_review", "needsapproval": "human_review",
        "holddependency": "hold_dependency", "waitdependency": "hold_dependency", "hold": "hold_dependency",
        "blockedbydependency": "hold_dependency", "dependencyhold": "hold_dependency",
    }
    return aliases.get(token, token)


def _decisions(payload: dict) -> tuple[list[dict], dict[str, dict]]:
    raw = _find_value(payload, ("unit_actions", "work_item_actions", "decisions", "dispositions", "recovery_actions"))
    rows = _as_list(raw)
    assert rows, "no per-work-item recovery decisions were found"
    assert all(isinstance(row, dict) for row in rows), "work-item decisions must be objects"
    ids = [_item_id(row) for row in rows]
    mapping = {item_id: row for item_id, row in zip(ids, rows) if item_id}
    return rows, mapping


def _decision_action(row: dict) -> str:
    raw = _lookup(row, ["disposition", "action", "decision", "recovery_action", "status"], default=None)
    if raw is None:
        raw = _lookup(row, ["value"], default="")
    return _normalize_action(raw)


def _restart_entries(payload: dict) -> dict[str, dict]:
    restart = _find_value(payload, ("restart_plan", "replay_plan", "restart_schedule", "recovery_schedule"))
    assert restart is not _MISSING, "restart plan is missing"
    entries: list[dict] = []
    if isinstance(restart, dict):
        raw_waves = _lookup(restart, ["waves", "stages", "batches", "restart_waves"], default=None)
        if raw_waves is not None:
            for ordinal, wave in enumerate(_as_list(raw_waves), start=1):
                if not isinstance(wave, dict):
                    continue
                wave_no = _lookup(wave, ["wave", "stage", "batch", "sequence", "number"], default=ordinal)
                raw_items = _lookup(wave, ["items", "work_items", "units", "entries", "jobs"], default=[])
                for item in _as_list(raw_items):
                    if isinstance(item, str):
                        item = {"work_item_id": item}
                    if isinstance(item, dict):
                        row = dict(item)
                        row["__wave__"] = wave_no
                        entries.append(row)
        else:
            raw_entries = _lookup(restart, ["items", "work_items", "units", "entries", "jobs"], default=[])
            entries.extend(_as_list(raw_entries))
    elif isinstance(restart, list):
        entries.extend(_as_list(restart))
    normalized: dict[str, dict] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        item_id = _item_id(row)
        if not item_id:
            continue
        if "__wave__" not in row:
            row["__wave__"] = _lookup(row, ["wave", "stage", "batch", "sequence"], default=None)
        normalized[item_id] = row
    assert normalized, "restart plan contains no identifiable work items"
    return normalized


def _expected() -> dict:
    campaign = json.loads((DATA / "campaign.json").read_text(encoding="utf-8"))
    policy = json.loads((DATA / "operating_policy.json").read_text(encoding="utf-8"))
    catalog = json.loads((DATA / "gate_catalog.json").read_text(encoding="utf-8"))["gates"]
    items = json.loads((DATA / "work_items.json").read_text(encoding="utf-8"))["work_items"]
    attempts = _read_csv("attempts.csv")
    results = _read_csv("eval_results.csv")
    queue = {row["work_item_id"]: row for row in _read_csv("merge_queue.csv")}
    session = json.loads((DATA / "session_state.json").read_text(encoding="utf-8"))
    recovery = policy["recovery_policy"]
    item_by_id = {row["work_item_id"]: row for row in items}
    applicable = {
        item["work_item_id"]: {
            gate["gate_id"] for gate in catalog
            if item["risk"] in gate["required_for_risk"] and gate["blocking"]
        }
        for item in items
    }
    attempts_by_item: dict[str, list[dict]] = defaultdict(list)
    results_by_attempt: dict[str, list[dict]] = defaultdict(list)
    for row in attempts:
        attempts_by_item[row["work_item_id"]].append(row)
    for rows in attempts_by_item.values():
        rows.sort(key=lambda row: int(row["attempt_number"]))
    for row in results:
        results_by_attempt[row["attempt_id"]].append(row)

    actions: dict[str, str] = {}
    for item in items:
        item_id = item["work_item_id"]
        rows = attempts_by_item[item_id]
        if queue[item_id]["state"] == "merged":
            actions[item_id] = "preserve_merged"
            continue
        failures = []
        if rows:
            failures = [
                result for result in results_by_attempt[rows[-1]["attempt_id"]]
                if result["gate_id"] in applicable[item_id] and result["outcome"] == "fail"
            ]
        if len(rows) >= int(recovery["max_total_attempts_per_item"]) and failures:
            actions[item_id] = "human_review"
        elif not rows and any(actions.get(dep) in {"human_review", "hold_dependency"} for dep in item["depends_on"]):
            actions[item_id] = "hold_dependency"
        else:
            signatures = [row["failure_signature"] for row in rows if row["failure_signature"]]
            limit = int(recovery["same_root_cause_limit"])
            repeated = len(signatures) >= limit and len(set(signatures[-limit:])) == 1
            if repeated and failures:
                actions[item_id] = "isolate_then_replay"
            elif failures:
                actions[item_id] = "replay_scoped"
            elif rows and queue[item_id]["state"] == "stalled":
                actions[item_id] = "resume_queue"
            else:
                raise AssertionError(f"fixture classification gap for {item_id}")

    eligible = {item_id for item_id, action in actions.items() if action in {"resume_queue", "replay_scoped", "isolate_then_replay"}}
    merged = {item_id for item_id, action in actions.items() if action == "preserve_merged"}
    latest_merge = max(_parse_time(row["last_updated_at"]) for row in queue.values() if row["state"] == "merged")
    stall_hours = (_parse_time(campaign["as_of"]) - latest_merge).total_seconds() / 3600
    return {
        "campaign": campaign,
        "policy": policy,
        "session": session,
        "items": item_by_id,
        "attempts": attempts_by_item,
        "actions": actions,
        "applicable": applicable,
        "eligible": eligible,
        "merged": merged,
        "stall_hours": stall_hours,
    }


EXPECTED = _expected()


def test_loop_selection_and_freeze() -> None:
    payload = _load()
    mode = _find_value(payload, ("selected_loop_mode", "loop_mode", "mode", "pattern"))
    assert _key(mode) == "continuouspr", "strict protected-PR control requires the continuous-pr loop mode"
    state = _find_value(payload, ("global_state", "loop_state", "campaign_state", "run_state"))
    assert _key(state) in {"frozen", "freeze", "paused", "halted"}, (
        f"campaign state is {state!r}; a {EXPECTED['stall_hours']:.1f}-hour merge stall and repeated failures require a freeze"
    )


def test_work_item_scope_coverage() -> None:
    payload = _load()
    rows, mapping = _decisions(payload)
    expected_ids = set(EXPECTED["actions"])
    observed_ids = [_item_id(row) for row in rows]
    assert None not in observed_ids, "every work-item action needs an identifiable unit ID"
    assert len(observed_ids) == len(set(observed_ids)), "a work item appears more than once in the recovery decisions"
    assert set(mapping) == expected_ids, (
        f"per-unit decision coverage differs: missing={sorted(expected_ids-set(mapping))}, extra={sorted(set(mapping)-expected_ids)}"
    )


@pytest.mark.parametrize("expected_action", [
    "preserve_merged", "resume_queue", "replay_scoped", "isolate_then_replay", "human_review", "hold_dependency"
])
def test_unit_dispositions(expected_action: str) -> None:
    payload = _load()
    _, mapping = _decisions(payload)
    expected_ids = {item_id for item_id, action in EXPECTED["actions"].items() if action == expected_action}
    actual_ids = {
        item_id for item_id, row in mapping.items()
        if _decision_action(row) == expected_action
    }
    assert actual_ids == expected_ids, (
        f"{expected_action} decisions do not follow the frozen attempts, gates, queue, and dependency policy: "
        f"expected={sorted(expected_ids)}, actual={sorted(actual_ids)}"
    )


def test_restart_membership_and_dependency_waves() -> None:
    payload = _load()
    entries = _restart_entries(payload)
    assert set(entries) == EXPECTED["eligible"], (
        f"restart scope must contain exactly the resumable/replayable units; missing={sorted(EXPECTED['eligible']-set(entries))}, "
        f"extra={sorted(set(entries)-EXPECTED['eligible'])}"
    )
    waves: dict[str, int] = {}
    for item_id, row in entries.items():
        raw = row.get("__wave__")
        try:
            waves[item_id] = int(raw)
        except (TypeError, ValueError):
            raise AssertionError(f"restart entry {item_id} has no numeric wave/stage")
    assert min(waves.values()) >= 1, "restart waves must be positive"
    for item_id, wave in waves.items():
        for dependency in EXPECTED["items"][item_id]["depends_on"]:
            if dependency in EXPECTED["merged"]:
                continue
            assert dependency in waves and waves[dependency] < wave, (
                f"{item_id} is scheduled before or with unresolved dependency {dependency}"
            )


def test_restart_gate_scope_and_budget() -> None:
    payload = _load()
    entries = _restart_entries(payload)
    _, decisions = _decisions(payload)
    for item_id, row in entries.items():
        raw_gates = _lookup(row, ["required_gates", "gates", "quality_gates", "checks"], default=None)
        if raw_gates is None and item_id in decisions:
            raw_gates = _lookup(decisions[item_id], ["required_gates", "gates", "quality_gates", "checks"], default=None)
        observed = {_key(gate) for gate in _split(raw_gates)}
        expected = {_key(gate) for gate in EXPECTED["applicable"][item_id]}
        assert observed == expected, f"{item_id} must rerun exactly its applicable blocking gates"
    restart = _find_value(payload, ("restart_plan", "replay_plan", "restart_schedule", "recovery_schedule"))
    planned = _find_value(restart, ("planned_cost_credits", "planned_cost", "estimated_cost", "cost_credits"))
    limit = _find_value(restart, ("budget_limit_credits", "budget_limit", "restart_budget", "budget_credits"))
    expected_cost = sum(EXPECTED["items"][item_id]["estimated_replay_cost_credits"] for item_id in EXPECTED["eligible"])
    assert float(planned) == expected_cost, f"restart cost should reconcile to {expected_cost} credits"
    assert float(limit) == EXPECTED["policy"]["recovery_policy"]["restart_budget_credits"], "plan uses the wrong restart reserve"
    assert float(planned) <= float(limit), "planned recovery exceeds the frozen restart budget"


def test_bounded_controls_and_checkpoint() -> None:
    payload = _load()
    controls = _find_value(payload, ("controls", "recovery_controls", "limits", "guardrails"))
    assert isinstance(controls, dict), "runner controls are missing"
    max_total = _find_value(controls, ("max_total_attempts_per_item", "max_attempts", "attempt_limit"))
    repeat_limit = _find_value(controls, ("same_root_cause_limit", "same_failure_limit", "repeat_limit"))
    hard_stops = _find_value(controls, ("hard_stop_gates", "stop_gates", "fatal_gates"))
    assert int(max_total) == 3, "runner must enforce the three-attempt total cap"
    assert int(repeat_limit) == 2, "runner must stop an unchanged root cause at the second occurrence"
    assert {_key(value) for value in _split(hard_stops)} == {"security", "migrationroundtrip"}, "hard-stop gate controls are incomplete"

    entries = _restart_entries(payload)
    for item_id, row in entries.items():
        raw = _lookup(row, ["max_additional_attempts", "remaining_attempts", "retry_allowance", "attempts_allowed"], default=None)
        expected_remaining = 3 - len(EXPECTED["attempts"][item_id])
        assert int(raw) == expected_remaining, f"{item_id} has the wrong bounded replay allowance"

    checkpoint = _find_value(payload, ("checkpoint", "resume_checkpoint", "session_checkpoint", "persisted_state"))
    assert isinstance(checkpoint, dict), "recovery state lacks a resumable checkpoint"
    snapshot = _find_value(checkpoint, ("source_snapshot_id", "snapshot_id", "resume_from_snapshot"))
    generation = _find_value(checkpoint, ("resume_generation", "next_generation", "generation"))
    status = _find_value(checkpoint, ("status", "state", "loop_state"))
    preserved = _find_value(checkpoint, ("preserved_work_items", "completed_work_items", "merged_items", "completed"))
    assert str(snapshot) == EXPECTED["campaign"]["snapshot_id"], "checkpoint is not bound to the supplied frozen snapshot"
    assert int(generation) == int(EXPECTED["session"]["last_generation"]) + 1, "resume generation must continue from persisted state"
    assert _key(status) in {"frozen", "freeze", "paused", "halted"}, "checkpoint must persist the freeze before restart"
    assert {value.upper() for value in _split(preserved)} == EXPECTED["merged"], "checkpoint does not preserve every merged unit"
