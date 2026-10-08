from __future__ import annotations

import csv
import os
import re
from collections import Counter
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
TASKS_PATH = RESULTS / "updated_workspace" / "TASKS.md"
MEMORY_DIR = RESULTS / "updated_workspace" / "memory"
REPORT_PATH = RESULTS / "update_report.md"

APPROVED_TRACKER = {"WK-1002", "WK-1004", "WK-1005", "WK-1006", "WK-1008", "WK-1015", "WK-1018"}
DECLINED_TRACKER = {"WK-1003", "WK-1007", "WK-1017"}
APPROVED_ACTIVITY = {"ACT-0031", "ACT-0058", "ACT-0117"}
DECLINED_ACTIVITY = {"ACT-0103"}
BASELINE_IDS = {f"LOCAL-{value:03d}" for value in range(1, 25)} | {"LOCAL-030", "LOCAL-031", "LOCAL-040", "LOCAL-041"}
BASELINE_MEMORY = {
    "glossary.md",
    "people/todd-martinez.md",
    "people/priya-nair.md",
    "people/ren-zhou.md",
    "projects/apollo.md",
    "projects/atlas.md",
    "projects/cedar.md",
    "projects/orion.md",
}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def task_records() -> tuple[dict[str, dict[str, str]], Counter[str]]:
    if not TASKS_PATH.is_file():
        pytest.skip("TASKS.md is unavailable; artifact usability records the root failure")
    text = TASKS_PATH.read_text(encoding="utf-8")
    state = None
    records: dict[str, dict[str, str]] = {}
    counts: Counter[str] = Counter()
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            heading = norm(line.lstrip("# "))
            if any(word in heading for word in ("someday", "later", "backlog")):
                state = "someday"
            elif any(word in heading for word in ("done", "complete", "closed", "finished")):
                state = "done"
            elif any(word in heading for word in ("active", "current", "open", "in progress")):
                state = "active"
            continue
        ids = re.findall(r"\b(?:LOCAL|WK|ACT)-\d+\b", line, flags=re.I)
        if not ids:
            continue
        task_id = ids[0].upper()
        inferred = state
        if re.search(r"\[[xX]\]", line) or re.search(r"\bstatus\s*[:=]\s*(?:done|completed|closed)\b", line, flags=re.I):
            inferred = "done"
        elif re.search(r"\bstatus\s*[:=]\s*(?:someday|later|backlog)\b", line, flags=re.I):
            inferred = "someday"
        elif re.search(r"\bstatus\s*[:=]\s*(?:active|open|in[_ -]?progress)\b", line, flags=re.I):
            inferred = "active"
        if inferred is None:
            continue
        counts[task_id] += 1
        records.setdefault(task_id, {"state": inferred, "text": line})
    if not records:
        pytest.skip("TASKS.md could not be normalized into task records; artifact usability records the root failure")
    return records, counts


def all_memory_text() -> str:
    if not MEMORY_DIR.is_dir():
        pytest.skip("memory directory is unavailable; artifact usability records the root failure")
    paths = sorted(MEMORY_DIR.rglob("*.md"))
    if not paths:
        pytest.skip("memory Markdown is unavailable; artifact usability records the root failure")
    return norm("\n".join(path.read_text(encoding="utf-8") for path in paths))


def read_tracker() -> dict[str, dict[str, str]]:
    with (DATA / "project_tracker.csv").open(encoding="utf-8", newline="") as handle:
        return {row["task_id"]: row for row in csv.DictReader(handle)}


def test_artifact_usability() -> None:
    assert TASKS_PATH.is_file(), "the requested updated_workspace/TASKS.md is missing"
    assert REPORT_PATH.is_file(), "the requested update_report.md is missing"
    assert MEMORY_DIR.is_dir(), "the requested updated workspace has no memory directory"
    task_text = TASKS_PATH.read_text(encoding="utf-8")
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    assert len(task_text.strip()) >= 500, "TASKS.md is too sparse to be the finished supplied workspace"
    assert len(report_text.strip()) >= 120, "the change report is empty or not meaningfully readable"
    present_memory = {str(path.relative_to(MEMORY_DIR)) for path in MEMORY_DIR.rglob("*.md")}
    missing = sorted(BASELINE_MEMORY - present_memory)
    assert not missing, f"supplied memory artifacts were not retained: {missing}"


