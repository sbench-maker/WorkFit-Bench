#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_system import AgentOrchestrator
from runtime import MockRoleModel, MockToolRegistry, load_incidents


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline incident-response agent")
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).with_name("fixtures"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    incidents = load_incidents(args.fixtures)
    if args.limit is not None:
        incidents = incidents[: max(0, args.limit)]
    orchestrator = AgentOrchestrator(MockRoleModel(args.fixtures), MockToolRegistry(args.fixtures), args.memory)
    report = orchestrator.run_all(incidents)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

