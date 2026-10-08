from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest


OUTPUT = Path("/root/results/output.json")
DATA = Path("/root/data")
GATES = {"research", "implementationplan", "implementation", "tests", "review", "mergereadyreport"}
VALID_STATES = {"pending", "blocked", "notstarted", "ready", "inprogress", "complete", "completed", "passed", "done"}
REQUIREMENTS = {f"R{i}" for i in range(1, 13)}
PRIMARY_MODULES = {
    "R1": {"libs/export-contract"},
    "R2": {"db/export-schema"},
    "R3": {"services/policy"},
    "R4": {"workers/export-snapshot"},
    "R5": {"workers/export-redaction"},
    "R6": {"workers/export-package"},
    "R7": {"services/export-api"},
    "R8": {"services/export-api"},
    "R9": {"services/audit"},
    "R10": {"web/admin-exports"},
    "R11": {"ops/export-lifecycle"},
    "R12": {"config/feature-flags", "tests/export-system"},
}
MIN_RISK = {"R1": 1, "R2": 3, "R3": 3, "R4": 2, "R5": 3, "R6": 3, "R7": 2, "R8": 2, "R9": 2, "R10": 2, "R11": 2, "R12": 2}
PREREQS = {
    "R1": set(),
    "R2": {"R1"},
    "R3": {"R1"},
    "R4": {"R1", "R2"},
    "R5": {"R4"},
    "R6": {"R5", "R2"},
    "R7": {"R1", "R2", "R3"},
    "R8": {"R1", "R2", "R3", "R6"},
    "R9": {"R7", "R8", "R6"},
    "R10": {"R7", "R8"},
    "R11": {"R2", "R6"},
    "R12": {"R9", "R10", "R11"},
}
REQUIRED_TESTS = {
    "R1": {"CT-01", "UT-01"},
    "R2": {"DB-01", "DB-02", "UT-02"},
    "R3": {"SEC-01", "SEC-02", "UT-03"},
    "R4": {"SNAP-01", "SNAP-02", "UT-05"},
    "R5": {"RED-01", "RED-02", "UT-06"},
    "R6": {"PKG-01", "PKG-02", "UT-07"},
    "R7": {"API-01", "UT-04"},
    "R8": {"API-02", "API-03", "UT-04"},
    "R9": {"AUD-01", "AUD-02", "UT-08"},
    "R10": {"UI-01", "UI-02", "UT-09"},
    "R11": {"OPS-01", "OPS-02", "UT-10"},
    "R12": {"CT-01", "SYS-01", "SYS-02", "SYS-03", "SYS-04", "UT-11", "UT-12"},
}
UNCHANGED_IDS = {
    "R1": "WU-CONTRACT", "R2": "WU-SCHEMA", "R3": "WU-POLICY", "R7": "WU-API",
    "R8": "WU-API", "R9": "WU-AUDIT", "R10": "WU-UI", "R11": "WU-OPS", "R12": "WU-ROLLOUT",
}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _find_first(obj: Any, aliases: set[str]) -> Any:
    wanted = {_norm(alias) for alias in aliases}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _norm(key) in wanted:
                return value
        for value in obj.values():
            found = _find_first(value, aliases)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_first(value, aliases)
            if found is not None:
                return found
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (set, tuple)):
        return list(value)
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    return [value]


def _strings(value: Any) -> list[str]:
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            candidate = _find_first(item, {"id", "name", "test_id", "unit_id", "module", "requirement_id"})
            if candidate is not None:
                result.append(str(candidate))
        elif item is not None:
            result.append(str(item))
    return result


def _load() -> dict | None:
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _unit_rows(payload: dict) -> list[dict]:
    raw = _find_first(payload, {"active_units", "work_units", "units"})
    if isinstance(raw, dict):
        raw = list(raw.values())
    return [row for row in _as_list(raw) if isinstance(row, dict)]


