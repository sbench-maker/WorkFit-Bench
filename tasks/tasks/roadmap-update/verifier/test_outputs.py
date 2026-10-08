from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "roadmap_update.md"
HORIZONS = ["Now", "Next", "Later"]
ID_RE = re.compile(r"\bRM[-_ ]?0*(\d{1,3})\b", re.IGNORECASE)
STATUS_PATTERNS = [
    ("Not Started", re.compile(r"\b(?:not[\s_-]*started|planned|todo)\b", re.IGNORECASE)),
    ("At Risk", re.compile(r"\b(?:at[\s_-]*risk|amber|yellow|watch)\b", re.IGNORECASE)),
    ("On Track", re.compile(r"\b(?:on[\s_-]*track|in[\s_-]*progress|green)\b", re.IGNORECASE)),
    ("Completed", re.compile(r"\b(?:completed|complete|done|shipped)\b", re.IGNORECASE)),
    ("Blocked", re.compile(r"\bblocked\b", re.IGNORECASE)),
]


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def canonical_id(match: re.Match[str]) -> str:
    return f"RM-{int(match.group(1)):03d}"


def load_text() -> str:
    assert OUTPUT_PATH.is_file(), "roadmap_update.md is missing, so the portfolio review has no deliverable"
    try:
        text = OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        pytest.fail(f"roadmap_update.md is not readable UTF-8 text: {exc}")
    assert text.strip(), "roadmap_update.md is empty"
    return text


def load_text_optional() -> str | None:
    if not OUTPUT_PATH.is_file():
        return None
    try:
        text = OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    return text if text.strip() else None


def heading_concepts(text: str) -> set[str]:
    concepts: set[str] = set()
    for line in text.splitlines():
        if not re.match(r"^\s*#{1,6}\s+", line):
            continue
        heading = re.sub(r"[^a-z0-9]+", " ", line.lower())
        if "status" in heading or "overview" in heading:
            concepts.add("status")
        if "roadmap" in heading or ("now" in heading and "next" in heading and "later" in heading):
            concepts.add("roadmap")
        if "change" in heading or "before" in heading or "prior" in heading:
            concepts.add("changes")
        if "risk" in heading or "dependenc" in heading or "blocker" in heading:
            concepts.add("risks")
        if "rationale" in heading or "decision" in heading or "tradeoff" in heading or "trade off" in heading:
            concepts.add("rationale")
    return concepts


def horizon_tokens(line: str) -> list[str]:
    found = []
    for horizon in HORIZONS:
        if re.search(rf"\b{horizon}\b", line, re.IGNORECASE):
            found.append(horizon)
    return found


def status_from_line(line: str) -> str | None:
    if "|" in line:
        exact = {
            "not started": "Not Started", "planned": "Not Started", "todo": "Not Started",
            "at risk": "At Risk", "amber": "At Risk", "yellow": "At Risk", "watch": "At Risk",
            "on track": "On Track", "in progress": "On Track", "green": "On Track",
            "completed": "Completed", "complete": "Completed", "done": "Completed", "shipped": "Completed",
            "blocked": "Blocked",
        }
        for cell in line.split("|"):
            normalized = re.sub(r"[^a-z]+", " ", cell.lower()).strip()
            if normalized in exact:
                return exact[normalized]
    found = [status for status, pattern in STATUS_PATTERNS if pattern.search(line)]
    return found[0] if len(found) == 1 else None


def extract_entries(text: str) -> tuple[dict[str, dict[str, str]], dict[str, list[str]]]:
    """Normalize either horizon sections or a single table with horizon/status columns."""
    candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    active_horizon: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if heading:
            tokens = horizon_tokens(heading.group(1))
            active_horizon = tokens[0] if len(tokens) == 1 else None
            continue
        matches = list(ID_RE.finditer(line))
        if not matches:
            continue
        status = status_from_line(line)
        tokens = horizon_tokens(line)
        horizon = tokens[0] if len(tokens) == 1 else active_horizon
        if not status or not horizon or (active_horizon is None and not line.lstrip().startswith("|")):
            continue
        for match in matches:
            candidates[canonical_id(match)].append({"horizon": horizon, "status": status, "line": line})

    entries: dict[str, dict[str, str]] = {}
    conflicts: dict[str, list[str]] = {}
    for item_id, rows in candidates.items():
        semantic = {(row["horizon"], row["status"]) for row in rows}
        if len(semantic) == 1:
            entries[item_id] = rows[0]
        else:
            conflicts[item_id] = [row["line"] for row in rows]
    return entries, conflicts


def date_horizon(value: str) -> str:
    day = date.fromisoformat(value)
    if day <= date(2026, 10, 11):
        return "Now"
    if day <= date(2026, 12, 6):
        return "Next"
    return "Later"


def expected_statuses() -> dict[str, str]:
    values = {row["initiative_id"]: row["status"] for row in read_csv("current_roadmap.csv")}
    values.update({"RM-012": "Blocked", "RM-014": "Blocked", "RM-016": "Blocked", "RM-033": "Not Started"})
    return values


