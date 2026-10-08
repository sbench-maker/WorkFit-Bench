from __future__ import annotations

import ast
import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT = RESULTS_DIR / "first-response-sla-tutorial.ipynb"
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SNAPSHOT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
TARGETS = {"urgent": 30, "high": 120, "normal": 480, "low": 1440}

ALIASES = {
    "label": {"priority", "channel", "group", "name", "label", "category", "severity"},
    "eligible": {"eligible", "eligiblecount", "eligibletickets", "total", "count", "tickets"},
    "met": {"met", "within", "withinsla", "withintarget", "ontime", "compliant"},
    "breached": {"breached", "breach", "missed", "late", "outsidesla"},
    "pending": {"pending", "pendingnotdue", "notdue", "unansweredintarget"},
    "rate": {"compliancerate", "compliance", "rate", "attainment", "slarate", "percentmet"},
}


def cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source)


def load_notebook() -> Tuple[Optional[dict[str, Any]], Optional[str]]:
    if not OUTPUT.is_file():
        return None, f"missing requested notebook: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"notebook is not readable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "notebook root must be a JSON object"
    return payload, None


def expected_summaries() -> dict[str, dict[str, dict[str, float]]]:
    buckets: dict[str, dict[str, dict[str, int]]] = {
        "priority": defaultdict(lambda: {"eligible": 0, "met": 0, "breached": 0, "pending": 0}),
        "channel": defaultdict(lambda: {"eligible": 0, "met": 0, "breached": 0, "pending": 0}),
    }
    with (DATA_DIR / "tickets.csv").open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    for row in records:
        if row["is_test"].strip().lower() == "true" or row["requester_type"] == "employee":
            continue
        opened = datetime.strptime(row["opened_at"], STAMP_FORMAT).replace(tzinfo=timezone.utc)
        if row["first_response_at"]:
            responded = datetime.strptime(row["first_response_at"], STAMP_FORMAT).replace(tzinfo=timezone.utc)
            elapsed = (responded - opened).total_seconds() / 60
            result = "met" if elapsed <= TARGETS[row["priority"]] else "breached"
        else:
            elapsed = (SNAPSHOT - opened).total_seconds() / 60
            result = "pending" if elapsed <= TARGETS[row["priority"]] else "breached"
        for grouping in ("priority", "channel"):
            bucket = buckets[grouping][row[grouping]]
            bucket["eligible"] += 1
            bucket[result] += 1

    expected: dict[str, dict[str, dict[str, float]]] = {}
    for grouping, groups in buckets.items():
        expected[grouping] = {}
        for label, counts in groups.items():
            decided = counts["met"] + counts["breached"]
            expected[grouping][label] = {
                **counts,
                "rate": round(100 * counts["met"] / decided, 1),
            }
    return expected


RUNNER = r'''
import ast
import contextlib
import io
import json
import sys

cells = json.loads(sys.stdin.read())
namespace = {"__name__": "__main__"}
stdout = io.StringIO()

def serializable(value, depth=0, seen=None):
    if seen is None:
        seen = set()
    if depth > 7:
        return "<depth-limit>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    identity = id(value)
    if identity in seen:
        return "<cycle>"
    if isinstance(value, dict):
        seen.add(identity)
        result = {str(k): serializable(v, depth + 1, seen) for k, v in list(value.items())[:1000]}
        seen.remove(identity)
        return result
    if isinstance(value, (list, tuple, set)):
        seen.add(identity)
        result = [serializable(item, depth + 1, seen) for item in list(value)[:1000]]
        seen.remove(identity)
        return result
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    return None

try:
    for index, source in enumerate(cells):
        tree = ast.parse(source, filename=f"<notebook-cell-{index}>", mode="exec")
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            tree.body[-1] = ast.Assign(
                targets=[ast.Name(id=f"display_value_{index}", ctx=ast.Store())],
                value=tree.body[-1].value,
            )
            ast.fix_missing_locations(tree)
        with contextlib.redirect_stdout(stdout):
            exec(compile(tree, f"<notebook-cell-{index}>", "exec"), namespace, namespace)
except BaseException as exc:
    result = {"ok": False, "error": f"cell {index}: {type(exc).__name__}: {exc}", "stdout": stdout.getvalue()}
else:
    values = {}
    for name, value in namespace.items():
        if name.startswith("__"):
            continue
        converted = serializable(value)
        if converted is not None:
            values[name] = converted
    result = {"ok": True, "variables": values, "stdout": stdout.getvalue()}
print("__SKILLSBENCH_NOTEBOOK_RESULT__" + json.dumps(result, ensure_ascii=False))
'''