def _unit_id(row: dict) -> str:
    return str(_find_first(row, {"id", "unit_id", "work_unit_id"}) or "")


def _requirements(row: dict) -> set[str]:
    value = _find_first(row, {"requirements", "requirement_ids", "rfc_requirements"})
    return {item.upper() for item in _strings(value) if re.fullmatch(r"R\d+", item.upper())}


def _modules(row: dict) -> set[str]:
    value = _find_first(row, {"modules", "components", "repository_modules", "module_scope"})
    return {item.strip() for item in _strings(value) if item.strip()}


def _dependencies(row: dict) -> set[str]:
    value = _find_first(row, {"depends_on", "dependencies", "predecessors", "requires_units"})
    return {item for item in _strings(value) if item}


def _test_ids(value: Any) -> set[str]:
    return {item.upper() for item in _strings(value) if re.fullmatch(r"[A-Za-z]+-\d+", item)}


def _risk(row: dict) -> int:
    value = _find_first(row, {"risk_level", "risk", "complexity_tier", "tier"})
    match = re.search(r"([123])", str(value or ""))
    return int(match.group(1)) if match else 0


def _status(row: dict) -> str:
    return _norm(_find_first(row, {"status", "state", "unit_status"}) or "")


def _gate_map(row: dict) -> dict[str, str]:
    raw = _find_first(row, {"quality_gates", "gates", "quality_pipeline"})
    result: dict[str, str] = {}
    if isinstance(raw, dict):
        for name, state in raw.items():
            if isinstance(state, dict):
                state = _find_first(state, {"state", "status"})
            result[_norm(name)] = _norm(state)
    else:
        for item in _as_list(raw):
            if isinstance(item, str):
                result[_norm(item)] = "complete"
            elif isinstance(item, dict):
                name = _find_first(item, {"name", "gate", "stage"})
                state = _find_first(item, {"state", "status", "result"})
                if name is not None:
                    result[_norm(name)] = _norm(state or "pending")
    return result


def _rows_by_id(payload: dict) -> dict[str, dict]:
    return {_unit_id(row): row for row in _unit_rows(payload) if _unit_id(row)}


def _owners(payload: dict) -> dict[str, str]:
    result = {}
    for row in _unit_rows(payload):
        for requirement in _requirements(row):
            result[requirement] = _unit_id(row)
    return result


def _flatten_queue(payload: dict) -> list[dict]:
    raw = _find_first(payload, {"merge_queue", "merge_plan", "queue"})
    rows = []
    if isinstance(raw, dict):
        raw = _find_first(raw, {"entries", "items", "waves", "units"}) or list(raw.values())
    for index, item in enumerate(_as_list(raw), start=1):
        if isinstance(item, str):
            rows.append({"unit_id": item, "_wave": index})
        elif isinstance(item, dict):
            direct = _find_first(item, {"unit_id", "work_unit_id", "id"})
            nested = _find_first(item, {"unit_ids", "units", "entries", "items"})
            if direct:
                clone = dict(item)
                clone["_wave"] = _find_first(item, {"wave", "position", "order"}) or index
                rows.append(clone)
            elif nested is not None:
                wave = _find_first(item, {"wave", "position", "order"}) or index
                for member in _as_list(nested):
                    clone = dict(item)
                    clone.pop("unit_ids", None)
                    clone.pop("units", None)
                    if isinstance(member, dict):
                        clone.update(member)
                    else:
                        clone["unit_id"] = member
                    clone["_wave"] = wave
                    rows.append(clone)
    return rows


def _queue_unit_id(row: dict) -> str:
    return str(_find_first(row, {"unit_id", "work_unit_id", "id"}) or "")


def _skip_without_payload() -> dict:
    payload = _load()
    if payload is None:
        pytest.skip("artifact readability is scored only by test_artifact_usability")
    return payload