def extract_change_section(text: str) -> str:
    lines = text.splitlines()
    start = None
    level = None
    for index, line in enumerate(lines):
        match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        title = match.group(2).lower()
        if any(word in title for word in ("change", "before", "prior roadmap", "what moved")):
            start, level = index + 1, len(match.group(1))
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        match = re.match(r"^\s*(#{1,6})\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def id_lines(text: str, item_id: str) -> list[str]:
    number = int(item_id.split("-")[1])
    pattern = re.compile(rf"\bRM[-_ ]?0*{number}\b", re.IGNORECASE)
    return [line for line in text.splitlines() if pattern.search(line)]


def test_portfolio_scope_and_status() -> None:
    text = load_text_optional()
    assert text is not None, "roadmap entries cannot be assessed because the requested artifact is unavailable"
    entries, conflicts = extract_entries(text)
    expected = expected_statuses()
    missing = sorted(set(expected) - set(entries))
    unexpected = sorted(set(entries) - set(expected))
    wrong_status = {
        item_id: {"actual": entries[item_id]["status"], "expected": status}
        for item_id, status in expected.items()
        if item_id in entries and entries[item_id]["status"] != status
    }
    assert not (missing or unexpected or conflicts or wrong_status), (
        "the updated roadmap's traceable scope/status is inconsistent: "
        f"missing={missing}, unexpected={unexpected}, conflicting_entries={sorted(conflicts)}, "
        f"wrong_status={wrong_status}"
    )


def test_deadlines_dependencies_and_capacity() -> None:
    text = load_text_optional()
    assert text is not None, "planning constraints cannot be assessed because the requested artifact is unavailable"
    entries, _ = extract_entries(text)
    source_rows = {row["initiative_id"]: row for row in read_csv("current_roadmap.csv")}
    change = json.loads((DATA_DIR / "change_request.json").read_text(encoding="utf-8"))
    new_item = change["new_initiative"]
    issues: list[str] = []

    # Only evaluate parsed entries here; scope omissions belong to the scope criterion.
    fixed_placements = {"RM-033": "Next", "RM-012": "Later", "RM-014": "Later", "RM-016": "Later"}
    for item_id, expected in fixed_placements.items():
        if item_id in entries and entries[item_id]["horizon"] != expected:
            issues.append(f"{item_id} is {entries[item_id]['horizon']}, expected {expected}")

    deadlines = {item_id: row["hard_deadline"] for item_id, row in source_rows.items() if row["hard_deadline"]}
    deadlines[new_item["initiative_id"]] = new_item["hard_deadline"]
    for item_id, deadline in deadlines.items():
        if item_id in entries and HORIZONS.index(entries[item_id]["horizon"]) > HORIZONS.index(date_horizon(deadline)):
            issues.append(f"{item_id} is after its hard deadline {deadline}")

    for dep in read_csv("dependencies.csv"):
        target = dep["initiative_id"]
        source = dep["dependency_ref"]
        if target not in entries:
            continue
        if dep["dependency_type"] == "external" and dep["current_ready_date"]:
            ready = date_horizon(dep["current_ready_date"])
            if HORIZONS.index(entries[target]["horizon"]) < HORIZONS.index(ready):
                issues.append(f"{target} precedes external dependency {dep['dependency_id']} ready {dep['current_ready_date']}")
        elif source in entries and HORIZONS.index(entries[target]["horizon"]) < HORIZONS.index(entries[source]["horizon"]):
            issues.append(f"{target} is earlier than prerequisite {source}")

    effort: dict[str, dict[str, int]] = defaultdict(dict)
    for row in read_csv("initiative_effort.csv"):
        effort[row["initiative_id"]][row["team"]] = int(row["remaining_points"])
    effort[new_item["initiative_id"]] = {team: int(points) for team, points in new_item["effort_by_team"].items()}
    capacity: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in read_csv("weekly_capacity.csv"):
        capacity[row["horizon"]][row["team"]] += int(row["available_points"])
    load: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item_id, entry in entries.items():
        if entry["status"] == "Completed":
            continue
        for team, points in effort.get(item_id, {}).items():
            load[entry["horizon"]][team] += points
    for horizon, team_values in load.items():
        for team, used in team_values.items():
            available = capacity[horizon].get(team, 0)
            if used > available:
                issues.append(f"{horizon}/{team} uses {used} points with {available} available")

    assert not issues, "the roadmap violates material planning constraints: " + "; ".join(issues)


def test_before_after_change_accounting() -> None:
    text = load_text_optional()
    assert text is not None, "changes cannot be assessed because the requested artifact is unavailable"
    entries, _ = extract_entries(text)
    source = {row["initiative_id"]: row["current_horizon"] for row in read_csv("current_roadmap.csv")}
    changes = extract_change_section(text)
    issues: list[str] = []

    if "RM-033" in entries:
        lines = id_lines(changes, "RM-033")
        joined = " ".join(lines)
        if not lines or not re.search(r"\b(?:add(?:ed|ition)?|new|not on|outside)\b", joined, re.IGNORECASE) or entries["RM-033"]["horizon"].lower() not in joined.lower():
            issues.append("RM-033 is not documented as an addition with its updated horizon")

    for item_id, current in source.items():
        if item_id not in entries or entries[item_id]["horizon"] == current:
            continue
        updated = entries[item_id]["horizon"]
        joined = " ".join(id_lines(changes, item_id))
        if not joined or current.lower() not in joined.lower() or updated.lower() not in joined.lower():
            issues.append(f"{item_id} lacks a consistent {current}-to-{updated} before/after entry")

    assert not issues, "the before/after change record is incomplete or inconsistent: " + "; ".join(issues)