def execute_notebook(notebook: dict[str, Any]) -> dict[str, Any]:
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        return {"ok": False, "error": "notebook cells is not a list"}
    sources = [cell_source(cell) for cell in cells if isinstance(cell, dict) and cell.get("cell_type") == "code"]
    env = dict(os.environ)
    env["TASK_DATA_DIR"] = str(DATA_DIR)
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", RUNNER],
            input=json.dumps(sources),
            text=True,
            capture_output=True,
            timeout=30,
            cwd=RESULTS_DIR if RESULTS_DIR.is_dir() else None,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"fresh-run process failed: {exc}"}
    marker = "__SKILLSBENCH_NOTEBOOK_RESULT__"
    position = completed.stdout.rfind(marker)
    if position < 0:
        return {
            "ok": False,
            "error": f"execution did not return a result (exit {completed.returncode}): {completed.stderr[-500:]}",
        }
    try:
        result = json.loads(completed.stdout[position + len(marker):].strip())
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"execution result was invalid: {exc}"}
    if completed.returncode != 0 and result.get("ok"):
        return {"ok": False, "error": f"fresh-run process exited {completed.returncode}"}
    return result


@pytest.fixture(scope="module")
def notebook_and_run() -> Tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]:
    notebook, error = load_notebook()
    executed = execute_notebook(notebook) if notebook is not None else {"ok": False, "error": error}
    return notebook, error, executed


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*%?\s*", value)
        if match:
            return float(match.group(1))
    return None


def discover_summary_rows(payload: Any) -> list[dict[str, Any]]:
    expected_labels = set(TARGETS) | {"email", "web", "chat"}
    rows: list[dict[str, Any]] = []

    def walk(value: Any, parent_label: Optional[str] = None) -> None:
        if isinstance(value, dict):
            normalized = {normalize_key(key): item for key, item in value.items()}
            label = parent_label
            for alias in ALIASES["label"]:
                if alias in normalized and normalize_key(normalized[alias]) in expected_labels:
                    label = normalize_key(normalized[alias])
                    break
            metrics: dict[str, float] = {}
            for metric in ("eligible", "met", "breached", "pending", "rate"):
                for alias in ALIASES[metric]:
                    if alias in normalized:
                        parsed = number(normalized[alias])
                        if parsed is not None:
                            metrics[metric] = parsed
                            break
            if label in expected_labels and all(metric in metrics for metric in ("eligible", "met", "breached", "pending", "rate")):
                rows.append({"label": label, **metrics})
            for key, child in value.items():
                normalized_key = normalize_key(key)
                walk(child, normalized_key if normalized_key in expected_labels else None)
        elif isinstance(value, list):
            for child in value:
                walk(child, parent_label)

    walk(payload)
    return rows


def row_matches(actual: dict[str, Any], expected: dict[str, float]) -> bool:
    for metric in ("eligible", "met", "breached", "pending"):
        if abs(float(actual[metric]) - float(expected[metric])) > 0.001:
            return False
    actual_rate = float(actual["rate"])
    if 0 <= actual_rate <= 1 and expected["rate"] > 1:
        actual_rate *= 100
    return abs(actual_rate - expected["rate"]) <= 0.11


