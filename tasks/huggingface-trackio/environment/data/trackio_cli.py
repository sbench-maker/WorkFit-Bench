#!/usr/bin/env python3
"""Offline CLI for querying the bundled Trackio-compatible store."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def store() -> dict:
    path = Path(os.environ.get("TRACKIO_DB_PATH", "/root/results/trackio_store.json"))
    if not path.exists():
        raise SystemExit(f"Error: tracking store not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def project_row(payload: dict, project: str) -> dict:
    try:
        return payload["projects"][project]
    except KeyError:
        raise SystemExit(f"Error: Project '{project}' not found.")


def run_row(payload: dict, project: str, run: str) -> dict:
    project_data = project_row(payload, project)
    try:
        return project_data["runs"][run]
    except KeyError:
        raise SystemExit(f"Error: Run '{run}' not found in project '{project}'.")


def metric_values(run: dict, metric: str) -> list[dict]:
    values = []
    for entry in run.get("logs", []):
        if metric in entry.get("metrics", {}):
            values.append(
                {
                    "step": entry.get("step"),
                    "timestamp": entry.get("timestamp"),
                    "value": entry["metrics"][metric],
                }
            )
    return values


def emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2, allow_nan=False))


def main() -> int:
    parser = argparse.ArgumentParser(prog="trackio")
    sub = parser.add_subparsers(dest="verb", required=True)

    list_parser = sub.add_parser("list")
    list_sub = list_parser.add_subparsers(dest="kind", required=True)
    list_sub.add_parser("projects").add_argument("--json", action="store_true")
    for kind in ("runs", "metrics", "alerts"):
        item = list_sub.add_parser(kind)
        item.add_argument("--project", required=True)
        item.add_argument("--run")
        item.add_argument("--level")
        item.add_argument("--since")
        item.add_argument("--json", action="store_true")

    get_parser = sub.add_parser("get")
    get_sub = get_parser.add_subparsers(dest="kind", required=True)
    project_cmd = get_sub.add_parser("project")
    project_cmd.add_argument("--project", required=True)
    project_cmd.add_argument("--json", action="store_true")
    run_cmd = get_sub.add_parser("run")
    run_cmd.add_argument("--project", required=True)
    run_cmd.add_argument("--run", required=True)
    run_cmd.add_argument("--json", action="store_true")
    metric_cmd = get_sub.add_parser("metric")
    metric_cmd.add_argument("--project", required=True)
    metric_cmd.add_argument("--run", required=True)
    metric_cmd.add_argument("--metric", required=True)
    metric_cmd.add_argument("--step", type=int)
    metric_cmd.add_argument("--around", type=int)
    metric_cmd.add_argument("--window", type=int, default=10)
    metric_cmd.add_argument("--json", action="store_true")
    snap_cmd = get_sub.add_parser("snapshot")
    snap_cmd.add_argument("--project", required=True)
    snap_cmd.add_argument("--run", required=True)
    snap_cmd.add_argument("--step", type=int)
    snap_cmd.add_argument("--around", type=int)
    snap_cmd.add_argument("--window", type=int, default=10)
    snap_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args()
    payload = store()
    if args.verb == "list" and args.kind == "projects":
        emit({"projects": sorted(payload.get("projects", {}))})
        return 0
    if args.verb == "list" and args.kind == "runs":
        row = project_row(payload, args.project)
        emit({"project": args.project, "runs": sorted(row.get("runs", {}))})
        return 0
    if args.verb == "list" and args.kind == "metrics":
        row = run_row(payload, args.project, args.run)
        metrics = sorted({key for log in row.get("logs", []) for key in log.get("metrics", {})})
        emit({"project": args.project, "run": args.run, "metrics": metrics})
        return 0
    if args.verb == "list" and args.kind == "alerts":
        project = project_row(payload, args.project)
        rows = []
        for run_name, run in project.get("runs", {}).items():
            if args.run and run_name != args.run:
                continue
            for alert in run.get("alerts", []):
                if args.level and alert.get("level") != args.level.lower():
                    continue
                if args.since and (alert.get("timestamp") or "") <= args.since:
                    continue
                rows.append(alert)
        rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run") or ""))
        emit({"project": args.project, "run": args.run, "level": args.level, "since": args.since, "alerts": rows})
        return 0
    if args.verb == "get" and args.kind == "project":
        row = project_row(payload, args.project)
        runs = sorted(row.get("runs", {}))
        emit({"project": args.project, "num_runs": len(runs), "runs": runs})
        return 0
    if args.verb == "get" and args.kind == "run":
        row = run_row(payload, args.project, args.run)
        metrics = sorted({key for log in row.get("logs", []) for key in log.get("metrics", {})})
        emit({"project": args.project, "run": args.run, "num_logs": len(row.get("logs", [])), "metrics": metrics, "config": row.get("config", {}), "last_step": max((log.get("step", -1) for log in row.get("logs", [])), default=-1), "finished": row.get("finished", False)})
        return 0
    if args.verb == "get" and args.kind == "metric":
        row = run_row(payload, args.project, args.run)
        values = metric_values(row, args.metric)
        if not values:
            raise SystemExit(f"Error: Metric '{args.metric}' not found in run '{args.run}' of project '{args.project}'.")
        if args.step is not None:
            values = [item for item in values if item["step"] == args.step]
        elif args.around is not None:
            values = [item for item in values if abs(item["step"] - args.around) <= args.window]
        emit({"project": args.project, "run": args.run, "metric": args.metric, "values": values})
        return 0
    if args.verb == "get" and args.kind == "snapshot":
        row = run_row(payload, args.project, args.run)
        if args.step is not None:
            logs = [item for item in row.get("logs", []) if item.get("step") == args.step]
        elif args.around is not None:
            logs = [item for item in row.get("logs", []) if abs(item.get("step", -10**9) - args.around) <= args.window]
        else:
            logs = row.get("logs", [])
        emit({"project": args.project, "run": args.run, "logs": logs})
        return 0
    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
