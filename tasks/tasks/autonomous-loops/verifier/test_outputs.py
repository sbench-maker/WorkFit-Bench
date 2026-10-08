from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS / "output.json"


def nk(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def split_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[|,;\n]", value) if part.strip()]
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            if isinstance(item, dict):
                candidate = field(item, ["unit_id", "work_unit_id", "id", "name", "gate", "type", "stage", "path"])
                if candidate is not None:
                    out.extend(split_values(candidate))
            else:
                out.extend(split_values(item))
        return out
    return [str(value)]


def field(obj: object, aliases: list[str], default=None):
    if not isinstance(obj, dict):
        return default
    wanted = {nk(alias) for alias in aliases}
    for key, value in obj.items():
        if nk(key) in wanted:
            return value
    return default


def find_value(obj: object, aliases: list[str]):
    wanted = {nk(alias) for alias in aliases}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if nk(key) in wanted:
                return value
        for value in obj.values():
            found = find_value(value, aliases)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_value(value, aliases)
            if found is not None:
                return found
    return None


def walk(obj: object):
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def load_submission() -> tuple[dict | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"{OUTPUT} is missing"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{OUTPUT} is not readable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "output.json must contain a JSON object"
    return payload, None


def require_submission() -> dict:
    payload, error = load_submission()
    assert error is None, error
    assert payload is not None
    return payload


def load_source() -> tuple[dict[str, dict], dict]:
    with (DATA / "work_units.csv").open(encoding="utf-8", newline="") as handle:
        units = {row["unit_id"]: row for row in csv.DictReader(handle)}
    policy = json.loads((DATA / "operating_policy.json").read_text(encoding="utf-8"))
    return units, policy


def record_id(record: dict) -> str | None:
    value = field(record, ["unit_id", "work_unit_id", "workitem_id", "id"])
    if value is None:
        return None
    match = re.search(r"WU[-_ ]?\d+", str(value), re.I)
    if not match:
        return None
    number = int(re.search(r"\d+", match.group()).group())
    return f"WU-{number:02d}"


def extract_units(root: dict) -> dict[str, dict]:
    candidates: list[dict[str, dict]] = []
    for node in walk(root):
        found: dict[str, dict] = {}
        if isinstance(node, list):
            for item in node:
                if isinstance(item, dict) and (uid := record_id(item)):
                    found[uid] = item
        elif isinstance(node, dict):
            for key, value in node.items():
                match = re.fullmatch(r"WU[-_ ]?(\d+)", str(key), re.I)
                if match and isinstance(value, dict):
                    uid = f"WU-{int(match.group(1)):02d}"
                    found[uid] = {"unit_id": uid, **value}
        if found:
            candidates.append(found)
    return max(candidates, key=len, default={})


def canonical_stage(value: str) -> str:
    token = nk(value)
    aliases = {
        "implementation": "implement", "coding": "implement",
        "tests": "test", "testing": "test", "verify": "test", "verification": "test",
        "planning": "plan", "researching": "research",
        "prdreview": "spec_review", "requirementsreview": "spec_review", "specreview": "spec_review",
        "codereview": "code_review", "review": "code_review",
        "reviewfix": "review_fix", "fixreview": "review_fix", "addressreview": "review_fix",
        "finalreview": "final_review",
    }
    return aliases.get(token, token)


def extract_tier_pipelines(root: dict) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    tiers = {"trivial", "small", "medium", "large"}
    for node in walk(root):
        if isinstance(node, dict):
            tier = field(node, ["tier", "complexity_tier", "name"])
            stages = field(node, ["stages", "pipeline", "steps", "quality_stages"])
            if isinstance(tier, str) and nk(tier) in tiers and stages is not None:
                result[nk(tier)] = [canonical_stage(v) for v in split_values(stages)]
            for key, value in node.items():
                if nk(key) in tiers:
                    candidate = field(value, ["stages", "pipeline", "steps", "quality_stages"], value)
                    if isinstance(candidate, (list, str)):
                        result[nk(key)] = [canonical_stage(v) for v in split_values(candidate)]
    return result


def extract_waves(root: dict, units: dict[str, dict]) -> dict[str, int]:
    assigned: dict[str, int] = {}
    for uid, record in units.items():
        value = field(record, ["wave", "wave_id", "layer", "batch", "parallel_group"])
        if isinstance(value, (int, float)) or (isinstance(value, str) and re.search(r"\d+", value)):
            assigned[uid] = int(re.search(r"\d+", str(value)).group())
    grouped = find_value(root, ["waves", "execution_waves", "layers", "batches", "parallel_plan"])
    if isinstance(grouped, list):
        for index, row in enumerate(grouped):
            if isinstance(row, dict):
                raw_wave = field(row, ["wave", "wave_id", "layer", "batch", "index"], index)
                match = re.search(r"\d+", str(raw_wave))
                wave = int(match.group()) if match else index
                members = field(row, ["unit_ids", "units", "work_units", "members", "items"])
            elif isinstance(row, list):
                wave, members = index, row
            else:
                continue
            for raw in split_values(members):
                match = re.search(r"WU[-_ ]?(\d+)", raw, re.I)
                if match:
                    assigned[f"WU-{int(match.group(1)):02d}"] = wave
    return assigned


def extract_merge_order(root: dict) -> list[str]:
    value = find_value(root, ["merge_order", "integration_order", "landing_order"])
    if value is None:
        container = find_value(root, ["merge_queue", "merge_plan", "integration_plan"])
        value = field(container, ["order", "sequence", "unit_ids", "units"]) if isinstance(container, dict) else container
    result = []
    for raw in split_values(value):
        match = re.search(r"WU[-_ ]?(\d+)", raw, re.I)
        if match:
            result.append(f"WU-{int(match.group(1)):02d}")
    return result


def expected_merge_order(source: dict[str, dict]) -> list[str]:
    remaining = set(source)
    landed: set[str] = set()
    result = []
    while remaining:
        ready = [uid for uid in remaining if set(split_values(source[uid]["dependencies"])) <= landed]
        assert ready, "fixture dependency graph is cyclic"
        chosen = min(ready, key=lambda uid: int(uid.split("-")[1]))
        result.append(chosen)
        landed.add(chosen)
        remaining.remove(chosen)
    return result


def strings_and_keys(value: object) -> set[str]:
    values: set[str] = set()
    if isinstance(value, str):
        values.update(nk(part) for part in re.split(r"[|,;\n]", value) if part.strip())
    elif isinstance(value, dict):
        for key, item in value.items():
            values.add(nk(key))
            values |= strings_and_keys(item)
    elif isinstance(value, list):
        for item in value:
            values |= strings_and_keys(item)
    return values


def extract_failures(root: dict) -> dict[str, dict]:
    container = find_value(root, ["failure_handling", "failure_policies", "recovery", "recovery_policies", "failure_modes"])
    result: dict[str, dict] = {}
    if isinstance(container, list):
        for item in container:
            if isinstance(item, dict):
                failure_type = field(item, ["failure_type", "type", "failure", "event"])
                if failure_type:
                    result[nk(failure_type)] = item
    elif isinstance(container, dict):
        for key, value in container.items():
            if isinstance(value, dict):
                failure_type = field(value, ["failure_type", "type", "failure", "event"], key)
                result[nk(failure_type)] = value
    return result


def gate_assignments(root: dict, units: dict[str, dict]) -> dict[str, set[tuple[str, str]]]:
    result: dict[str, set[tuple[str, str]]] = defaultdict(set)

    def add(uid: str, gate: object, position: object = "") -> None:
        gate_name = nk(gate)
        encoded_position = ""
        if "beforeimplement" in gate_name or "preimplement" in gate_name:
            encoded_position = "beforeimplement"
        elif "beforemerge" in gate_name or "premerge" in gate_name or "beforelanding" in gate_name:
            encoded_position = "beforemerge"
        if gate_name.startswith("planapproval") or gate_name.startswith("humanplanapproval"):
            gate_name = "planapproval"
        elif gate_name.startswith("rolloutapproval") or gate_name.startswith("humanrolloutapproval"):
            gate_name = "rolloutapproval"
        gate_name = {"planapprovalgate": "planapproval", "humanplanapproval": "planapproval", "rolloutapprovalgate": "rolloutapproval", "humanrolloutapproval": "rolloutapproval"}.get(gate_name, gate_name)
        pos = nk(position) or encoded_position
        pos = {"preimplement": "beforeimplement", "beforeimplementation": "beforeimplement", "premerge": "beforemerge", "beforelanding": "beforemerge"}.get(pos, pos)
        if gate_name:
            result[uid].add((gate_name, pos))

    for uid, record in units.items():
        gates = field(record, ["human_gates", "approval_gates", "gates", "approvals"])
        if isinstance(gates, list):
            for gate in gates:
                if isinstance(gate, dict):
                    add(uid, field(gate, ["gate", "name", "type"]), field(gate, ["position", "timing", "before"]))
                else:
                    raw = str(gate)
                    add(uid, raw, "before_implement" if "plan" in raw.lower() else "before_merge")
        elif gates:
            for raw in split_values(gates):
                add(uid, raw, "before_implement" if "plan" in raw.lower() else "before_merge")

    grouped = find_value(root, ["human_gates", "approval_gates", "human_review_points"])
    if isinstance(grouped, list):
        for row in grouped:
            if not isinstance(row, dict):
                continue
            members = field(row, ["unit_ids", "units", "work_units", "applies_to"])
            gate = field(row, ["gate", "name", "type"])
            position = field(row, ["position", "timing", "before"])
            for raw in split_values(members):
                match = re.search(r"WU[-_ ]?(\d+)", raw, re.I)
                if match:
                    add(f"WU-{int(match.group(1)):02d}", gate, position)
    return result


@pytest.mark.parametrize("aspect", ["coverage", "dependencies_and_files", "waves", "workspaces", "merge_order"])
def test_dag_coverage_parallel_safety_and_merge_order(aspect: str):
    root = require_submission()
    source, policy = load_source()
    units = extract_units(root)
    expected_ids = set(source)
    if aspect == "coverage":
        assert set(units) == expected_ids, f"work-unit coverage differs: expected {sorted(expected_ids)}, got {sorted(units)}"
    elif aspect == "dependencies_and_files":
        assert set(units) == expected_ids, "cannot verify dependencies and file boundaries until every RFC unit is represented"
        for uid, expected in source.items():
            actual_deps = {v.upper().replace("_", "-").replace(" ", "-") for v in split_values(field(units[uid], ["dependencies", "deps", "depends_on", "prerequisites"]))}
            expected_deps = set(split_values(expected["dependencies"]))
            assert actual_deps == expected_deps, f"{uid} dependency set is {actual_deps}, expected {expected_deps}"
            actual_files = set(split_values(field(units[uid], ["file_scope", "planned_files", "files", "paths", "ownership_boundary"])))
            expected_files = set(split_values(expected["planned_files"]))
            assert actual_files == expected_files, f"{uid} file boundary is incomplete or overbroad"
    elif aspect == "waves":
        waves = extract_waves(root, units)
        assert set(waves) == expected_ids, "every RFC unit needs exactly one wave/layer assignment"
        assert len(set(waves.values())) > 1 and any(list(waves.values()).count(w) > 1 for w in set(waves.values())), "the plan does not use any safe parallel wave"
        grouped: dict[int, list[str]] = defaultdict(list)
        for uid, wave in waves.items():
            grouped[wave].append(uid)
        for wave, members in grouped.items():
            assert len(members) <= policy["scheduling"]["max_parallel_agents"], f"wave {wave} exceeds agent capacity"
            touched: set[str] = set()
            for uid in members:
                deps = set(split_values(source[uid]["dependencies"]))
                assert all(waves[dep] < wave for dep in deps), f"{uid} runs before or alongside dependency in wave {wave}"
                files = set(split_values(source[uid]["planned_files"]))
                assert not (files & touched), f"wave {wave} has a shared-file collision for {uid}: {sorted(files & touched)}"
                touched |= files
    elif aspect == "workspaces":
        values = []
        for uid, record in units.items():
            workspace = field(record, ["workspace", "worktree", "branch", "isolated_workspace"])
            if workspace is not None:
                values.append(str(workspace))
        if len(values) == len(expected_ids):
            assert len({nk(v) for v in values}) == len(expected_ids), "work units do not have unique isolated workspaces"
        else:
            pattern = find_value(root, ["workspace_pattern", "worktree_pattern", "isolated_workspace_pattern"])
            assert isinstance(pattern, str) and ("unit" in pattern.lower() or "{" in pattern), "the plan does not define an isolated workspace per work unit"
    else:
        actual = extract_merge_order(root)
        expected = expected_merge_order(source)
        assert actual == expected, f"merge order must follow dependencies and the policy tie-break; expected {expected}, got {actual}"


@pytest.mark.parametrize("uid", [f"WU-{i:02d}" for i in range(1, 13)])
def test_risk_tiers_quality_stages_and_human_gates(uid: str):
    root = require_submission()
    source, policy = load_source()
    units = extract_units(root)
    assert uid in units, f"{uid} is absent, so its risk pipeline cannot be verified"
    points = int(source[uid]["complexity_points"])
    tier_rule = next(rule for rule in policy["tier_rules"] if rule["min_points"] <= points <= rule["max_points"])
    actual_tier = nk(field(units[uid], ["tier", "complexity_tier", "risk_tier"], ""))
    assert actual_tier == nk(tier_rule["tier"]), f"{uid} tier is {actual_tier!r}, expected {tier_rule['tier']}"
    stages = field(units[uid], ["stages", "pipeline", "steps", "quality_stages"])
    actual_stages = [canonical_stage(v) for v in split_values(stages)]
    if not actual_stages:
        actual_stages = extract_tier_pipelines(root).get(actual_tier, [])
    expected_stages = [canonical_stage(v) for v in tier_rule["stages"]]
    assert actual_stages == expected_stages, f"{uid} quality stages are {actual_stages}, expected {expected_stages}"

    gates = gate_assignments(root, units).get(uid, set())
    expected_gates = set()
    if points >= 8:
        expected_gates.add(("planapproval", "beforeimplement"))
    if source[uid]["blast_radius"] == "critical" or source[uid]["reversible"].lower() == "false":
        expected_gates.add(("rolloutapproval", "beforemerge"))
    for gate, position in expected_gates:
        assert (gate, position) in gates, f"{uid} is missing {gate} at {position}"
    unexpected = {gate for gate, _ in gates} - {gate for gate, _ in expected_gates}
    assert not unexpected, f"{uid} has unnecessary risk gates {sorted(unexpected)}, contrary to the effort constraint"


@pytest.mark.parametrize("aspect", ["state"] + [
    "test_failure", "merge_conflict", "ci_infra_flake", "review_rejection",
    "agent_timeout", "stale_base", "budget_exhausted", "duration_exhausted",
])
def test_persistent_state_and_failure_recovery(aspect: str):
    root = require_submission()
    _, policy = load_source()
    if aspect == "state":
        state = find_value(root, ["state_contract", "persistent_state", "checkpointing", "state_persistence"])
        assert state is not None, "persistent cross-iteration state is missing"
        run_path = find_value(state, ["run_state_path", "run_state", "state_path"])
        notes_path = find_value(state, ["unit_notes_pattern", "unit_state_pattern", "work_unit_notes"])
        assert str(run_path) == policy["persistent_state"]["run_state_path"], "run-state path does not match the operating policy"
        assert str(notes_path) == policy["persistent_state"]["unit_notes_pattern"], "per-unit notes pattern does not match the operating policy"
        tokens = strings_and_keys(state)
        for required in policy["persistent_state"]["required_run_fields"] + policy["persistent_state"]["required_unit_fields"]:
            assert nk(required) in tokens, f"persistent state omits required field {required}"
        return

    failures = extract_failures(root)
    expected = next(row for row in policy["failure_policies"] if row["failure_type"] == aspect)
    actual = failures.get(nk(aspect))
    assert actual is not None, f"recovery policy omits {aspect}"
    action = nk(field(actual, ["action", "response", "recovery_action"], ""))
    aliases = {
        "returntoimplement": {"returntoimplement", "backtoimplement", "fixandretry"},
        "evictandrequeueafterblockers": {"evictandrequeueafterblockers", "evictandrequeue", "evictcaptureandrequeue"},
        "retrysamegate": {"retrysamegate", "retrygate", "retrytest"},
        "routetoreviewfix": {"routetoreviewfix", "reviewfix", "addressreviewfindings"},
        "checkpointthenrequeue": {"checkpointthenrequeue", "checkpointandrequeue"},
        "rebasethenretest": {"rebasethenretest", "rebaseandretest"},
        "stopforoperator": {"stopforoperator", "stopandescalate", "operatorstop", "haltforoperator"},
    }
    expected_action = nk(expected["action"])
    assert action in aliases.get(expected_action, {expected_action}), f"{aspect} recovery action is {action!r}, expected {expected['action']}"
    retry = field(actual, ["retry_limit", "max_retries", "retries", "retry_count"])
    assert isinstance(retry, (int, float, str)) and int(retry) == expected["retry_limit"], f"{aspect} retry limit must be {expected['retry_limit']}"
    resume = nk(field(actual, ["resume_from", "restart_from", "resume_stage", "next_stage"], ""))
    assert resume == nk(expected["resume_from"]), f"{aspect} resume point is {resume!r}, expected {expected['resume_from']}"
    capture = strings_and_keys(field(actual, ["capture", "evidence", "context", "record", "failure_context"], []))
    missing = {nk(v) for v in expected["capture"]} - capture
    assert not missing, f"{aspect} fails to persist recovery context: {sorted(missing)}"


@pytest.mark.parametrize("aspect", ["limits", "merge_evidence", "success", "stop_conditions"])
def test_merge_evidence_and_termination_controls(aspect: str):
    root = require_submission()
    _, policy = load_source()
    if aspect == "limits":
        limits = find_value(root, ["limits", "bounds", "budgets", "execution_limits"])
        assert isinstance(limits, dict), "execution limits are missing"
        for key, expected in policy["limits"].items():
            actual = field(limits, [key])
            assert isinstance(actual, (int, float, str)) and float(actual) == float(expected), f"limit {key} must be {expected}"
    elif aspect == "merge_evidence":
        merge = find_value(root, ["merge_queue", "merge_plan", "integration_plan"])
        evidence = find_value(merge if merge is not None else root, ["eligibility", "merge_evidence", "required_evidence", "gates"])
        tokens = strings_and_keys(evidence)
        missing = {nk(v) for v in policy["required_merge_evidence"]} - tokens
        assert not missing, f"merge eligibility omits required evidence: {sorted(missing)}"
    else:
        completion = find_value(root, ["completion", "termination", "stop_conditions", "exit_conditions"])
        assert completion is not None, "completion and termination controls are missing"
        tokens = strings_and_keys(completion)
        expected_values = policy["completion"]["success_requires" if aspect == "success" else "stop_immediately_on"]
        missing = {nk(v) for v in expected_values} - tokens
        assert not missing, f"{aspect} omits policy conditions: {sorted(missing)}"
