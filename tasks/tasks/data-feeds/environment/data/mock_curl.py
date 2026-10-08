#!/usr/bin/env python3
"""A tiny curl-compatible emulator for the frozen Bright Data endpoints."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse


CATALOG = Path(os.environ.get("MOCK_FEED_CATALOG", "/root/data/api_catalog.json"))
STATE = Path(os.environ.get("MOCK_FEED_STATE", "/root/results/.feed_mock_state.json"))


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def load_state() -> dict[str, int]:
    if not STATE.is_file():
        return {}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, int]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")


def find_arg(args: list[str], names: tuple[str, ...]) -> str | None:
    for i, arg in enumerate(args):
        if arg in names and i + 1 < len(args):
            return args[i + 1]
    return None


def main() -> int:
    args = sys.argv[1:]
    if "--version" in args:
        print("curl offline-feed-emulator/1.0")
        return 0
    url = next((arg for arg in reversed(args) if arg.startswith("http://") or arg.startswith("https://")), None)
    if not url:
        emit({"error": "mock curl expected a URL"})
        return 2
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["entries"]
    method = (find_arg(args, ("-X", "--request")) or "GET").upper()
    parsed = urlparse(url)
    if method == "POST" and parsed.path.endswith("/trigger"):
        dataset_id = parse_qs(parsed.query).get("dataset_id", [""])[0]
        raw_body = find_arg(args, ("-d", "--data", "--data-raw"))
        try:
            body = json.loads(raw_body or "[]")
            input_payload = body[0]
        except (json.JSONDecodeError, IndexError, TypeError):
            emit({"error": "invalid trigger body"})
            return 0
        entry = next((row for row in catalog if row["dataset_id"] == dataset_id and row["input"] == input_payload), None)
        if entry is None:
            emit({"error": "request is not present in the frozen catalog"})
        elif entry["terminal"] == "trigger_error":
            emit({"error": entry["error"]})
        else:
            emit({"snapshot_id": entry["snapshot_id"]})
        return 0
    marker = "/datasets/v3/snapshot/"
    if method == "GET" and marker in parsed.path:
        snapshot_id = parsed.path.split(marker, 1)[1].split("/", 1)[0]
        entry = next((row for row in catalog if row["snapshot_id"] == snapshot_id), None)
        if entry is None:
            emit({"status": "failed", "error": "unknown snapshot"})
            return 0
        state = load_state()
        index = int(state.get(snapshot_id, 0))
        states = entry["states"]
        if index < len(states):
            emit({"status": states[index], "snapshot_id": snapshot_id})
            state[snapshot_id] = index + 1
            save_state(state)
            return 0
        if entry["terminal"] == "timeout":
            emit({"status": "running", "snapshot_id": snapshot_id})
        elif entry["terminal"] == "failed":
            emit({"status": "failed", "snapshot_id": snapshot_id, "error": entry["error"]})
        else:
            emit(entry["records"])
        state[snapshot_id] = index + 1
        save_state(state)
        return 0
    emit({"error": "endpoint is not implemented by the offline emulator"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
