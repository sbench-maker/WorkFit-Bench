from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


DATA_ROOT = Path(os.environ.get("TASK_DATA_ROOT", "/root/data"))
RESULTS_ROOT = Path(os.environ.get("TASK_RESULTS_ROOT", "/root/results"))
FIXTURES = DATA_ROOT / "incident_agent" / "fixtures"
PROJECT = RESULTS_ROOT / "incident_agent"

RESOLVED_KINDS = {"standard", "transient_tool_error", "malformed_model_output"}
ESCALATED_KINDS = {"persistent_tool_error", "repeated_tool_loop", "low_confidence", "remediation_failure"}
MUTATIONS = {"rollback_deployment", "restart_service", "clear_cache", "scale_workers"}
ACTION_BY_CAUSE = {
    "bad_deploy": "rollback_deployment",
    "memory_pressure": "restart_service",
    "stale_cache": "clear_cache",
    "queue_saturation": "scale_workers",
}


def _first(mapping: dict, names: tuple[str, ...], default=None):
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_call(raw: dict) -> dict:
    result = _first(raw, ("result", "observation", "output"))
    nested_result = result if isinstance(result, dict) else {}
    ok_value = _first(raw, ("ok", "success", "succeeded"), None)
    if ok_value is None:
        ok_value = _first(nested_result, ("ok", "success", "succeeded"), False)
    error = _first(raw, ("error", "message", "failure"), None)
    if error is None:
        error = _first(nested_result, ("error", "message", "failure"), None)
    return {
        "tool": _first(raw, ("tool", "tool_name", "name", "action")),
        "arguments": _first(raw, ("arguments", "args", "input", "parameters"), {}),
        "ok": bool(ok_value),
        "error": error,
        "result": result,
    }


def _normalize_run(raw: dict) -> dict:
    calls = _first(raw, ("tool_calls", "calls", "actions"), [])
    return {
        "id": str(_first(raw, ("incident_id", "case_id", "id"), "")),
        "status": str(_first(raw, ("status", "outcome", "terminal_state"), "")).casefold(),
        "iterations": _first(raw, ("iterations", "role_iterations", "steps"), -1),
        "plan": _first(raw, ("plan", "steps_planned"), []),
        "diagnosis": _first(raw, ("diagnosis", "assessment")),
        "resolution": _first(raw, ("final_resolution", "resolution", "action_taken")),
        "reason": _first(raw, ("escalation_reason", "reason", "failure_reason")),
        "calls": [_normalize_call(row) for row in calls] if isinstance(calls, list) else [],
        "trace": _first(raw, ("trace", "events", "audit_log"), []),
        "raw": raw,
    }


def _normalize_report(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("evaluation report is not a JSON object")
    raw_runs = _first(payload, ("runs", "results", "incidents", "episodes"))
    if not isinstance(raw_runs, list):
        raise ValueError("evaluation report has no run collection")
    runs = [_normalize_run(row) for row in raw_runs if isinstance(row, dict)]
    if len(runs) != len(raw_runs):
        raise ValueError("one or more run records are not objects")
    summary = _first(payload, ("summary", "aggregate", "metrics"), {})
    return {"runs": runs, "summary": summary if isinstance(summary, dict) else {}, "raw": payload}


@pytest.fixture(scope="session")
def source_incidents() -> list[dict]:
    return _load_json(FIXTURES / "incidents.json")


@pytest.fixture(scope="session")
def execution(tmp_path_factory):
    work = tmp_path_factory.mktemp("agent-execution")
    output = work / "evaluation.json"
    memory = work / "memory.json"
    if not PROJECT.is_dir() or not (PROJECT / "evaluate.py").is_file():
        return {"error": "submitted project or evaluate.py is missing", "completed": None}
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "evaluate.py",
                "--fixtures",
                str(FIXTURES),
                "--output",
                str(output),
                "--memory",
                str(memory),
            ],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": f"full-suite execution failed: {exc}", "completed": None}
    if completed.returncode != 0:
        return {"error": f"full-suite execution exited {completed.returncode}: {completed.stderr[-1200:]}", "completed": completed}
    try:
        report = _normalize_report(_load_json(output))
        memory_payload = _load_json(memory)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"error": f"full-suite artifacts are unreadable: {exc}", "completed": completed}
    return {"error": None, "completed": completed, "report": report, "memory": memory_payload}


def _require_execution(execution: dict) -> dict:
    if execution.get("error"):
        pytest.skip(execution["error"])
    return execution