def test_requirement_ownership_and_scope() -> None:
    payload = _skip_without_payload()
    units = _unit_rows(payload)
    ownership: dict[str, list[dict]] = {requirement: [] for requirement in REQUIREMENTS}
    for row in units:
        for requirement in _requirements(row):
            if requirement in ownership:
                ownership[requirement].append(row)
    bad_counts = {req: len(rows) for req, rows in ownership.items() if len(rows) != 1}
    assert not bad_counts, f"every RFC requirement must have exactly one active owner; bad counts: {bad_counts}"
    assert ownership["R4"][0] is not ownership["R5"][0] and ownership["R5"][0] is not ownership["R6"][0] and ownership["R4"][0] is not ownership["R6"][0], "R4, R5, and R6 must be split across three reviewable successor units"
    for requirement, rows in ownership.items():
        modules = _modules(rows[0])
        assert PRIMARY_MODULES[requirement] <= modules, f"{requirement} owner omits its primary repository module"
    owners = {requirement: _unit_id(rows[0]) for requirement, rows in ownership.items()}
    for requirement, expected_id in UNCHANGED_IDS.items():
        assert owners[requirement] == expected_id, f"unaffected {requirement} should preserve existing unit ID {expected_id}"


def test_stalled_worker_recovery_and_risk() -> None:
    payload = _skip_without_payload()
    units = _unit_rows(payload)
    active_ids = {_unit_id(row) for row in units}
    assert "WU-WORKER" not in active_ids, "the stalled broad worker unit must be evicted from the active DAG"
    for row in units:
        requirements = _requirements(row)
        if requirements:
            expected = max(MIN_RISK[req] for req in requirements)
            assert _risk(row) >= expected, f"{_unit_id(row)} understates the RFC's minimum risk tier"
    recovery = _find_first(payload, {"recovery", "retired_units", "recovery_plan"})
    recovery_rows = [row for row in _as_list(recovery) if isinstance(row, dict)]
    target = next((row for row in recovery_rows if str(_find_first(row, {"retired_unit_id", "unit_id", "id"}) or "") == "WU-WORKER"), None)
    assert target is not None, "recovery record does not identify retired WU-WORKER"
    action = _norm(_find_first(target, {"action", "status", "disposition"}) or "")
    assert action in {"evicted", "retired", "replaced", "removedfromactivequeue"}, "WU-WORKER recovery action is not an eviction/retirement"
    successors = set(_strings(_find_first(target, {"successor_unit_ids", "successors", "replacement_units"})))
    expected_successors = {_unit_id(next(row for row in units if req in _requirements(row))) for req in ("R4", "R5", "R6")}
    assert expected_successors <= successors, "recovery record must name all three narrower successor units"


def test_dependency_graph_is_acyclic_and_complete() -> None:
    payload = _skip_without_payload()
    rows = _rows_by_id(payload)
    owners = _owners(payload)
    assert set(owners) == REQUIREMENTS, "cannot validate DAG until requirement ownership is complete"
    for unit_id, row in rows.items():
        deps = _dependencies(row)
        assert unit_id not in deps and deps <= set(rows), f"{unit_id} has a self-reference or unknown dependency: {sorted(deps - set(rows))}"
        expected = set()
        for requirement in _requirements(row):
            expected.update(owners[prereq] for prereq in PREREQS[requirement])
        expected.discard(unit_id)
        assert expected <= deps, f"{unit_id} omits prerequisite unit dependencies {sorted(expected - deps)}"
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(unit_id: str) -> None:
        assert unit_id not in visiting, f"dependency cycle reaches {unit_id}"
        if unit_id in visited:
            return
        visiting.add(unit_id)
        for dependency in _dependencies(rows[unit_id]):
            visit(dependency)
        visiting.remove(unit_id)
        visited.add(unit_id)
    for unit_id in rows:
        visit(unit_id)
    graph = _find_first(payload, {"dependency_graph", "dag", "graph"})
    edge_rows = _find_first(graph, {"edges", "links", "dependencies"}) if isinstance(graph, dict) else None
    graph_edges = set()
    for edge in _as_list(edge_rows):
        if isinstance(edge, dict):
            source = _find_first(edge, {"from", "source", "producer", "dependency"})
            target = _find_first(edge, {"to", "target", "consumer", "dependent"})
            if source and target:
                graph_edges.add((str(source), str(target)))
        elif isinstance(edge, (list, tuple)) and len(edge) == 2:
            graph_edges.add((str(edge[0]), str(edge[1])))
    expected_edges = {(dependency, unit_id) for unit_id, row in rows.items() for dependency in _dependencies(row)}
    assert graph_edges == expected_edges, "graph snapshot edges must match unit dependency declarations"
    order = _strings(_find_first(graph, {"topological_order", "order", "topological_sort"})) if isinstance(graph, dict) else []
    assert len(order) == len(rows) and set(order) == set(rows), "graph needs one complete topological order"
    positions = {unit_id: index for index, unit_id in enumerate(order)}
    assert all(positions[source] < positions[target] for source, target in graph_edges), "declared topological order violates an edge"


