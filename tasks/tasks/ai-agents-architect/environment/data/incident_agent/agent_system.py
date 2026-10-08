"""Implement the bounded multi-role orchestrator in this module."""

from __future__ import annotations

from pathlib import Path

from runtime import MockRoleModel, MockToolRegistry


class AgentOrchestrator:
    def __init__(self, model: MockRoleModel, tools: MockToolRegistry, memory_path: Path) -> None:
        self.model = model
        self.tools = tools
        self.memory_path = memory_path

    def run_all(self, incidents: list[dict]) -> dict:
        raise NotImplementedError("complete the agent orchestration")