def test_confirmed_task_state_transitions() -> None:
    records, counts = task_records()
    expected_states = {
        "LOCAL-001": "active",
        "LOCAL-004": "active",
        "LOCAL-005": "someday",
        "LOCAL-006": "done",
        "LOCAL-007": "active",
        "LOCAL-008": "done",
        "LOCAL-009": "done",
        "LOCAL-010": "active",
        **{task_id: "active" for task_id in APPROVED_TRACKER | APPROVED_ACTIVITY},
    }
    missing = sorted(set(expected_states) - set(records))
    assert not missing, f"confirmed task changes are missing: {missing}"
    wrong_states = {task_id: records[task_id]["state"] for task_id, expected in expected_states.items() if records[task_id]["state"] != expected}
    assert not wrong_states, f"confirmed tasks are in the wrong state: {wrong_states}"
    assert "2026-08-24" in records["LOCAL-001"]["text"], "LOCAL-001 was not rescheduled to the confirmed date"
    assert "2026-09-04" in records["LOCAL-004"]["text"], "LOCAL-004 was not rescheduled to the confirmed date"
    for task_id in APPROVED_TRACKER | APPROVED_ACTIVITY:
        assert counts[task_id] == 1, f"confirmed addition {task_id} should appear exactly once"
    for task_id in DECLINED_TRACKER | DECLINED_ACTIVITY:
        assert task_id not in records, f"declined item {task_id} was added"
    assert "WK-1001" not in records and "WK-1009" not in records, "fuzzy-matched tracker items were duplicated instead of retaining their local tasks"


def test_memory_updates_and_unresolved_gaps() -> None:
    memory = all_memory_text()
    report = norm(REPORT_PATH.read_text(encoding="utf-8")) if REPORT_PATH.is_file() else ""
    assert all(term in memory for term in ("nebula", "partner enablement pilot", "discovery", "todd martinez")), "confirmed Nebula project context is incomplete"
    assert all(term in memory for term in ("devon li", "observability lead", "atlas", "telemetry review")), "confirmed Devon Li context is incomplete"
    assert all(term in memory for term in ("atlas", "launch-ready", "security sign-off", "act-0024")), "the confirmed Atlas status enrichment is missing or unsupported"
    assert all(term in memory for term in ("todd martinez", "priya nair", "covers", "atlas security sign-off", "act-0088")), "the confirmed temporary coverage relationship is missing or unsupported"
    glossary = norm((MEMORY_DIR / "glossary.md").read_text(encoding="utf-8"))
    assert not re.search(r"\brfd\s*[:=\-–—]\s*[a-z]", glossary), "RFD was given an unconfirmed glossary expansion"
    assert "rfd" in report and any(term in report for term in ("unresolved", "unknown", "clarif", "what does", "ask maya")), "the unresolved RFD gap was not surfaced for Maya"


def test_authorized_scope_and_source_references() -> None:
    records, counts = task_records()
    missing_baseline = sorted(BASELINE_IDS - set(records))
    assert not missing_baseline, f"existing task records were lost from the finished workspace: {missing_baseline}"
    duplicated_baseline = sorted(task_id for task_id in BASELINE_IDS if counts[task_id] != 1)
    assert not duplicated_baseline, f"existing task records were duplicated: {duplicated_baseline}"
    introduced = {task_id for task_id in records if task_id.startswith(("WK-", "ACT-"))}
    unauthorized = sorted(introduced - APPROVED_TRACKER - APPROVED_ACTIVITY)
    assert not unauthorized, f"unapproved or out-of-scope tasks were introduced: {unauthorized}"
    tracker = read_tracker()
    for task_id in APPROVED_TRACKER:
        row = tracker[task_id]
        text = norm(records[task_id]["text"])
        assert row["assignee_id"] == "USR-MAYA", f"fixture error: {task_id} is not Maya's assignment"
        assert norm(row["source_ref"]) in text, f"new tracker task {task_id} lost its source reference"
        assert row["due_date"] in records[task_id]["text"], f"new tracker task {task_id} lost its tracker due date"
    for task_id in APPROVED_ACTIVITY:
        assert f"activity/{task_id}".casefold() in norm(records[task_id]["text"]), f"activity follow-up {task_id} lost its source reference"
