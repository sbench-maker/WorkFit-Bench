#!/usr/bin/env python3
"""Offline, deterministic stand-in for the mission-oriented fleet service.

The command names and returned objects mirror the service workflow while all state
is stored in a caller-selected local JSON file. No network access is performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


DEFAULT_STATE = Path("/root/results/fleet_state.json")
DATA_DIR = Path(__file__).resolve().parent
TERMINAL = {"completed", "failed", "cancelled"}


MISSION_SPECS = [
    {
        "mission_id": "M-101",
        "title": "Map compatibility and release contract",
        "mission_type": "planning",
        "depends_on": [],
        "auto_dispatch": True,
        "duration_ticks": 2,
        "prompt": "Confirm the 30-day compatibility contract, affected owners, and release gates using release_request.md, repository_inventory.json, and test_history.jsonl.",
    },
    {
        "mission_id": "M-102",
        "title": "Implement scoped token core",
        "mission_type": "implementation",
        "depends_on": ["M-101"],
        "auto_dispatch": True,
        "duration_ticks": 4,
        "prompt": "Implement signed per-tenant service tokens, scope enforcement, revocation, rotation, and redaction in services/token/issuer.py, services/token/revocation.py, and services/token/scopes.py.",
    },
    {
        "mission_id": "M-103",
        "title": "Add service-token API rollout",
        "mission_type": "implementation",
        "depends_on": ["M-101"],
        "auto_dispatch": True,
        "duration_ticks": 3,
        "prompt": "Add issue, revoke, and last-used API behavior plus the 30-day mixed-version compatibility path in api/v2/service_tokens.py and api/v2/schemas/service_token.py.",
    },
    {
        "mission_id": "M-104",
        "title": "Build reversible token-vault migration",
        "mission_type": "implementation",
        "depends_on": ["M-101"],
        "auto_dispatch": True,
        "duration_ticks": 5,
        "prompt": "Implement and validate zero-downtime forward and rollback migrations in db/migrations/0142_token_vault.sql and db/rollback/0142_token_vault_down.sql.",
    },
    {
        "mission_id": "M-105",
        "title": "Add observability and operator runbook",
        "mission_type": "implementation",
        "depends_on": ["M-101"],
        "auto_dispatch": True,
        "duration_ticks": 2,
        "prompt": "Add redaction-safe metrics, the token health dashboard, and the rotation runbook without ever recording token bodies.",
    },
    {
        "mission_id": "M-106",
        "title": "Run mixed-version integration suite",
        "mission_type": "testing",
        "depends_on": ["M-102", "M-103", "M-104"],
        "auto_dispatch": True,
        "duration_ticks": 3,
        "prompt": "Exercise lifecycle, mixed-version compatibility, rollout, and rollback in tests/integration/test_service_token_lifecycle.py and tests/integration/test_mixed_version_auth.py.",
    },
    {
        "mission_id": "M-107",
        "title": "Review rotation, revocation, and redaction",
        "mission_type": "review",
        "depends_on": ["M-102", "M-105"],
        "auto_dispatch": True,
        "duration_ticks": 2,
        "prompt": "Review key rotation, revocation races, scope boundaries, and token redaction using the security tests and observability changes.",
    },
    {
        "mission_id": "M-108",
        "title": "Evaluate final release gate",
        "mission_type": "release",
        "depends_on": ["M-106", "M-107"],
        "auto_dispatch": True,
        "duration_ticks": 1,
        "prompt": "Evaluate the release gate from integration and security reports, record readiness, and identify any manual follow-up.",
    },
]


REPORT_CONTENT = {
    "M-101": {
        "files_changed": [],
        "what_done": "Mapped the compatibility window, seven owned change areas, and the rollback, mixed-version, and security gates.",
        "tests": [{"name": "planning-contract-check", "passed": True}],
        "errors": [],
        "next_steps": ["Proceed with core, API, migration, and observability missions."],
    },
    "M-102": {
        "files_changed": ["services/token/issuer.py", "services/token/revocation.py", "services/token/scopes.py", "tests/security/test_revocation_race.py"],
        "what_done": "Implemented tenant-bound signing, explicit scopes, rotation overlap, revocation checks, and redacted audit fields.",
        "tests": [
            {"name": "unit-token", "passed": True},
            {"name": "security-revocation", "passed": True},
        ],
        "errors": [],
        "next_steps": ["Feed the core implementation into integration and security review missions."],
    },
    "M-103": {
        "files_changed": ["api/v2/service_tokens.py", "api/v2/schemas/service_token.py", "tests/integration/test_mixed_version_auth.py"],
        "what_done": "Added issue, revoke, and last-used behavior with a time-bounded legacy-token compatibility branch.",
        "tests": [
            {"name": "unit-api", "passed": True},
            {"name": "api-contract", "passed": True},
        ],
        "errors": [],
        "next_steps": ["Validate the API together with the token core and database migration."],
    },
    "M-104": {
        "files_changed": ["db/migrations/0142_token_vault.sql", "db/rollback/0142_token_vault_down.sql"],
        "what_done": "Implemented the forward migration, but rollback validation failed before the branch could merge.",
        "tests": [
            {"name": "migration-forward", "passed": True},
            {"name": "migration-rollback", "passed": False},
        ],
        "errors": [
            {
                "code": "ROLLBACK_CHECKSUM_MISMATCH",
                "message": "Rollback checksum for tenant_token_scope differs after the down/up cycle.",
                "file": "db/rollback/0142_token_vault_down.sql",
            }
        ],
        "next_steps": ["Correct the down migration checksum and rerun both migration directions before integration."],
    },
    "M-105": {
        "files_changed": ["ops/metrics/service_tokens.yml", "ops/dashboards/token_health.json", "docs/runbooks/service-token-rotation.md", "tests/security/test_token_redaction.py"],
        "what_done": "Added safe metrics, rotation and revocation panels, an operator runbook, and a redaction regression test.",
        "tests": [
            {"name": "metrics-schema", "passed": True},
            {"name": "security-redaction", "passed": True},
        ],
        "errors": [],
        "next_steps": ["Use the new evidence in the security review."],
    },
    "M-106": {
        "files_changed": [],
        "what_done": "Not started because the required migration mission did not complete successfully.",
        "tests": [],
        "errors": [],
        "next_steps": ["Rerun after M-104 completes successfully."],
    },
    "M-107": {
        "files_changed": [],
        "what_done": "Reviewed rotation overlap, tenant scope separation, revocation races, and token-body redaction; no material security defect remained.",
        "tests": [
            {"name": "security-redaction", "passed": True},
            {"name": "security-revocation", "passed": True},
        ],
        "errors": [],
        "next_steps": ["Carry the passing security evidence into the final release gate."],
    },
    "M-108": {
        "files_changed": [],
        "what_done": "Not started because the integration mission was cancelled after its migration dependency failed.",
        "tests": [],
        "errors": [],
        "next_steps": ["Re-evaluate only after M-104 and M-106 complete successfully."],
    },
}


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"state does not exist: {path}; call plan_project first")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _event(state: dict, action: str, mission_id: str | None = None, **extra: object) -> None:
    row = {"tick": state["tick"], "action": action}
    if mission_id is not None:
        row["mission_id"] = mission_id
    row.update(extra)
    state["events"].append(row)


def plan_project(prompt_file: Path, state_path: Path) -> dict:
    prompt = prompt_file.read_text(encoding="utf-8")
    if "Polaris service-token rollout" not in prompt or "30-day compatibility" not in prompt:
        raise RuntimeError("the supplied prompt is not the approved Polaris release request")
    dashboard = json.loads((DATA_DIR / "initial_dashboard.json").read_text(encoding="utf-8"))
    missions = {}
    for spec in MISSION_SPECS:
        row = dict(spec)
        row.update({"status": "draft", "started_tick": None, "ended_tick": None})
        missions[row["mission_id"]] = row
    state = {
        "schema_version": "devfleet-mock-1.0",
        "tick": 0,
        "max_agents": dashboard["max_agents"],
        "project": {
            "project_id": "PRJ-POLARIS-042",
            "name": "Polaris service-token rollout",
            "description": "Approved offline rehearsal for the scoped service-token release.",
        },
        "missions": missions,
        "events": [],
    }
    _event(state, "planned", mission_count=len(missions))
    _save(state_path, state)
    return {"project_id": state["project"]["project_id"], "missions": list(missions.values())}


def _running(state: dict) -> list[dict]:
    return [row for row in state["missions"].values() if row["status"] == "running"]


def _launch(state: dict, row: dict, mode: str) -> None:
    row["status"] = "running"
    row["started_tick"] = state["tick"]
    _event(state, f"{mode}_dispatch", row["mission_id"], running_agents=len(_running(state)))


def dispatch_mission(mission_id: str, state_path: Path) -> dict:
    state = _load(state_path)
    row = state["missions"].get(mission_id)
    if row is None:
        raise RuntimeError(f"unknown mission: {mission_id}")
    if row["depends_on"]:
        raise RuntimeError("only a root mission can be dispatched manually")
    if row["status"] != "draft":
        raise RuntimeError(f"mission is not dispatchable from {row['status']}")
    if len(_running(state)) >= state["max_agents"]:
        raise RuntimeError("no agent slot is available")
    _launch(state, row, "manual")
    _save(state_path, state)
    return {"mission_id": mission_id, "status": row["status"], "started_tick": row["started_tick"]}


def _cancel_failed_descendants(state: dict) -> bool:
    changed = False
    for row in state["missions"].values():
        if row["status"] not in {"draft", "queued"} or not row["depends_on"]:
            continue
        dependencies = [state["missions"][dep]["status"] for dep in row["depends_on"]]
        if all(status in TERMINAL for status in dependencies) and any(status != "completed" for status in dependencies):
            row["status"] = "cancelled"
            row["ended_tick"] = state["tick"]
            _event(state, "cancelled", row["mission_id"], reason="dependency_not_completed")
            changed = True
    return changed


def _schedule_ready(state: dict) -> None:
    ready = []
    for row in state["missions"].values():
        if row["status"] not in {"draft", "queued"} or not row["depends_on"]:
            continue
        if all(state["missions"][dep]["status"] == "completed" for dep in row["depends_on"]):
            ready.append(row)
    ready.sort(key=lambda row: row["mission_id"])
    slots = state["max_agents"] - len(_running(state))
    for row in ready:
        if slots > 0:
            _launch(state, row, "auto")
            slots -= 1
        elif row["status"] != "queued":
            row["status"] = "queued"
            _event(state, "queued", row["mission_id"], reason="capacity")


def _advance(state: dict) -> None:
    state["tick"] += 1
    completed_now = []
    for row in list(_running(state)):
        if state["tick"] - row["started_tick"] < row["duration_ticks"]:
            continue
        row["status"] = "failed" if row["mission_id"] == "M-104" else "completed"
        row["ended_tick"] = state["tick"]
        completed_now.append(row)
    for row in completed_now:
        _event(state, row["status"], row["mission_id"])
    while _cancel_failed_descendants(state):
        pass
    _schedule_ready(state)


def get_mission_status(mission_id: str, state_path: Path) -> dict:
    state = _load(state_path)
    if mission_id not in state["missions"]:
        raise RuntimeError(f"unknown mission: {mission_id}")
    _advance(state)
    _save(state_path, state)
    row = state["missions"][mission_id]
    return {
        "mission_id": mission_id,
        "status": row["status"],
        "started_tick": row["started_tick"],
        "ended_tick": row["ended_tick"],
        "tick": state["tick"],
    }


def get_dashboard(state_path: Path) -> dict:
    state = _load(state_path)
    counts = {}
    for row in state["missions"].values():
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "project_id": state["project"]["project_id"],
        "tick": state["tick"],
        "max_agents": state["max_agents"],
        "running_agents": len(_running(state)),
        "status_counts": counts,
        "recent_activity": state["events"][-8:],
    }


def list_missions(state_path: Path, status: str | None = None) -> list[dict]:
    state = _load(state_path)
    rows = list(state["missions"].values())
    if status is not None:
        rows = [row for row in rows if row["status"] == status]
    return rows


def get_report(mission_id: str, state_path: Path) -> dict:
    state = _load(state_path)
    row = state["missions"].get(mission_id)
    if row is None:
        raise RuntimeError(f"unknown mission: {mission_id}")
    if row["status"] not in TERMINAL:
        raise RuntimeError(f"report is unavailable while mission is {row['status']}")
    report = {
        "mission_id": mission_id,
        "title": row["title"],
        "status": row["status"],
        "worktree_branch": f"devfleet/{mission_id.lower()}",
        **REPORT_CONTENT[mission_id],
    }
    if row["status"] == "cancelled":
        report["worktree_branch"] = None
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan_project")
    plan.add_argument("--prompt-file", type=Path, required=True)
    dispatch = sub.add_parser("dispatch_mission")
    dispatch.add_argument("mission_id")
    status = sub.add_parser("get_mission_status")
    status.add_argument("mission_id")
    sub.add_parser("get_dashboard")
    report = sub.add_parser("get_report")
    report.add_argument("mission_id")
    missions = sub.add_parser("list_missions")
    missions.add_argument("--status")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "plan_project":
            result = plan_project(args.prompt_file, args.state)
        elif args.command == "dispatch_mission":
            result = dispatch_mission(args.mission_id, args.state)
        elif args.command == "get_mission_status":
            result = get_mission_status(args.mission_id, args.state)
        elif args.command == "get_dashboard":
            result = get_dashboard(args.state)
        elif args.command == "get_report":
            result = get_report(args.mission_id, args.state)
        elif args.command == "list_missions":
            result = list_missions(args.state, args.status)
        else:
            raise RuntimeError("unsupported command")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
