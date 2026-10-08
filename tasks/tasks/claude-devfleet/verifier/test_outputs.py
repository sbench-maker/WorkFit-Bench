from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Any


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
OUTPUT = RESULTS / "output.json"
EXPECTED_IDS = {f"M-{number}" for number in range(101, 109)}
EXPECTED_STATUS = {
    "M-101": "completed",
    "M-102": "completed",
    "M-103": "completed",
    "M-104": "failed",
    "M-105": "completed",
    "M-106": "cancelled",
    "M-107": "completed",
    "M-108": "cancelled",
}


def _load_simulator():
    spec = importlib.util.spec_from_file_location("fixture_fleet", DATA / "devfleet_mock.py")
    assert spec is not None and spec.loader is not None, "the frozen simulator fixture is unavailable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FLEET = _load_simulator()
EXPECTED_SPECS = {row["mission_id"]: row for row in FLEET.MISSION_SPECS}


def _pick(mapping: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    normalized = {str(key).lower().replace("-", "_").replace(" ", "_"): value for key, value in mapping.items()}
    for key in keys:
        candidate = key.lower().replace("-", "_").replace(" ", "_")
        if candidate in normalized:
            return normalized[candidate]
    return default


def _mission_id(value: Any) -> str:
    if isinstance(value, dict):
        value = _pick(value, "mission_id", "id", "mission")
    return str(value or "").strip().upper().replace("_", "-")


def _status(value: Any) -> str:
    value = str(value or "").strip().lower().replace("_", "-")
    aliases = {"success": "completed", "complete": "completed", "canceled": "cancelled", "failure": "failed"}
    return aliases.get(value, value)


def _rows(value: Any, *, id_key: str = "mission_id") -> list[dict]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        rows = []
        for key, row in value.items():
            if isinstance(row, dict):
                item = dict(row)
                item.setdefault(id_key, key)
            else:
                item = {id_key: key, "status": row}
            rows.append(item)
        return rows
    return []


def _load_output() -> dict:
    assert OUTPUT.is_file(), "missing /root/results/output.json; there is no handoff to use"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"output.json is not readable JSON: {exc}") from exc
    assert isinstance(payload, dict), "output.json must contain a JSON object"
    return payload


def _extract_plan(payload: dict) -> list[dict]:
    plan = _pick(payload, "mission_plan", "missions", "plan", default=[])
    if isinstance(plan, dict) and any(key in plan for key in ("missions", "mission_plan", "tasks")):
        plan = _pick(plan, "missions", "mission_plan", "tasks", default=[])
    return _rows(plan)


def _extract_reports(payload: dict) -> list[dict]:
    return _rows(_pick(payload, "mission_reports", "reports", "structured_reports", default=[]))


def _extract_statuses(payload: dict, plan: list[dict], reports: list[dict]) -> dict[str, str]:
    raw = _pick(payload, "final_statuses", "statuses", "mission_statuses", default={})
    statuses = {}
    for row in _rows(raw):
        mid = _mission_id(row)
        if mid:
            statuses[mid] = _status(_pick(row, "status", "final_status", "state"))
    if not statuses and isinstance(raw, dict):
        statuses = {_mission_id(key): _status(value) for key, value in raw.items()}
    for collection in (plan, reports):
        for row in collection:
            mid = _mission_id(row)
            status = _status(_pick(row, "final_status", "status", "state"))
            if mid and status:
                statuses.setdefault(mid, status)
    return statuses


def _extract_events(payload: dict) -> list[dict]:
    events = _pick(payload, "dispatch_record", "dispatches", "events", "activity", default=[])
    return _rows(events, id_key="mission_id")


def _action(row: dict) -> str:
    value = str(_pick(row, "action", "event", "type", "dispatch_type", "mode", default="")).lower()
    value = value.replace("-", "_").replace(" ", "_")
    aliases = {
        "manual": "manual_dispatch",
        "dispatch": "manual_dispatch",
        "dispatched": "manual_dispatch",
        "auto": "auto_dispatch",
        "automatic": "auto_dispatch",
        "auto_dispatched": "auto_dispatch",
        "queued_for_capacity": "queued",
    }
    return aliases.get(value, value)


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(key) for key in value]
    if isinstance(value, list):
        answer = []
        for item in value:
            if isinstance(item, dict):
                item = _pick(item, "path", "file", "name", "id", default="")
            answer.append(str(item))
        return answer
    return [str(value)]


def _test_map(report: dict) -> dict[str, bool]:
    raw = _pick(report, "tests", "test_results", "tested", default=[])
    if isinstance(raw, dict):
        return {str(key): bool(value) for key, value in raw.items()}
    answer = {}
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        name = str(_pick(row, "name", "test", "suite", default=""))
        passed = _pick(row, "passed", "ok", "success")
        if passed is None:
            passed = _status(_pick(row, "status", "result")) in {"completed", "passed", "pass"}
        if name:
            answer[name] = bool(passed)
    return answer