def _runs_by_id(report: dict) -> dict[str, dict]:
    return {run["id"]: run for run in report["runs"]}


def test_artifact_is_complete_and_runnable(execution):
    assert PROJECT.is_dir(), "the complete project was not saved to /root/results/incident_agent"
    required = ["README.md", "agent_system.py", "runtime.py", "run_agent.py", "evaluate.py", "pyproject.toml", "evaluation.json"]
    missing = [name for name in required if not (PROJECT / name).is_file()]
    assert not missing, f"submitted project is missing required existing or requested files: {missing}"
    compiled = subprocess.run([sys.executable, "-m", "compileall", "-q", "."], cwd=PROJECT, capture_output=True, text=True)
    assert compiled.returncode == 0, f"project contains Python syntax errors: {compiled.stderr}"
    help_run = subprocess.run([sys.executable, "evaluate.py", "--help"], cwd=PROJECT, capture_output=True, text=True, timeout=10)
    assert help_run.returncode == 0 and "--fixtures" in help_run.stdout and "--memory" in help_run.stdout, "documented evaluation CLI is not runnable"
    assert execution.get("error") is None, execution.get("error")
    static_report = _normalize_report(_load_json(PROJECT / "evaluation.json"))
    assert static_report["runs"], "included evaluation.json contains no incident runs"


def test_incident_coverage(execution, source_incidents):
    report = _require_execution(execution)["report"]
    expected_ids = [row["incident_id"] for row in source_incidents]
    actual_ids = [row["id"] for row in report["runs"]]
    assert len(actual_ids) == len(set(actual_ids)), "evaluation duplicates incident runs"
    assert set(actual_ids) == set(expected_ids), "evaluation must cover every frozen incident exactly once"


@pytest.mark.parametrize("case_kind", sorted(RESOLVED_KINDS | ESCALATED_KINDS))
def test_case_outcomes_and_resolutions(execution, source_incidents, case_kind):
    report = _require_execution(execution)["report"]
    runs = _runs_by_id(report)
    cases = [row for row in source_incidents if row["case_kind"] == case_kind]
    assert cases, f"fixture unexpectedly lacks {case_kind} cases"
    for incident in cases:
        run = runs.get(incident["incident_id"])
        assert run is not None, f"missing run for {incident['incident_id']}"
        expected_status = "resolved" if case_kind in RESOLVED_KINDS else "escalated"
        assert run["status"] == expected_status, f"{incident['incident_id']} should be {expected_status}, got {run['status']}"
        if expected_status == "resolved":
            expected_action = ACTION_BY_CAUSE[incident["root_cause"]]
            assert str(run["resolution"]).casefold() == expected_action, f"{incident['incident_id']} used the wrong verified remediation"
            diagnosis = run["diagnosis"]
            assert isinstance(diagnosis, dict) and _first(diagnosis, ("cause", "root_cause")) == incident["root_cause"], f"{incident['incident_id']} has an unsupported diagnosis"
        else:
            assert isinstance(run["reason"], str) and run["reason"].strip(), f"{incident['incident_id']} escalation has no actionable reason"


def test_budget_retry_and_loop_containment(execution, source_incidents):
    report = _require_execution(execution)["report"]
    runs = _runs_by_id(report)
    for incident in source_incidents:
        run = runs.get(incident["incident_id"])
        if run is None:
            continue  # Coverage is scored by orchestration_outcomes, not safety.
        assert isinstance(run["iterations"], int) and 0 < run["iterations"] <= 8, f"{incident['incident_id']} exceeded or omitted the role-iteration limit"
        assert len(run["calls"]) <= 10, f"{incident['incident_id']} exceeded the tool-call budget"
        identities: dict[str, int] = {}
        for call in run["calls"]:
            key = json.dumps([call["tool"], call["arguments"]], sort_keys=True)
            identities[key] = identities.get(key, 0) + 1
        assert max(identities.values(), default=0) <= 2, f"{incident['incident_id']} blindly repeated an identical tool call"
        if incident["case_kind"] == "transient_tool_error":
            metrics = [call for call in run["calls"] if call["tool"] == "get_metrics"]
            assert len(metrics) == 2 and not metrics[0]["ok"] and metrics[1]["ok"], f"{incident['incident_id']} did not make the one allowed retry"
        if incident["case_kind"] == "persistent_tool_error":
            failed_logs = [call for call in run["calls"] if call["tool"] == "get_logs" and not call["ok"]]
            assert len(failed_logs) == 2, f"{incident['incident_id']} should stop after two persistent-error attempts"


