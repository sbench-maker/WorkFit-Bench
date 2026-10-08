#!/usr/bin/env python3
"""Deterministic local stand-in for storage and Agent Platform tuning APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path


SNAPSHOT = Path(__file__).with_name("mock_cloud_snapshot.json")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_state(path):
    target = Path(path)
    if not target.is_file():
        raise SystemExit("state is not initialized; run init first")
    return read_json(target)


def require_bucket(state, uri):
    matches = [bucket for bucket in state["accessible_buckets"] if uri == bucket or uri.startswith(bucket + "/")]
    if not matches:
        raise SystemExit(f"mock storage object is outside an accessible bucket: {uri}")


def cmd_init(args):
    snapshot = read_json(SNAPSHOT)
    write_json(args.state, {
        "schema_version": "1.0",
        "project": snapshot["project"],
        "location": snapshot["location"],
        "clock": snapshot["clock"],
        "accessible_buckets": snapshot["accessible_buckets"],
        "model_contract": snapshot["model_contract"],
        "objects": {},
        "jobs": {},
    })


def cmd_storage_ls(args):
    state = load_state(args.state)
    require_bucket(state, args.uri)
    print(args.uri)


def cmd_storage_cp(args):
    state = load_state(args.state)
    source = Path(args.source)
    if not source.is_file():
        raise SystemExit(f"source does not exist: {source}")
    require_bucket(state, args.uri)
    state["objects"][args.uri] = {
        "sha256": sha256(source),
        "bytes": source.stat().st_size,
        "source_name": source.name,
    }
    write_json(args.state, state)


def cmd_submit(args):
    state = load_state(args.state)
    request = read_json(args.request)
    required = {
        "project", "location", "base_model", "train_dataset", "validation_dataset",
        "output_uri", "epochs", "learning_rate", "tuning_mode", "adapter_size",
    }
    missing = sorted(required - set(request))
    if missing:
        raise SystemExit(f"request is missing fields: {', '.join(missing)}")
    if request["project"] != state["project"] or request["location"] != state["location"]:
        raise SystemExit("request project/location does not match the initialized mock context")
    contract = state["model_contract"]
    if request["base_model"] != contract["base_model"]:
        raise SystemExit("unsupported base_model for this frozen mock")
    if request["tuning_mode"] != contract["tuning_mode"]:
        raise SystemExit("this model must use PEFT_ADAPTER in this handoff")
    if request["epochs"] != contract["epochs"] or abs(float(request["learning_rate"]) - contract["learning_rate"]) > 1e-12:
        raise SystemExit("hyperparameters are outside the approved configuration")
    if request["adapter_size"] != contract["adapter_size"]:
        raise SystemExit("adapter_size is outside the approved configuration")
    for key in ("train_dataset", "validation_dataset"):
        if request[key] not in state["objects"]:
            raise SystemExit(f"dataset was not uploaded before submission: {request[key]}")
    require_bucket(state, request["output_uri"])
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    request_sha = hashlib.sha256(canonical).hexdigest()
    job_id = "tune-" + request_sha[:12]
    job_name = f"projects/{state['project']}/locations/{state['location']}/tuningJobs/{job_id}"
    state["jobs"][job_id] = {
        "name": job_name,
        "state": "JOB_STATE_QUEUED",
        "request_sha256": request_sha,
        "submitted_at": state["clock"],
    }
    write_json(args.state, state)
    write_json(args.receipt, {
        "job_id": job_id,
        "job_name": job_name,
        "state": "JOB_STATE_QUEUED",
        "request_sha256": request_sha,
        "submitted_at": state["clock"],
    })


def cmd_monitor(args):
    state = load_state(args.state)
    job_id = args.job_id.split("/")[-1]
    if job_id not in state["jobs"]:
        raise SystemExit(f"unknown job: {args.job_id}")
    start = datetime.fromisoformat(state["clock"].replace("Z", "+00:00"))
    states = ["JOB_STATE_QUEUED", "JOB_STATE_RUNNING", "JOB_STATE_SUCCEEDED"]
    rows = [
        {"job_id": job_id, "state": value, "observed_at": (start + timedelta(minutes=i * 4)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}
        for i, value in enumerate(states)
    ]
    target = Path(args.events)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    state["jobs"][job_id]["state"] = "JOB_STATE_SUCCEEDED"
    state["jobs"][job_id]["completed_at"] = rows[-1]["observed_at"]
    write_json(args.state, state)


def main():
    parser = argparse.ArgumentParser(description="Offline mock for the tuning control plane")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--state", required=True)
    init.set_defaults(func=cmd_init)
    ls = sub.add_parser("storage-ls")
    ls.add_argument("--state", required=True)
    ls.add_argument("--uri", required=True)
    ls.set_defaults(func=cmd_storage_ls)
    cp = sub.add_parser("storage-cp")
    cp.add_argument("--state", required=True)
    cp.add_argument("--source", required=True)
    cp.add_argument("--uri", required=True)
    cp.set_defaults(func=cmd_storage_cp)
    submit = sub.add_parser("submit")
    submit.add_argument("--state", required=True)
    submit.add_argument("--request", required=True)
    submit.add_argument("--receipt", required=True)
    submit.set_defaults(func=cmd_submit)
    monitor = sub.add_parser("monitor")
    monitor.add_argument("--state", required=True)
    monitor.add_argument("--job-id", required=True)
    monitor.add_argument("--events", required=True)
    monitor.set_defaults(func=cmd_monitor)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
