"""Deterministic role-model and tool-registry mocks for the offline task."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


class ToolError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class MockRoleModel:
    """Returns frozen role messages while preserving the shape of model calls."""

    def __init__(self, fixtures: Path) -> None:
        rows = _read_jsonl(fixtures / "model_scripts.jsonl")
        self._scripts = {row["incident_id"]: row for row in rows}

    def generate(self, role: str, incident_id: str, turn: int, state: dict) -> str:
        if role not in {"planner", "investigator", "remediator"}:
            raise ValueError(f"unknown role: {role}")
        messages = self._scripts[incident_id].get(role, [])
        if not messages:
            return json.dumps({"type": "escalate", "reason": f"{role} has no safe next step"})
        # Replaying the last message exposes orchestrators that do not detect loops.
        return messages[min(turn, len(messages) - 1)]


class MockToolRegistry:
    """Schema-aware local tools with policy enforcement and deterministic faults."""

    ACTION_BY_CAUSE = {
        "bad_deploy": "rollback_deployment",
        "memory_pressure": "restart_service",
        "stale_cache": "clear_cache",
        "queue_saturation": "scale_workers",
    }

    def __init__(self, fixtures: Path) -> None:
        registry = _read_json(fixtures / "tool_registry.json")
        self.policy = registry["policy"]
        self.tools = {tool["name"]: tool for tool in registry["tools"]}
        incidents = _read_json(fixtures / "incidents.json")
        self.incidents = {row["incident_id"]: row for row in incidents}
        self.telemetry = defaultdict(list)
        for row in _read_jsonl(fixtures / "telemetry.jsonl"):
            self.telemetry[row["incident_id"]].append(row)
        self.changes = defaultdict(list)
        for row in _read_jsonl(fixtures / "changes.jsonl"):
            self.changes[row["incident_id"]].append(row)
        self.attempts: dict[tuple[str, str, str], int] = defaultdict(int)
        self.paged: set[str] = set()

    def invoke(self, name: str, arguments: dict) -> dict:
        if name not in self.tools:
            raise ToolError(f"tool is not registered: {name}", retryable=False)
        if not isinstance(arguments, dict):
            raise ToolError("tool arguments must be an object", retryable=False)
        missing = [item for item in self.tools[name]["required_arguments"] if not arguments.get(item)]
        if missing:
            raise ToolError(f"missing required arguments: {', '.join(missing)}", retryable=False)
        incident_id = arguments.get("incident_id")
        incident = self.incidents.get(incident_id)
        if incident is None:
            raise ToolError(f"unknown incident: {incident_id}", retryable=False)

        key = (incident_id, name, json.dumps(arguments, sort_keys=True))
        self.attempts[key] += 1
        attempt = self.attempts[key]
        kind = incident["case_kind"]

        if kind == "transient_tool_error" and name == "get_metrics" and attempt == 1:
            raise ToolError("telemetry shard temporarily unavailable", retryable=True)
        if kind == "persistent_tool_error" and name == "get_logs":
            raise ToolError("log index remains unavailable", retryable=True)

        if name == "get_metrics":
            return {"ok": True, "records": self.telemetry[incident_id]}
        if name == "get_logs":
            return {
                "ok": True,
                "digest": f"Signals are consistent with {incident['root_cause'].replace('_', ' ')}",
                "service": incident["service"],
            }
        if name == "get_recent_changes":
            return {"ok": True, "records": self.changes[incident_id]}
        if name == "page_oncall":
            self.paged.add(incident_id)
            return {"ok": True, "acknowledged": True, "team": "fictional-oncall"}

        if arguments.get("service") != incident["service"]:
            raise ToolError("mutation target does not match the incident service", retryable=False)
        if incident["severity"] == "P1" and incident["environment"] == "production" and incident_id not in self.paged:
            raise ToolError("production P1 mutation requires on-call acknowledgement", retryable=False)
        expected = self.ACTION_BY_CAUSE[incident["root_cause"]]
        if name != expected:
            raise ToolError(f"unsafe remediation for diagnosed cause: {name}", retryable=False)
        if incident["case_kind"] == "remediation_failure":
            return {"ok": False, "resolved": False, "error": "post-action health check failed"}
        return {"ok": True, "resolved": True, "action": name, "service": incident["service"]}


def load_incidents(fixtures: Path) -> list[dict]:
    return _read_json(fixtures / "incidents.json")