def test_merge_queue_respects_dependencies_and_readiness() -> None:
    payload = _skip_without_payload()
    rows = _rows_by_id(payload)
    queue = _flatten_queue(payload)
    queue_ids = [_queue_unit_id(row) for row in queue]
    assert queue_ids and len(queue_ids) == len(set(queue_ids)), "merge queue must identify each queued unit once"
    expected = {unit_id for unit_id, row in rows.items() if _status(row) not in {"merged", "complete", "completed"}}
    assert set(queue_ids) == expected, f"merge queue must cover all and only unmerged active units; missing/extras: {sorted(expected ^ set(queue_ids))}"
    assert "WU-WORKER" not in queue_ids and "WU-CONTRACT" not in queue_ids, "retired or already merged units must not re-enter the queue"
    assert _status(rows["WU-CONTRACT"]) in {"merged", "complete", "completed"}, "already merged WU-CONTRACT must remain merged"
    for unit_id in {"WU-SCHEMA", "WU-POLICY"}:
        assert _status(rows[unit_id]) in {"mergeready", "ready", "readytomerge"}, f"{unit_id} completed its unit gates and should remain merge-ready"
    for unit_id in expected - {"WU-SCHEMA", "WU-POLICY"}:
        assert _status(rows[unit_id]) not in {"merged", "complete", "completed", "mergeready", "ready", "readytomerge"}, f"{unit_id} overstates readiness despite unfinished work or dependencies"
    positions = {unit_id: index for index, unit_id in enumerate(queue_ids)}
    waves = {_queue_unit_id(entry): str(entry.get("_wave", "")) for entry in queue}
    for unit_id in queue_ids:
        for dependency in _dependencies(rows[unit_id]):
            if dependency in positions:
                assert positions[dependency] < positions[unit_id], f"{unit_id} is queued before dependency {dependency}"
                assert waves[dependency] != waves[unit_id], f"dependent units {dependency} and {unit_id} cannot share a merge wave"
    immediate = set()
    for index, entry in enumerate(queue):
        state = _norm(_find_first(entry, {"queue_state", "readiness", "phase", "status"}) or "")
        if state in {"immediate", "ready", "now"} or (not state and index < 2):
            immediate.add(_queue_unit_id(entry))
        rebase = _find_first(entry, {"rebase", "rebase_target", "rebase_action", "branch_base"})
        assert isinstance(rebase, str) and rebase.strip(), f"queue entry {_queue_unit_id(entry)} lacks a rebase target/action"
        if index >= 2:
            preconditions = " ".join(_strings(_find_first(entry, {"preconditions", "conditions", "gates", "requirements"}))).lower()
            assert "depend" in preconditions and "gate" in preconditions, f"later queue entry {_queue_unit_id(entry)} must state dependency and unfinished-gate preconditions"
    assert immediate == {"WU-SCHEMA", "WU-POLICY"}, f"only the two completed-gate units are immediately mergeable, got {sorted(immediate)}"