def test_mission_plan_dag_and_prompts():
    """The simulator-returned project plan is preserved as an actionable, acyclic DAG."""
    payload = _load_output()
    plan = _extract_plan(payload)
    by_id = {_mission_id(row): row for row in plan}
    assert set(by_id) == EXPECTED_IDS, "the approved simulator plan must contain each mission exactly once"
    assert len(plan) == len(by_id), "duplicate mission rows make dispatch and reporting ambiguous"
    for mid, expected in EXPECTED_SPECS.items():
        row = by_id[mid]
        dependencies = {_mission_id(item) for item in _as_string_list(_pick(row, "depends_on", "dependencies", "requires", default=[]))}
        assert dependencies == set(expected["depends_on"]), f"{mid} has the wrong dependency edges"
        auto = _pick(row, "auto_dispatch", "auto_start", "automatic", default=None)
        assert auto is True or str(auto).strip().lower() in {"true", "yes", "enabled"}, f"{mid} lost its automatic dependency dispatch setting"
        assert str(_pick(row, "title", "name", default="")).strip(), f"{mid} has no human-readable mission title"
        assert len(str(_pick(row, "prompt", "description", "instructions", default="")).strip()) >= 30, f"{mid} lacks an actionable mission prompt"
    assert sum(not EXPECTED_SPECS[mid]["depends_on"] for mid in EXPECTED_IDS) == 1, "the plan should have one approved root"


def test_dispatch_and_terminal_states():
    """Dispatch follows the dependency watcher and capacity queue, and every mission terminates."""
    payload = _load_output()
    plan = _extract_plan(payload)
    reports = _extract_reports(payload)
    statuses = _extract_statuses(payload, plan, reports)
    assert statuses == EXPECTED_STATUS, "final states do not reflect the failed migration and its cancelled descendants"

    events = _extract_events(payload)
    manual = {_mission_id(row) for row in events if _action(row) == "manual_dispatch"}
    automatic = {_mission_id(row) for row in events if _action(row) == "auto_dispatch"}
    queued = {_mission_id(row) for row in events if _action(row) == "queued"}
    assert manual == {"M-101"}, "only the approved root mission should be dispatched manually"
    assert automatic == {"M-102", "M-103", "M-104", "M-105", "M-107"}, "ready descendants were not auto-dispatched exactly as dependencies allowed"
    assert "M-105" in queued, "the record does not show the fourth ready child waiting for the three-agent capacity"
    assert not ({"M-106", "M-108"} & (manual | automatic)), "cancelled descendants must never consume an agent slot"


def test_structured_report_fidelity():
    """Every terminal mission report preserves the mock service's concrete evidence."""
    payload = _load_output()
    reports = _extract_reports(payload)
    by_id = {_mission_id(row): row for row in reports}
    assert set(by_id) == EXPECTED_IDS, "a structured report is required for every terminal mission"
    assert len(reports) == len(by_id), "duplicate reports make the release handoff unreliable"

    for mid in sorted(EXPECTED_IDS):
        actual = by_id[mid]
        expected = FLEET.REPORT_CONTENT[mid]
        assert _status(_pick(actual, "status", "final_status", "state")) == EXPECTED_STATUS[mid], f"{mid} report status disagrees with final state"
        files = set(_as_string_list(_pick(actual, "files_changed", "changed_files", "files", default=[])))
        assert files == set(expected["files_changed"]), f"{mid} changed-file evidence is incomplete or fabricated"
        assert _test_map(actual) == {row["name"]: row["passed"] for row in expected["tests"]}, f"{mid} test evidence is inaccurate"
        assert str(_pick(actual, "what_done", "work_done", "summary", default="")).strip(), f"{mid} does not explain what happened"
        assert _as_string_list(_pick(actual, "next_steps", "next_step", "follow_up", default=[])), f"{mid} has no next-step guidance"

    failure_errors = _pick(by_id["M-104"], "errors", "error", "failures", default=[])
    failure_rows = failure_errors if isinstance(failure_errors, list) else [failure_errors]
    assert any(
        isinstance(row, dict)
        and _pick(row, "code") == "ROLLBACK_CHECKSUM_MISMATCH"
        and _pick(row, "file", "path") == "db/rollback/0142_token_vault_down.sql"
        for row in failure_rows
    ), "the failed migration report omits the actionable rollback checksum evidence"
    for mid in ("M-106", "M-108"):
        assert not _as_string_list(_pick(by_id[mid], "files_changed", "changed_files", "files", default=[])), f"{mid} was cancelled and must not claim code changes"
    active_branches = []
    for mid in sorted(EXPECTED_IDS - {"M-106", "M-108"}):
        branch = str(_pick(by_id[mid], "worktree_branch", "branch", "worktree", default="")).strip()
        assert branch, f"{mid} lacks the isolated worktree branch needed for follow-up"
        active_branches.append(branch)
    assert len(active_branches) == len(set(active_branches)), "missions must not claim the same worktree branch"
