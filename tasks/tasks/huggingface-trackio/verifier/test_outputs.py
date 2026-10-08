from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from typing import Any

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
SCRIPT_PATH = RESULTS_DIR / "train_monitored.py"
STORE_PATH = RESULTS_DIR / "experiment_store.json"
REPORT_PATH = RESULTS_DIR / "experiment_report.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source() -> tuple[dict, dict, list[dict[str, str]]]:
    specs = load_json(DATA_DIR / "run_specs.json")
    policy = load_json(DATA_DIR / "monitoring_policy.json")
    with (DATA_DIR / "telemetry.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return specs, policy, rows


SPECS, POLICY, SOURCE_ROWS = load_source()
RUN_IDS = [row["run_id"] for row in SPECS["runs"]]


def cli_prefix() -> list[str]:
    configured = os.environ.get("TRACKIO_CLI")
    if configured:
        return shlex.split(configured)
    return ["trackio"]


def run_cli(store: Path, *args: str) -> dict:
    env = os.environ.copy()
    env["TRACKIO_DB_PATH"] = str(store)
    completed = subprocess.run(
        [*cli_prefix(), *args, "--json"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"local experiment query failed ({' '.join(args)}): {completed.stderr.strip()}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"experiment CLI did not return JSON: {exc}") from exc


@pytest.fixture(scope="session")
def replayed_store(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    if not SCRIPT_PATH.is_file():
        return {"path": None, "error": f"missing runnable script: {SCRIPT_PATH}"}
    scratch = tmp_path_factory.mktemp("replay")
    fresh_store = scratch / "experiment_store.json"
    env = os.environ.copy()
    env["TRACKIO_DB_PATH"] = str(fresh_store)
    env["MONITORING_RESULTS_DIR"] = str(scratch)
    env["SWEEP_DATA_DIR"] = str(DATA_DIR)
    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(RESULTS_DIR),
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"path": None, "error": f"script replay failed: {exc}"}
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout)[-1200:]
        return {"path": None, "error": f"script exited {completed.returncode}: {detail}"}
    if not fresh_store.is_file():
        return {
            "path": None,
            "error": "script did not create a fresh local store at the documented TRACKIO_DB_PATH",
        }
    return {"path": fresh_store, "error": None}


def expected_metric_series(run_id: str, metric: str) -> list[tuple[int, float | None]]:
    values = []
    for row in SOURCE_ROWS:
        if row["run_id"] != run_id or row[metric] == "":
            continue
        value = float(row[metric])
        values.append((int(row["step"]), value if math.isfinite(value) else None))
    return values


def expected_alerts(run_id: str) -> list[tuple[str, int]]:
    rows = [row for row in SOURCE_ROWS if row["run_id"] == run_id]
    diagnostics = POLICY["diagnostics"]
    emitted: set[str] = set()
    found: list[tuple[str, int]] = []
    recent: list[tuple[int, float]] = []
    evaluations: list[tuple[int, float]] = []
    for raw in rows:
        step = int(raw["step"])
        loss = float(raw["train_loss"])
        if not math.isfinite(loss) and "nonfinite_loss" not in emitted:
            found.append((diagnostics["nonfinite_loss"]["level"], step))
            emitted.add("nonfinite_loss")
        if math.isfinite(loss):
            rule = diagnostics["divergence"]
            recent.append((step, loss))
            recent = recent[-int(rule["consecutive_steps"]) :]
            enough = len(recent) == int(rule["consecutive_steps"])
            consecutive = enough and all(recent[i][0] == recent[0][0] + i for i in range(len(recent)))
            rising = enough and all(recent[i][1] < recent[i + 1][1] for i in range(len(recent) - 1))
            above = enough and all(value >= float(rule["threshold"]) for _, value in recent)
            if consecutive and rising and above and "divergence" not in emitted:
                found.append((rule["level"], step))
                emitted.add("divergence")
        if raw["val_loss"] != "":
            rule = diagnostics["validation_plateau"]
            evaluations.append((step, float(raw["val_loss"])))
            window = evaluations[-int(rule["evaluation_points"]) :]
            if len(window) == int(rule["evaluation_points"]) and step >= int(rule["earliest_step"]):
                improvement = window[0][1] - window[-1][1]
                span = max(value for _, value in window) - min(value for _, value in window)
                if (
                    improvement < float(rule["minimum_required_improvement"])
                    and span <= float(rule["maximum_range"])
                    and "validation_plateau" not in emitted
                ):
                    found.append((rule["level"], step))
                    emitted.add("validation_plateau")
    return sorted(found, key=lambda item: (item[1], item[0]))


def assert_number(actual: Any, expected: float, context: str) -> None:
    assert isinstance(actual, (int, float)) and not isinstance(actual, bool), f"{context} is not numeric"
    assert math.isclose(float(actual), expected, rel_tol=1e-6, abs_tol=1e-7), (
        f"{context} is {actual}, expected {expected}"
    )


def normalized_report_runs(report: Any) -> tuple[dict[str, dict], list[str]]:
    if not isinstance(report, dict):
        return {}, ["report root is not an object"]
    container: Any = None
    for key in ("runs", "experiments", "run_summaries", "results"):
        if key in report:
            container = report[key]
            break
    if isinstance(container, dict):
        rows = []
        for run_id, value in container.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("run_id", run_id)
                rows.append(row)
    elif isinstance(container, list):
        rows = container
    else:
        return {}, ["report has no recognizable run collection"]
    indexed: dict[str, dict] = {}
    errors: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"run entry {index} is not an object")
            continue
        run_id = next((row.get(key) for key in ("run_id", "run", "name", "id") if row.get(key) is not None), None)
        if not isinstance(run_id, str) or not run_id:
            errors.append(f"run entry {index} has no usable identifier")
            continue
        if run_id in indexed:
            errors.append(f"run {run_id} appears more than once")
        indexed[run_id] = row
    return indexed, errors


def value_from(row: dict, kind: str, field: str) -> Any:
    group_aliases = {
        "final": ("final_validation", "latest_validation", "final", "latest", "last_validation"),
        "best": ("best_validation", "best", "best_eval", "optimum_validation"),
    }[kind]
    field_aliases = {
        "step": ("step", "global_step", "eval_step"),
        "val_loss": ("val_loss", "validation_loss", "loss"),
        "val_accuracy": ("val_accuracy", "validation_accuracy", "accuracy", "acc"),
    }[field]
    for group_key in group_aliases:
        group = row.get(group_key)
        if isinstance(group, dict):
            for field_key in field_aliases:
                if field_key in group:
                    return group[field_key]
    validation = row.get("validation")
    if isinstance(validation, dict):
        for group_key in group_aliases:
            group = validation.get(group_key)
            if isinstance(group, dict):
                for field_key in field_aliases:
                    if field_key in group:
                        return group[field_key]
    prefixes = ("final", "latest", "last") if kind == "final" else ("best", "minimum", "optimum")
    for prefix in prefixes:
        for field_key in field_aliases:
            for flat_key in (f"{prefix}_{field_key}", f"{field_key}_{prefix}"):
                if flat_key in row:
                    return row[flat_key]
    return None


def report_alert_count(row: dict) -> int | None:
    for key in ("alerts", "incidents", "diagnostic_alerts"):
        value = row.get(key)
        if isinstance(value, (list, dict)):
            return len(value)
    for key in ("alert_count", "num_alerts", "incident_count"):
        value = row.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def normalized_decision(row: dict) -> str | None:
    raw = next((row.get(key) for key in ("decision", "status", "action", "recommendation") if row.get(key) is not None), None)
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower().replace("_", " ").replace("-", " ")
    aliases = {
        "stop": "STOP",
        "halt": "STOP",
        "terminate": "STOP",
        "investigate": "INVESTIGATE",
        "review": "INVESTIGATE",
        "inspect": "INVESTIGATE",
        "continue": "CONTINUE",
        "keep running": "CONTINUE",
        "proceed": "CONTINUE",
    }
    return aliases.get(value)


def test_artifacts_execute_and_store_is_queryable(replayed_store: dict[str, Any]) -> None:
    """Requested artifacts open, the script replays, and the new local store answers CLI queries."""
    missing = [str(path) for path in (SCRIPT_PATH, STORE_PATH, REPORT_PATH) if not path.is_file()]
    assert not missing, f"missing requested monitoring artifacts: {missing}"
    try:
        load_json(STORE_PATH)
        load_json(REPORT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"requested JSON artifact is unreadable: {exc}")
    assert replayed_store["error"] is None, replayed_store["error"]
    fresh_store = replayed_store["path"]
    listing = run_cli(fresh_store, "list", "runs", "--project", SPECS["project"])
    assert set(listing.get("runs", [])) == set(RUN_IDS), (
        "fresh replay store is not queryable for every configured run"
    )
    unfinished = []
    for run_id in RUN_IDS:
        summary = run_cli(fresh_store, "get", "run", "--project", SPECS["project"], "--run", run_id)
        if summary.get("finished") is not True:
            unfinished.append(run_id)
    assert not unfinished, f"runs were not finalized after replay: {unfinished}"


def test_logged_metrics_and_configuration(replayed_store: dict[str, Any]) -> None:
    """Metric series and run configs in the fresh store match every supplied observation."""
    if replayed_store["error"] is not None:
        pytest.skip("fresh replay unavailable; root execution failure is reported by artifact criterion")
    store = replayed_store["path"]
    errors: list[str] = []
    specs_by_id = {row["run_id"]: row for row in SPECS["runs"]}
    for run_id in RUN_IDS:
        summary = run_cli(store, "get", "run", "--project", SPECS["project"], "--run", run_id)
        if summary.get("config") != specs_by_id[run_id]["config"]:
            errors.append(f"{run_id}: stored configuration differs from run_specs.json")
        for metric in (*POLICY["required_metrics"]["every_step"], *POLICY["required_metrics"]["when_observed"]):
            payload = run_cli(
                store,
                "get",
                "metric",
                "--project",
                SPECS["project"],
                "--run",
                run_id,
                "--metric",
                metric,
            )
            actual = [(int(item["step"]), item.get("value")) for item in payload.get("values", [])]
            expected = expected_metric_series(run_id, metric)
            if [step for step, _ in actual] != [step for step, _ in expected]:
                errors.append(f"{run_id}/{metric}: logged steps do not match supplied observations")
                continue
            for (step, actual_value), (_, expected_value) in zip(actual, expected):
                if expected_value is None:
                    if actual_value is not None:
                        errors.append(f"{run_id}/{metric}@{step}: non-finite source value should remain explicitly unavailable")
                elif not isinstance(actual_value, (int, float)) or isinstance(actual_value, bool) or not math.isclose(
                    float(actual_value), expected_value, rel_tol=1e-6, abs_tol=1e-7
                ):
                    errors.append(f"{run_id}/{metric}@{step}: got {actual_value}, expected {expected_value}")
    assert not errors, "metric/configuration fidelity problems:\n" + "\n".join(errors[:25])


def test_policy_alerts(replayed_store: dict[str, Any]) -> None:
    """Fresh-store alerts match the first qualifying policy events with no false positives."""
    if replayed_store["error"] is not None:
        pytest.skip("fresh replay unavailable; root execution failure is reported by artifact criterion")
    store = replayed_store["path"]
    errors = []
    for run_id in RUN_IDS:
        payload = run_cli(
            store,
            "list",
            "alerts",
            "--project",
            SPECS["project"],
            "--run",
            run_id,
        )
        actual = sorted(
            [(str(row.get("level", "")).lower(), int(row.get("step"))) for row in payload.get("alerts", [])],
            key=lambda item: (item[1], item[0]),
        )
        expected = expected_alerts(run_id)
        if actual != expected:
            errors.append(f"{run_id}: alerts {actual}, expected {expected}")
    assert not errors, "policy alert problems:\n" + "\n".join(errors)


def test_report_scope_and_validation_summaries(replayed_store: dict[str, Any]) -> None:
    """The report covers each run with correct latest/best validation facts and alert count."""
    try:
        report = load_json(REPORT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"report cannot be normalized: {exc}")
    indexed, errors = normalized_report_runs(report)
    if set(indexed) != set(RUN_IDS):
        errors.append(f"report run IDs are {sorted(indexed)}, expected {sorted(RUN_IDS)}")
    for run_id in RUN_IDS:
        row = indexed.get(run_id)
        if row is None:
            continue
        val_loss = expected_metric_series(run_id, "val_loss")
        val_accuracy = dict(expected_metric_series(run_id, "val_accuracy"))
        latest_step, latest_loss = val_loss[-1]
        best_step, best_loss = min(val_loss, key=lambda item: item[1])
        checks = [
            (value_from(row, "final", "step"), latest_step, f"{run_id} final step"),
            (value_from(row, "final", "val_loss"), latest_loss, f"{run_id} final val_loss"),
            (value_from(row, "final", "val_accuracy"), val_accuracy[latest_step], f"{run_id} final val_accuracy"),
            (value_from(row, "best", "step"), best_step, f"{run_id} best step"),
            (value_from(row, "best", "val_loss"), best_loss, f"{run_id} best val_loss"),
            (value_from(row, "best", "val_accuracy"), val_accuracy[best_step], f"{run_id} best val_accuracy"),
        ]
        for actual, expected, context in checks:
            try:
                assert_number(actual, float(expected), context)
            except AssertionError as exc:
                errors.append(str(exc))
        count = report_alert_count(row)
        expected_count = len(expected_alerts(run_id))
        if count != expected_count:
            errors.append(f"{run_id}: report alert count is {count}, expected {expected_count}")
    assert not errors, "report coverage/summary problems:\n" + "\n".join(errors[:30])


def test_report_triage_decisions() -> None:
    """Per-run and optional aggregate decisions agree with the alert-level priority."""
    try:
        report = load_json(REPORT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"report cannot be normalized: {exc}")
    indexed, errors = normalized_report_runs(report)
    expected: dict[str, str] = {}
    for run_id in RUN_IDS:
        levels = {level for level, _ in expected_alerts(run_id)}
        expected[run_id] = "STOP" if "error" in levels else "INVESTIGATE" if "warn" in levels else "CONTINUE"
        if run_id in indexed:
            actual = normalized_decision(indexed[run_id])
            if actual != expected[run_id]:
                errors.append(f"{run_id}: decision is {actual}, expected {expected[run_id]}")
    summary = report.get("decision_summary") if isinstance(report, dict) else None
    if isinstance(summary, dict):
        for decision in ("STOP", "INVESTIGATE", "CONTINUE"):
            raw = next((summary.get(key) for key in (decision, decision.lower()) if key in summary), None)
            expected_members = {run_id for run_id, value in expected.items() if value == decision}
            if isinstance(raw, list) and set(raw) != expected_members:
                errors.append(f"decision_summary {decision} members disagree with per-run decisions")
            elif isinstance(raw, int) and raw != len(expected_members):
                errors.append(f"decision_summary {decision} count disagrees with per-run decisions")
    assert not errors, "triage decision problems:\n" + "\n".join(errors)
