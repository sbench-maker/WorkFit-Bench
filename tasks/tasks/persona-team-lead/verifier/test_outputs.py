from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()
OUTPUT_PATH = RESULTS_DIR / "output.json"


def key_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def pick(mapping: dict, *aliases: str, default: Any = None) -> Any:
    normalized = {key_norm(str(key)): value for key, value in mapping.items()}
    for alias in aliases:
        if key_norm(alias) in normalized:
            return normalized[key_norm(alias)]
    return default


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        # Accept grouping by operation/status/section.
        rows: list = []
        for child in value.values():
            if isinstance(child, list):
                rows.extend(child)
            elif isinstance(child, dict):
                rows.append(child)
        return rows or [value]
    return [value]


def nullish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "unassigned", "tbd", "unknown"}:
        return None
    return value


def norm_date(value: Any) -> str | None:
    value = nullish(value)
    if value is None:
        return None
    match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", str(value))
    if match:
        year, month, day = (int(part) for part in match.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    month_match = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b",
        str(value),
        re.IGNORECASE,
    )
    if not month_match:
        return str(value).strip().lower()
    month_names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    month = month_names.index(month_match.group(1)[:3].lower()) + 1
    day = int(month_match.group(2))
    year = int(month_match.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}"


def norm_operation(value: Any, status: str, task_id: str | None) -> str:
    raw = key_norm(str(value or ""))
    if raw in {"create", "new", "add", "insert", "proposecreate"}:
        return "create"
    if raw in {"update", "edit", "modify", "change", "close", "cancel", "reopen", "proposeupdate"}:
        return "update"
    if task_id:
        return "update"
    return "create" if status else raw


def norm_priority(value: Any) -> str:
    raw = key_norm(str(value or ""))
    aliases = {
        "p0": "critical", "urgent": "critical", "critical": "critical", "sev1": "critical",
        "p1": "high", "high": "high", "important": "high",
        "p2": "normal", "medium": "normal", "normal": "normal", "standard": "normal",
    }
    return aliases.get(raw, raw)


def norm_status(value: Any) -> str:
    raw = key_norm(str(value or ""))
    aliases = {
        "open": "todo", "pending": "todo", "notstarted": "todo", "reopened": "todo", "reopen": "todo", "todo": "todo",
        "inprogress": "in_progress", "working": "in_progress", "active": "in_progress",
        "blocked": "blocked", "waiting": "blocked",
        "done": "done", "complete": "done", "completed": "done", "closed": "done",
        "cancelled": "cancelled", "canceled": "cancelled", "void": "cancelled",
        "needsconfirmation": "todo", "reviewrequired": "todo",
    }
    return aliases.get(raw, raw)


def norm_owner(value: Any) -> str | None:
    value = nullish(value)
    if isinstance(value, dict):
        value = pick(value, "owner_id", "user_id", "id", "email", "name")
    value = nullish(value)
    if value is None:
        return None
    raw = str(value).strip()
    users = {
        "maya": "U001", "maya chen": "U001", "maya.chen@northstar.example": "U001",
        "elena": "U002", "elena park": "U002", "elena.park@northstar.example": "U002",
        "idris": "U003", "idris okafor": "U003", "idris.okafor@northstar.example": "U003",
        "priya": "U004", "priya shah": "U004", "priya.shah@northstar.example": "U004",
        "tomas": "U005", "tomas reed": "U005", "tomas.reed@northstar.example": "U005",
    }
    return users.get(raw.lower().lstrip("@"), raw.upper())


def norm_account(value: Any) -> str | None:
    value = nullish(value)
    if isinstance(value, dict):
        value = pick(value, "account_id", "customer_id", "id", "name", "account_name")
    value = nullish(value)
    if value is None:
        return None
    raw = str(value).strip()
    accounts = {
        "nimbus harbor": "A001", "cedar labs": "A002", "aster retail": "A003",
        "juniper transit": "A004", "mercury fleet": "A005", "delta data": "A006",
        "solace foods": "A007", "atlas works": "A008", "bluepeak systems": "A009",
    }
    return accounts.get(raw.lower(), raw.upper())


def norm_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return float(match.group()) if match else None


def norm_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"true", "yes", "y", "1", "required", "needs_review", "needs confirmation"}