def assert_grouping_matches(executed: dict[str, Any], grouping: str) -> None:
    assert executed.get("ok") is True, f"cannot inspect {grouping} summary because fresh execution failed: {executed.get('error')}"
    rows = discover_summary_rows(executed.get("variables", {}))
    expected = expected_summaries()[grouping]
    missing_or_wrong = []
    for label, expected_row in expected.items():
        candidates = [row for row in rows if row["label"] == label]
        if not any(row_matches(row, expected_row) for row in candidates):
            missing_or_wrong.append(label)
    assert not missing_or_wrong, (
        f"executed notebook has no correct {grouping} summary row for {missing_or_wrong}; "
        "expected eligibility, boundary, unanswered-ticket, pending-denominator, and rate rules to agree with the policy"
    )
    matched = [
        next(row for row in rows if row["label"] == label and row_matches(row, expected_row))
        for label, expected_row in expected.items()
    ]
    eligible_total = sum(row["eligible"] for row in matched)
    assert eligible_total == 239, f"{grouping} summary covers {eligible_total} eligible tickets instead of 239"


def test_notebook_artifact_is_usable(
    notebook_and_run: Tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]
) -> None:
    notebook, error, _ = notebook_and_run
    assert error is None and notebook is not None, error
    assert notebook.get("nbformat") == 4, "requested artifact is not an nbformat 4 notebook"
    assert isinstance(notebook.get("nbformat_minor"), int), "notebook is missing an integer nbformat_minor"
    cells = notebook.get("cells")
    assert isinstance(cells, list) and cells, "notebook has no ordered cells"
    assert all(isinstance(cell, dict) and cell.get("cell_type") in {"markdown", "code", "raw"} for cell in cells), (
        "notebook contains malformed or unsupported cell entries"
    )
    markdown_cells = [cell for cell in cells if cell.get("cell_type") == "markdown" and cell_source(cell).strip()]
    code_cells = [cell for cell in cells if cell.get("cell_type") == "code" and cell_source(cell).strip()]
    assert len(markdown_cells) >= 4 and len(code_cells) >= 4, (
        "notebook lacks the substantive markdown/code mix needed for the requested step-by-step tutorial"
    )
    first_substantive = next(cell for cell in cells if cell_source(cell).strip())
    assert first_substantive.get("cell_type") == "markdown", "tutorial should orient the reader before running code"
    combined = "\n".join(cell_source(cell) for cell in cells)
    unresolved = [
        phrase for phrase in (
            "# Tutorial: TITLE",
            "Describe who this is for.",
            "Explain what the next cell does in plain language.",
            "Try a different input.",
        )
        if phrase in combined
    ]
    assert not unresolved, f"notebook still contains unfilled scaffold text: {unresolved}"


def test_notebook_runs_top_to_bottom_with_standard_library(
    notebook_and_run: Tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]
) -> None:
    notebook, error, executed = notebook_and_run
    assert error is None and notebook is not None, error
    imports: set[str] = set()
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        source = cell_source(cell)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"code cell {index} is not valid Python: {exc}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imports.add("<relative-import>")
                elif node.module:
                    imports.add(node.module.split(".", 1)[0])
    allowed = set(getattr(sys, "stdlib_module_names", ())) | {
        "__future__", "csv", "os", "collections", "datetime", "pathlib", "json", "math",
        "random", "statistics", "re", "typing", "itertools", "functools", "decimal",
    }
    nonstandard = sorted(imports - allowed)
    assert not nonstandard, f"notebook imports non-standard or local packages despite the offline standard-library request: {nonstandard}"
    assert executed.get("ok") is True, f"notebook does not run top-to-bottom from a clean state: {executed.get('error')}"


def test_priority_summary_matches_policy(
    notebook_and_run: Tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]
) -> None:
    assert_grouping_matches(notebook_and_run[2], "priority")


def test_channel_summary_matches_policy(
    notebook_and_run: Tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]
) -> None:
    assert_grouping_matches(notebook_and_run[2], "channel")