def test_unit_acceptance_tests_and_gate_states() -> None:
    payload = _skip_without_payload()
    rows = _unit_rows(payload)
    catalog = json.loads((DATA / "ci_catalog.json").read_text(encoding="utf-8"))["tests"]
    valid_test_ids = {row["test_id"] for row in catalog}
    expected_completed = {
        "WU-CONTRACT": GATES, "WU-SCHEMA": GATES, "WU-POLICY": GATES,
        "WU-API": {"research", "implementationplan"},
        "WU-AUDIT": {"research", "implementationplan"},
        "WU-UI": {"research"}, "WU-OPS": {"research"}, "WU-ROLLOUT": {"research"},
    }
    for row in rows:
        unit_id = _unit_id(row)
        requirements = _requirements(row)
        actual_tests = _test_ids(_find_first(row, {"acceptance_tests", "test_ids", "validation_tests", "tests"}))
        required = set().union(*(REQUIRED_TESTS[req] for req in requirements))
        assert required <= actual_tests, f"{unit_id} is missing blocking acceptance tests {sorted(required - actual_tests)}"
        assert actual_tests <= valid_test_ids, f"{unit_id} invents test IDs {sorted(actual_tests - valid_test_ids)}"
        gate_map = _gate_map(row)
        assert set(gate_map) == GATES, f"{unit_id} must expose all six quality gates exactly once"
        assert set(gate_map.values()) <= VALID_STATES, f"{unit_id} uses an unrecognized quality-gate state"
        completed = {name for name, state in gate_map.items() if state in {"complete", "completed", "passed", "done"}}
        if unit_id in expected_completed:
            assert completed == expected_completed[unit_id], f"{unit_id} gate completion contradicts the frozen snapshot"
        else:
            assert requirements <= {"R4", "R5", "R6"} and completed == {"research"}, f"new successor {unit_id} should preserve research findings without inventing later completed gates"


def test_post_merge_and_final_verification() -> None:
    payload = _skip_without_payload()
    rows = _rows_by_id(payload)
    queue = _flatten_queue(payload)
    catalog = json.loads((DATA / "ci_catalog.json").read_text(encoding="utf-8"))["tests"]
    system_tests = {row["test_id"]: set(row["covers"]) for row in catalog if row["kind"] == "system"}
    valid_test_ids = {row["test_id"] for row in catalog}
    merged_requirements = set(_requirements(rows["WU-CONTRACT"]))
    for entry in queue:
        unit_id = _queue_unit_id(entry)
        merged_requirements.update(_requirements(rows[unit_id]))
        actual = _test_ids(_find_first(entry, {"post_merge_tests", "tests", "integration_tests", "rerun_tests"}))
        required = _test_ids(_find_first(rows[unit_id], {"acceptance_tests", "test_ids", "validation_tests", "tests"}))
        required.update(test_id for test_id, coverage in system_tests.items() if coverage <= merged_requirements)
        assert required <= actual, f"post-merge plan for {unit_id} misses required reruns {sorted(required - actual)}"
        assert actual <= valid_test_ids, f"post-merge plan for {unit_id} invents test IDs {sorted(actual - valid_test_ids)}"
    final = _find_first(payload, {"final_verification", "release_verification", "system_verification"})
    final_tests = _test_ids(_find_first(final, {"test_ids", "tests", "system_tests"}))
    assert final_tests == {"SYS-01", "SYS-02", "SYS-03", "SYS-04"}, "final verification must identify exactly the four cataloged system suites"
    checks = " ".join(_strings(_find_first(final, {"checks", "conditions", "rehearsals", "verification_steps"}))).lower()
    assert "cohort" in checks and ("history" in checks or "inspect" in checks), "final verification omits the cohort-disable/job-history rehearsal"