def norm_sources(value: Any) -> set[str]:
    parts: list[Any] = []
    if isinstance(value, dict):
        for child in value.values():
            parts.extend(as_list(child))
    else:
        for child in as_list(value):
            if isinstance(child, str):
                parts.extend(re.split(r"[|,;\s]+", child))
            else:
                parts.append(child)
    sources: set[str] = set()
    for part in parts:
        if isinstance(part, dict):
            part = pick(part, "source_ref", "ref", "id", "source_id")
        if part is None:
            continue
        raw = str(part).strip().upper().replace("/", ":")
        raw = re.sub(r"^(EMAIL|MAIL):?", "EMAIL:", raw)
        raw = re.sub(r"^(CHAT|MESSAGE):?", "CHAT:", raw)
        if raw.startswith("THR-"):
            raw = "EMAIL:" + raw
        elif raw.startswith("CH-"):
            raw = "CHAT:" + raw
        if re.fullmatch(r"(?:EMAIL:THR-\d{3}|CHAT:CH-K\d{3}|TASK:TSK-\d{3})", raw):
            sources.add(raw.lower())
    return sources


def flatten_strings(value: Any) -> str:
    values: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            values.append(str(key))
            values.append(flatten_strings(child))
    elif isinstance(value, list):
        for child in value:
            values.append(flatten_strings(child))
    elif value is not None:
        values.append(str(value))
    return " ".join(values)


@dataclass
class Change:
    raw: dict
    operation: str
    task_id: str | None
    account_id: str | None
    title: str
    owner_id: str | None
    due_date: str | None
    priority: str
    status: str
    sources: set[str]
    review_required: bool


@dataclass
class Model:
    raw: dict | None
    error: str | None
    changes: list[Change]
    attention: Any
    digest: Any
    chat_draft: Any


def find_section(root: dict, *aliases: str) -> Any:
    direct = pick(root, *aliases)
    if direct is not None:
        return direct
    for wrapper_name in ("coordination_packet", "packet", "result", "output", "plan"):
        wrapper = pick(root, wrapper_name)
        if isinstance(wrapper, dict):
            direct = pick(wrapper, *aliases)
            if direct is not None:
                return direct
    return None


