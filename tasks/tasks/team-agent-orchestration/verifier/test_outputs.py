from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DATA = Path(os.environ.get("ORCHESTRATION_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("ORCHESTRATION_OUTPUT_PATH", "/root/results/output.json"))
_MISSING = object()


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _lookup(mapping: Any, aliases: tuple[str, ...] | list[str], default: Any = _MISSING) -> Any:
    if not isinstance(mapping, dict):
        if default is not _MISSING:
            return default
        raise KeyError(f"expected an object while looking for {aliases}")
    normalized = {_key(key): value for key, value in mapping.items()}
    for alias in aliases:
        if _key(alias) in normalized:
            return normalized[_key(alias)]
    if default is not _MISSING:
        return default
    raise KeyError(f"none of {aliases} found")


def _find_list(node: Any, aliases: tuple[str, ...]) -> list | None:
    if isinstance(node, dict):
        normalized_aliases = {_key(alias) for alias in aliases}
        for key, value in node.items():
            if _key(key) in normalized_aliases and isinstance(value, list):
                return value
        for value in node.values():
            found = _find_list(value, aliases)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_list(value, aliases)
            if found is not None:
                return found
    return None


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _split(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        for alias in ("include", "included", "files", "paths", "scope"):
            nested = _lookup(value, [alias], default=None)
            if nested is not None:
                return _split(nested)
        return []
    return [part.strip() for part in re.split(r"[;,\n]", str(value)) if part.strip()]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _load_submission() -> dict:
    assert OUTPUT.is_file(), f"missing requested release plan: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"release plan is not readable JSON: {exc}") from exc
    assert isinstance(payload, dict), "release plan must be a JSON object"
    return payload


def _card_id(row: Any) -> str | None:
    value = _lookup(row, ["card_id", "work_item_id", "item_id", "id"], default=None)
    return None if value is None else str(value).strip().upper()


def _cards(payload: dict) -> tuple[list[dict], dict[str, dict]]:
    direct = _lookup(payload, ["release_board", "board", "cards", "work_items", "workitems", "kanban_cards"], default=None)
    rows = direct if isinstance(direct, list) else _find_list(
        payload, ("release_board", "board", "cards", "work_items", "workitems", "kanban_cards")
    )
    assert rows is not None, "release plan has no active-card collection"
    assert all(isinstance(row, dict) for row in rows), "active-card collection contains a non-object entry"
    identifiers = [_card_id(row) for row in rows]
    usable = [identifier for identifier in identifiers if identifier]
    mapping = {identifier: row for identifier, row in zip(identifiers, rows) if identifier}
    assert len(mapping) == len(usable), "active-card collection contains duplicate card identifiers"
    return rows, mapping


def _normalize_state(value: Any) -> str:
    token = _key(value)
    aliases = {
        "backlog": "backlog",
        "unshaped": "backlog",
        "ready": "ready",
        "running": "running",
        "inprogress": "running",
        "active": "running",
        "review": "review",
        "underreview": "review",
        "inreview": "review",
        "blocked": "blocked",
        "merged": "merged",
        "integrated": "merged",
        "done": "merged",
        "archived": "archived",
    }
    return aliases.get(token, token)


def _normalize_readiness(value: Any) -> str:
    token = _key(value)
    aliases = {
        "merged": "merged",
        "integrated": "merged",
        "readynow": "ready_now",
        "ready": "ready_now",
        "mergeable": "ready_now",
        "pendingdependency": "pending_dependency",
        "waitingdependency": "pending_dependency",
        "waitingondependency": "pending_dependency",
        "afterdependency": "pending_dependency",
        "blocked": "blocked",
        "notready": "not_ready",
        "pendinggates": "not_ready",
        "running": "not_ready",
        "backlog": "not_ready",
    }
    return aliases.get(token, token)


def _normalize_status(value: Any) -> str:
    token = _key(value)
    aliases = {
        "pass": "pass",
        "passed": "pass",
        "success": "pass",
        "green": "pass",
        "fail": "fail",
        "failed": "fail",
        "red": "fail",
        "pending": "pending",
        "missing": "pending",
        "notrun": "pending",
        "todo": "pending",
    }
    return aliases.get(token, token)


def _gate_map(card: dict) -> dict[str, dict]:
    raw = _lookup(card, ["gates", "merge_gates", "gate_results", "checks"], default=None)
    found: dict[str, dict] = {}
    if isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, dict):
                status = _lookup(value, ["status", "result", "outcome"], default=None)
                evidence = _lookup(value, ["evidence_id", "evidence", "artifact", "path", "link"], default=None)
            else:
                status, evidence = value, None
            found[_key(name)] = {"status": _normalize_status(status), "evidence": evidence}
    elif isinstance(raw, list):
        for value in raw:
            if not isinstance(value, dict):
                continue
            name = _lookup(value, ["gate", "kind", "name", "check"], default=None)
            if name is None:
                continue
            found[_key(name)] = {
                "status": _normalize_status(_lookup(value, ["status", "result", "outcome"], default=None)),
                "evidence": _lookup(value, ["evidence_id", "evidence", "artifact", "path", "link"], default=None),
            }
    return found


def _source_expectations() -> dict:
    context = json.loads((DATA / "project_context.json").read_text(encoding="utf-8"))
    as_of = _parse_time(context["as_of"])
    items = _read_csv("work_items.csv")
    acceptance = _read_csv("acceptance_checks.csv")
    evidence = [row for row in _read_csv("evidence.csv") if _parse_time(row["observed_at"]) <= as_of]
    changes = _read_csv("file_changes.csv")
    blockers = [row for row in _read_csv("blockers.csv") if row["status"].lower() == "open"]
    acceptance_by_card: dict[str, list[dict]] = defaultdict(list)
    evidence_by_card: dict[str, list[dict]] = defaultdict(list)
    changes_by_card: dict[str, list[dict]] = defaultdict(list)
    blockers_by_card: dict[str, list[dict]] = defaultdict(list)
    for row in acceptance:
        acceptance_by_card[row["card_id"]].append(row)
    for row in evidence:
        evidence_by_card[row["card_id"]].append(row)
    for row in changes:
        changes_by_card[row["card_id"]].append(row)
    for row in blockers:
        blockers_by_card[row["card_id"]].append(row)

    def owner(item: dict) -> str:
        return item["current_owner"] or context["ownership"]["component_primary"][item["component"]]

    def latest(card_id: str, kind: str) -> dict | None:
        rows = [row for row in evidence_by_card[card_id] if row["kind"] == kind]
        return max(rows, key=lambda row: _parse_time(row["observed_at"])) if rows else None

    expected_gates: dict[str, dict[str, dict]] = {}
    merge_evidence: dict[str, dict | None] = {}
    states: dict[str, str] = {}
    by_id = {row["card_id"]: row for row in items}
    for card_id, item in by_id.items():
        gates = {}
        for kind in _split(item["required_gates"]):
            row = latest(card_id, kind)
            gates[_key(kind)] = {
                "status": "pending" if row is None else row["status"],
                "evidence_id": None if row is None else row["evidence_id"],
                "artifact": None if row is None else row["artifact_path"],
            }
        expected_gates[card_id] = gates
        merge_evidence[card_id] = latest(card_id, "merge")
        if item["archived_reason"]:
            state = "archived"
        elif (latest(card_id, "merge") or {}).get("status") == "pass":
            state = "merged"
        elif any(row["state_blocking"].lower() == "true" for row in blockers_by_card[card_id]) or any(row["status"] == "fail" for row in gates.values()):
            state = "blocked"
        else:
            checks = acceptance_by_card[card_id]
            all_acceptance = bool(checks) and all(row["status"] == "pass" for row in checks)
            all_gates = bool(gates) and all(row["status"] == "pass" for row in gates.values())
            handoff = latest(card_id, "handoff")
            has_handoff = bool(handoff and handoff["status"] == "pass" and handoff["artifact_path"])
            has_changes = bool(changes_by_card[card_id])
            if all_acceptance and all_gates and has_changes and has_handoff:
                state = "review"
            elif has_changes or any(row["kind"] == "heartbeat" and row["status"] == "running" for row in evidence_by_card[card_id]):
                state = "running"
            elif checks and owner(item) and item["scope_files"]:
                state = "ready"
            else:
                state = "backlog"
        states[card_id] = state

    active = {card_id for card_id, state in states.items() if state != "archived"}
    merged = {card_id for card_id in active if states[card_id] == "merged"}
    review = {card_id for card_id in active if states[card_id] == "review"}
    remaining = set(review)
    merge_plan: list[str] = []
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    while remaining:
        available = [
            card_id for card_id in remaining
            if all(dep in merged or dep in merge_plan for dep in _split(by_id[card_id]["depends_on"]))
        ]
        if not available:
            break
        chosen = min(available, key=lambda card_id: (priority_order[by_id[card_id]["priority"]], card_id))
        merge_plan.append(chosen)
        remaining.remove(chosen)

    readiness = {}
    for card_id in active:
        deps = _split(by_id[card_id]["depends_on"])
        if states[card_id] == "merged":
            readiness[card_id] = "merged"
        elif states[card_id] == "review" and all(dep in merged for dep in deps):
            readiness[card_id] = "ready_now"
        elif states[card_id] == "review":
            readiness[card_id] = "pending_dependency"
        elif states[card_id] == "blocked":
            readiness[card_id] = "blocked"
        else:
            readiness[card_id] = "not_ready"

    boundaries = {}
    for card_id in active:
        item = by_id[card_id]
        boundaries[card_id] = {
            "owner": owner(item),
            "branch": item["branch"] or f"agent/{card_id}-{_slug(item['title'])}",
            "worktree": item["worktree"] if item["worktree"] not in {"", "."} else f"/worktrees/{card_id}",
            "scope": set(_split(item["scope_files"])),
            "forbidden": set(_split(item["forbidden_files"])),
        }
    return {
        "active": active,
        "states": states,
        "gates": expected_gates,
        "merge_evidence": merge_evidence,
        "readiness": readiness,
        "merge_plan": merge_plan,
        "boundaries": boundaries,
        "blockers": {row["blocker_id"]: row for row in blockers},
        "merged": merged,
    }


EXPECTED = _source_expectations()


def test_active_card_coverage_ownership_and_boundaries() -> None:
    _, cards = _cards(_load_submission())
    actual_ids = set(cards)
    missing = sorted(EXPECTED["active"] - actual_ids)
    unexpected = sorted(actual_ids - EXPECTED["active"])
    issues = []
    if missing:
        issues.append(f"missing active cards {missing}")
    if unexpected:
        issues.append(f"included archived or unknown cards {unexpected}")
    worktrees: dict[str, str] = {}
    branches: dict[str, str] = {}
    for card_id in sorted(EXPECTED["active"] & actual_ids):
        card = cards[card_id]
        expected = EXPECTED["boundaries"][card_id]
        owner = str(_lookup(card, ["owner", "accountable_owner", "assignee"], default="")).strip().lower()
        branch = str(_lookup(card, ["branch", "branch_name"], default="")).strip()
        worktree = str(_lookup(card, ["worktree", "workspace", "worktree_path"], default="")).strip()
        scope = set(_split(_lookup(card, ["scope_files", "file_scope", "scope", "allowed_files"], default=[])))
        forbidden = set(_split(_lookup(card, ["forbidden_files", "forbidden", "excluded_files", "do_not_touch"], default=[])))
        if owner != expected["owner"]:
            issues.append(f"{card_id} owner={owner!r}, expected {expected['owner']!r}")
        if branch != expected["branch"]:
            issues.append(f"{card_id} branch={branch!r}, expected collision-safe {expected['branch']!r}")
        if worktree != expected["worktree"]:
            issues.append(f"{card_id} worktree={worktree!r}, expected isolated {expected['worktree']!r}")
        if scope != expected["scope"]:
            issues.append(f"{card_id} file scope does not match its declared contract")
        if forbidden != expected["forbidden"]:
            issues.append(f"{card_id} forbidden-file boundary is missing or changed")
        if worktree in worktrees and worktree:
            issues.append(f"{card_id} shares worktree {worktree!r} with {worktrees[worktree]}")
        worktrees[worktree] = card_id
        if branch in branches and branch:
            issues.append(f"{card_id} shares branch {branch!r} with {branches[branch]}")
        branches[branch] = card_id
    assert not issues, "; ".join(issues[:20])


def test_states_and_gate_evidence_reconcile() -> None:
    _, cards = _cards(_load_submission())
    issues = []
    for card_id in sorted(EXPECTED["active"] & set(cards)):
        card = cards[card_id]
        actual_state = _normalize_state(_lookup(card, ["state", "kanban_state", "status"], default=""))
        expected_state = EXPECTED["states"][card_id]
        if actual_state != expected_state:
            issues.append(f"{card_id} state={actual_state!r}, expected {expected_state!r}")
        if expected_state == "merged":
            source = EXPECTED["merge_evidence"][card_id]
            card_text = json.dumps(card, sort_keys=True)
            references = {source["evidence_id"], source["artifact_path"]} if source else set()
            references.discard("")
            if not any(reference in card_text for reference in references):
                issues.append(f"{card_id} merged state lacks its frozen merge evidence reference")
        actual_gates = _gate_map(card)
        for gate, expected in EXPECTED["gates"][card_id].items():
            if gate not in actual_gates:
                issues.append(f"{card_id} omits required gate {gate}")
                continue
            actual = actual_gates[gate]
            if actual["status"] != expected["status"]:
                issues.append(f"{card_id}/{gate} status={actual['status']!r}, expected {expected['status']!r}")
            if expected["status"] != "pending":
                evidence_text = str(actual["evidence"] or "")
                allowed = {expected["evidence_id"], expected["artifact"]}
                allowed.discard(None)
                allowed.discard("")
                if not any(str(value) in evidence_text for value in allowed):
                    issues.append(f"{card_id}/{gate} lacks its frozen evidence reference")
    assert not issues, "; ".join(issues[:25])


def _blocker_rows(payload: dict) -> dict[str, dict]:
    rows = _find_list(payload, ("blockers", "issues", "holds", "impediments")) or []
    mapping = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = _lookup(row, ["blocker_id", "issue_id", "id"], default=None)
        if identifier is not None:
            mapping[str(identifier).strip().upper()] = row
    return mapping


def test_open_blockers_have_accountable_actions() -> None:
    actual = _blocker_rows(_load_submission())
    expected = EXPECTED["blockers"]
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    issues = []
    if missing:
        issues.append(f"missing open blockers {missing}")
    if extra:
        issues.append(f"unknown or closed blockers included {extra}")
    term_groups = {
        "B01": (("debug", "secret"), ("risk", "review"), ("rerun", "run")),
        "B02": (("multilingual", "ranking"), ("eval", "evaluator"), ("rerun", "run")),
        "B03": (("c02", "ingestion"), ("rebase", "regenerate"), ("isolated", "worktree")),
        "B04": (("a0603", "rollback"), ("coverage", "test")),
        "B05": (("handoff",), ("evidence", "test"), ("publish", "write", "attach")),
    }
    for blocker_id in sorted(set(expected) & set(actual)):
        source = expected[blocker_id]
        row = actual[blocker_id]
        card_id = str(_lookup(row, ["card_id", "work_item_id", "item_id"], default="")).strip().upper()
        owner = str(_lookup(row, ["owner", "blocker_owner", "accountable_owner"], default="")).strip().lower()
        action = str(_lookup(row, ["next_action", "action", "unblock_action", "resolution"], default="")).lower()
        if card_id != source["card_id"]:
            issues.append(f"{blocker_id} is attached to {card_id!r}, expected {source['card_id']}")
        if owner != source["owner"]:
            issues.append(f"{blocker_id} owner={owner!r}, expected {source['owner']!r}")
        if not action.strip():
            issues.append(f"{blocker_id} has no next action")
        elif any(not any(term in action for term in group) for group in term_groups[blocker_id]):
            issues.append(f"{blocker_id} next action does not address its recorded cause: {action!r}")
    assert not issues, "; ".join(issues[:20])


def _merge_ids(payload: dict) -> list[str]:
    rows = _find_list(payload, ("merge_plan", "integration_sequence", "merge_sequence", "integration_plan")) or []
    enriched = []
    for index, row in enumerate(rows):
        if isinstance(row, str):
            enriched.append((index, row.strip().upper()))
            continue
        if not isinstance(row, dict):
            continue
        identifier = _card_id(row)
        sequence = _lookup(row, ["sequence", "rank", "order", "position"], default=index + 1)
        try:
            sort_key = float(sequence)
        except (TypeError, ValueError):
            sort_key = index + 1
        if identifier:
            enriched.append((sort_key, identifier))
    return [identifier for _, identifier in sorted(enriched, key=lambda pair: pair[0])]


def test_merge_readiness_and_integration_sequence() -> None:
    payload = _load_submission()
    _, cards = _cards(payload)
    issues = []
    for card_id in sorted(EXPECTED["active"] & set(cards)):
        actual = _normalize_readiness(_lookup(cards[card_id], ["merge_readiness", "readiness", "merge_status"], default=""))
        expected = EXPECTED["readiness"][card_id]
        if actual != expected:
            issues.append(f"{card_id} merge readiness={actual!r}, expected {expected!r}")
    actual_plan = _merge_ids(payload)
    if actual_plan != EXPECTED["merge_plan"]:
        issues.append(f"integration sequence {actual_plan} does not match dependency-safe priority order {EXPECTED['merge_plan']}")
    if len(actual_plan) != len(set(actual_plan)):
        issues.append("integration sequence contains duplicate cards")
    assert not issues, "; ".join(issues[:20])