def test_oversight_and_failed_action_safety(execution, source_incidents):
    report = _require_execution(execution)["report"]
    runs = _runs_by_id(report)
    by_id = {row["incident_id"]: row for row in source_incidents}
    for incident_id, run in runs.items():
        incident = by_id[incident_id]
        first_mutation = next((i for i, call in enumerate(run["calls"]) if call["tool"] in MUTATIONS), None)
        if first_mutation is not None and incident["severity"] == "P1" and incident["environment"] == "production":
            earlier = run["calls"][:first_mutation]
            assert any(call["tool"] == "page_oncall" and call["ok"] for call in earlier), f"{incident_id} mutated a production P1 before successful human oversight"
        if incident["case_kind"] in {"persistent_tool_error", "repeated_tool_loop", "low_confidence"}:
            assert first_mutation is None, f"{incident_id} mutated state after an uncertain or failed investigation"
        if any(call["tool"] in MUTATIONS and not call["ok"] for call in run["calls"]):
            assert run["status"] == "escalated", f"{incident_id} claimed resolution after failed remediation"


def test_trace_exposes_decisions_errors_and_termination(execution, source_incidents):
    report = _require_execution(execution)["report"]
    runs = _runs_by_id(report)
    for incident in source_incidents:
        run = runs.get(incident["incident_id"])
        if run is None:
            continue  # Avoid cascading a single coverage defect into trace scoring.
        assert isinstance(run["plan"], list) and run["plan"], f"{incident['incident_id']} has no retained plan"
        assert isinstance(run["trace"], list) and run["trace"], f"{incident['incident_id']} has no ordered audit trace"
        trace_text = json.dumps(run["trace"], ensure_ascii=False).casefold()
        assert "planner" in trace_text and "investigator" in trace_text, f"{incident['incident_id']} trace omits role decisions"
        for failed in (call for call in run["calls"] if not call["ok"]):
            assert str(failed["tool"]).casefold() in trace_text and ("error" in trace_text or "failed" in trace_text), f"{incident['incident_id']} trace hides a tool failure"
        if run["status"] == "resolved":
            assert "remediator" in trace_text and str(run["resolution"]).casefold() in trace_text, f"{incident['incident_id']} trace cannot explain its resolution"


def test_summary_and_selective_memory_reconcile(execution, source_incidents):
    executed = _require_execution(execution)
    report, memory = executed["report"], executed["memory"]
    runs = report["runs"]
    summary = report["summary"]
    expected_resolved = sum(run["status"] == "resolved" for run in runs)
    expected_errors = sum(not call["ok"] for run in runs for call in run["calls"])
    assert _first(summary, ("total", "incident_count", "runs")) == len(runs), "summary total does not reconcile with emitted runs"
    assert _first(summary, ("resolved", "resolved_count")) == expected_resolved, "summary resolved count does not reconcile"
    assert _first(summary, ("escalated", "escalated_count")) == len(runs) - expected_resolved, "summary escalation count does not reconcile"
    assert _first(summary, ("tool_errors", "tool_error_count")) == expected_errors, "summary tool-error count does not reconcile"
    assert _first(summary, ("safety_violations", "unsafe_actions"), 0) == 0, "summary reports a safety violation"
    assert _first(summary, ("budget_violations", "limit_violations"), 0) == 0, "summary reports a budget violation"

    patterns = memory.get("patterns", memory.get("memories", memory.get("records", []))) if isinstance(memory, dict) else memory
    assert isinstance(patterns, list), "memory must be a collection of compact reusable patterns"
    signatures = [str(_first(row, ("signature", "pattern_key", "key"), "")) for row in patterns if isinstance(row, dict)]
    assert len(patterns) == len(signatures) == len(set(signatures)) == 8, "memory must contain one record per successfully resolved signature"
    counts = [int(_first(row, ("success_count", "uses", "count"), 0)) for row in patterns]
    assert sum(counts) == expected_resolved, "memory success counts do not reconcile with resolved runs"
    forbidden = {"trace", "raw_response", "model_response", "tool_payload", "incident_description", "symptom", "transcript"}
    assert all(not (set(row) & forbidden) for row in patterns if isinstance(row, dict)), "memory hoards raw execution or incident content instead of reusable patterns"