def load_model() -> Model:
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("top-level JSON must be an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return Model(None, str(exc), [], None, None, None)

    change_section = find_section(payload, "task_changes", "task_change_plan", "action_plan", "changes", "actions", "task_updates")
    changes: list[Change] = []
    for raw in as_list(change_section):
        if not isinstance(raw, dict):
            continue
        task_id = nullish(pick(raw, "task_id", "existing_task_id", "matched_task_id", "tracker_id"))
        if task_id is not None:
            task_id = str(task_id).strip().upper()
        status = norm_status(pick(raw, "status", "resulting_status", "new_status", "state"))
        owner = pick(raw, "owner_id", "owner", "assignee", "assigned_to")
        review_value = pick(raw, "review_required", "needs_review", "human_review", "needs_confirmation")
        review_text = flatten_strings(pick(raw, "review_reason", "reason", "conflict", default="")).lower()
        changes.append(Change(
            raw=raw,
            operation=norm_operation(pick(raw, "operation", "op", "action", "change_type"), status, task_id),
            task_id=task_id,
            account_id=norm_account(pick(raw, "account_id", "customer_id", "account", "account_name", "customer")),
            title=str(pick(raw, "deliverable", "title", "summary", "task", "description", default="")),
            owner_id=norm_owner(owner),
            due_date=norm_date(pick(raw, "due_date", "deadline", "due", "customer_date")),
            priority=norm_priority(pick(raw, "priority", "severity")),
            status=status,
            sources=norm_sources(pick(raw, "source_refs", "sources", "source_ids", "evidence", "traceability")),
            review_required=norm_bool(review_value) or "confirm" in review_text or "conflict" in review_text or "unavailable" in review_text,
        ))
    return Model(
        payload,
        None,
        changes,
        find_section(payload, "attention", "attention_items", "risks", "exceptions", "issues"),
        find_section(payload, "weekly_digest", "digest", "weekly_summary", "summary"),
        find_section(payload, "team_chat_draft", "chat_draft", "kickoff_message", "monday_message", "team_message"),
    )


@pytest.fixture(scope="session")
def model() -> Model:
    return load_model()


EXPECTED = {
    "TSK-010": {"operation": "update", "account": "A001", "owner": "U004", "due": "2026-04-20", "priority": "high", "status": "in_progress", "review": False, "sources": {"email:thr-001"}},
    "TSK-011": {"operation": "update", "account": "A002", "owner": "U003", "due": "2026-04-20", "priority": "high", "status": "blocked", "review": False, "sources": {"email:thr-002", "chat:ch-k002"}},
    "NEW-A003-INVOICE": {"operation": "create", "account": "A003", "owner": "U002", "due": "2026-04-22", "priority": "high", "status": "todo", "review": False, "sources": {"email:thr-003"}},
    "NEW-A004-RCA": {"operation": "create", "account": "A004", "owner": "U004", "due": "2026-04-20", "priority": "critical", "status": "in_progress", "review": False, "sources": {"email:thr-004"}},
    "NEW-A004-STATUS": {"operation": "create", "account": "A004", "owner": "U005", "due": "2026-04-20", "priority": "critical", "status": "todo", "review": False, "sources": {"chat:ch-k004"}},
    "NEW-A005-RENEWAL": {"operation": "create", "account": "A005", "owner": None, "due": "2026-04-22", "priority": "high", "status": "todo", "review": True, "sources": {"email:thr-005", "chat:ch-k003"}},
    "NEW-A006-IMPORT": {"operation": "create", "account": "A006", "owner": "U002", "due": None, "priority": "normal", "status": "todo", "review": True, "sources": {"email:thr-006"}},
    "NEW-A007-GUIDE": {"operation": "create", "account": "A007", "owner": "U005", "due": "2026-04-23", "priority": "high", "status": "todo", "review": True, "sources": {"email:thr-007"}},
    "TSK-012": {"operation": "update", "account": "A008", "owner": "U002", "due": "2026-04-24", "priority": "normal", "status": "cancelled", "review": False, "sources": {"email:thr-008"}},
    "TSK-013": {"operation": "update", "account": "A003", "owner": "U004", "due": "2026-04-17", "priority": "normal", "status": "done", "review": False, "sources": {"chat:ch-k001"}},
    "TSK-014": {"operation": "update", "account": "A009", "owner": "U002", "due": "2026-04-23", "priority": "normal", "status": "todo", "review": False, "sources": {"email:thr-009"}},
}


def identity(change: Change) -> str | None:
    if change.task_id in EXPECTED:
        return change.task_id
    source_map = {
        "email:thr-003": "NEW-A003-INVOICE",
        "email:thr-004": "NEW-A004-RCA",
        "chat:ch-k004": "NEW-A004-STATUS",
        "email:thr-005": "NEW-A005-RENEWAL",
        "email:thr-006": "NEW-A006-IMPORT",
        "email:thr-007": "NEW-A007-GUIDE",
    }
    for source, result in source_map.items():
        if source in change.sources:
            return result
    text = key_norm(change.title)
    fallbacks = [
        ("A003", ("invoice", "mapping"), "NEW-A003-INVOICE"),
        ("A004", ("rca",), "NEW-A004-RCA"),
        ("A004", ("status", "update"), "NEW-A004-STATUS"),
        ("A005", ("renewal", "brief"), "NEW-A005-RENEWAL"),
        ("A006", ("import", "sample"), "NEW-A006-IMPORT"),
        ("A007", ("troubleshoot", "guide"), "NEW-A007-GUIDE"),
    ]
    for account, words, result in fallbacks:
        if change.account_id == account and all(word in text for word in words):
            return result
    return None


def indexed(model: Model) -> dict[str, list[Change]]:
    result: dict[str, list[Change]] = {}
    for row in model.changes:
        result.setdefault(identity(row) or "UNKNOWN", []).append(row)
    return result


def require_readable(model: Model) -> None:
    if model.error:
        pytest.skip(f"artifact unreadable; root cause is scored once under artifact_usability: {model.error}")


@pytest.mark.parametrize(
    "group",
    [
        {"TSK-010", "TSK-011", "TSK-012", "TSK-013", "TSK-014"},
        {"NEW-A003-INVOICE", "NEW-A004-RCA", "NEW-A004-STATUS"},
        {"NEW-A005-RENEWAL", "NEW-A006-IMPORT", "NEW-A007-GUIDE"},
    ],
    ids=["existing-task-updates", "firm-new-commitments", "review-needed-commitments"],
)
def test_required_task_change_scope(model: Model, group: set[str]):
    require_readable(model)
    found = indexed(model)
    missing = sorted(item for item in group if item not in found)
    assert not missing, f"missing required tracker changes: {missing}"


def test_task_change_dedup_and_traceability(model: Model):
    require_readable(model)
    found = indexed(model)
    assert "UNKNOWN" not in found, "the plan contains an unsupported or untraceable extra task change"
    duplicates = {item: len(rows) for item, rows in found.items() if len(rows) != 1}
    assert not duplicates, f"cross-channel actions were not consolidated exactly once: {duplicates}"
    assert set(found) == set(EXPECTED), "the plan invents or omits task mutations"
    for item, rows in found.items():
        assert EXPECTED[item]["sources"].issubset(rows[0].sources), f"{item} lacks stable source traceability"


DECISION_GROUPS = [
    ["TSK-010", "TSK-011", "NEW-A003-INVOICE"],
    ["NEW-A004-RCA", "NEW-A004-STATUS", "NEW-A005-RENEWAL"],
    ["NEW-A006-IMPORT", "NEW-A007-GUIDE"],
    ["TSK-012", "TSK-013", "TSK-014"],
]


@pytest.mark.parametrize("keys", DECISION_GROUPS, ids=["near-term-assignment", "incident-and-handoff", "ambiguous-and-availability", "cancel-complete-reopen"])
def test_task_change_decisions(model: Model, keys: list[str]):
    require_readable(model)
    found = indexed(model)
    problems = []
    inspected = 0
    for item in keys:
        if item not in found or len(found[item]) != 1:
            # Coverage and deduplication are scored only by task_change_scope.
            # This criterion evaluates the decisions on changes that are present.
            continue
        inspected += 1
        actual = found[item][0]
        expected = EXPECTED[item]
        checks = {
            "operation": actual.operation,
            "account": actual.account_id,
            "owner": actual.owner_id,
            "due": actual.due_date,
            "priority": actual.priority,
            "status": actual.status,
            "review": actual.review_required,
        }
        for field, actual_value in checks.items():
            if actual_value != expected[field]:
                problems.append(f"{item}.{field}={actual_value!r}, expected {expected[field]!r}")
    if inspected == 0:
        pytest.skip("no changes from this decision group were present; omission is scored under task_change_scope")
    assert not problems, "material task decisions disagree with the frozen sources: " + "; ".join(problems)


def test_attention_items(model: Model):
    require_readable(model)
    text = flatten_strings(model.attention).lower()
    for task_id in ("tsk-011", "tsk-020", "tsk-021"):
        assert task_id in text, f"attention section omits active risk {task_id.upper()}"
    assert "blocked" in text, "attention section does not communicate the blocking condition"
    tsk020_window = text[max(0, text.find("tsk-020") - 100): text.find("tsk-020") + 180]
    assert "overdue" in tsk020_window and "unowned" in tsk020_window, "TSK-020 must be identifiable as overdue and unowned"


def test_calendar_and_availability_conflicts(model: Model):
    require_readable(model)
    text = flatten_strings(model.attention).lower()
    assert "cal-k001" in text and "cal-k002" in text and ("u004" in text or "priya" in text), "Priya's material Monday overlap is missing or not traceable to both events"
    assert "cal-k003" in text and ("a007" in text or "thr-007" in text or "solace" in text) and ("u005" in text or "tomas" in text), "the Solace deadline-versus-availability conflict is missing"
    assert not ("cal-k004" in text and "cal-k005" in text), "the tentative optional event was incorrectly treated as a material calendar conflict"


def extract_okr_rows(digest: Any) -> list[dict]:
    if isinstance(digest, dict):
        section = pick(digest, "okr_snapshot", "okrs", "okr_updates", "key_results")
        return [row for row in as_list(section) if isinstance(row, dict)]
    return []


def test_okr_snapshot(model: Model):
    require_readable(model)
    rows = extract_okr_rows(model.digest)
    by_id = {}
    for row in rows:
        okr_id = pick(row, "okr_id", "key_result_id", "id")
        if okr_id:
            by_id[str(okr_id).upper()] = row
    assert set(by_id) == {"KR-001", "KR-002"}, "weekly digest should include exactly the non-on-track key results"
    expected = {"KR-001": ("at_risk", 78.0, 90.0), "KR-002": ("off_track", 5.0, 3.0)}
    for okr_id, (status, current, target) in expected.items():
        row = by_id[okr_id]
        actual_status = key_norm(str(pick(row, "status", "state", "health", default="")))
        assert actual_status == key_norm(status), f"{okr_id} has the wrong status"
        assert norm_number(pick(row, "current", "actual", "value")) == current, f"{okr_id} has the wrong current value"
        assert norm_number(pick(row, "target", "goal", "threshold")) == target, f"{okr_id} has the wrong target"


def test_confidentiality_boundary(model: Model):
    require_readable(model)
    text = flatten_strings(model.raw).lower()
    forbidden = [
        "18% lower",
        "copperleaf",
        "+1-202-555-0199",
        "medical appointment",
        "procurement concerns remain private",
    ]
    leaked = [phrase for phrase in forbidden if phrase in text]
    assert not leaked, f"the packet exposes restricted customer or staff detail: {leaked}"
