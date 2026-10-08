#!/usr/bin/env python3
"""Fail fast when a generated task image is missing declared runtime support."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import pwd
import shutil
import sys
from pathlib import Path


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("environment manifest must be a JSON object")
    return payload


def validate_environment(manifest: dict, *, phase: str) -> list[str]:
    issues: list[str] = []
    user = manifest.get("agent_user")
    if not isinstance(user, str) or not user:
        issues.append("agent_user is missing")
    else:
        try:
            pwd.getpwnam(user)
        except KeyError:
            issues.append(f"agent user does not exist: {user}")

    for command in manifest.get("required_commands", []):
        if not isinstance(command, str) or not command:
            issues.append("required_commands contains an invalid entry")
        elif shutil.which(command) is None:
            issues.append(f"required command is unavailable: {command}")

    for package in manifest.get("required_python_packages", []):
        if not isinstance(package, dict):
            issues.append("required_python_packages contains an invalid entry")
            continue
        distribution = package.get("distribution")
        import_name = package.get("import_name")
        expected_version = package.get("version")
        if not all(isinstance(value, str) and value for value in (distribution, import_name, expected_version)):
            issues.append("Python package entries require distribution, import_name, and version")
            continue
        try:
            actual_version = importlib.metadata.version(distribution)
            importlib.import_module(import_name)
        except (importlib.metadata.PackageNotFoundError, ImportError):
            issues.append(f"required Python package is unavailable: {distribution}")
            continue
        if actual_version != expected_version:
            issues.append(
                f"Python package version mismatch: {distribution} expected {expected_version}, got {actual_version}"
            )

    if phase == "runtime":
        original_euid = os.geteuid()
        if isinstance(user, str) and user:
            try:
                expected_uid = pwd.getpwnam(user).pw_uid
            except KeyError:
                expected_uid = None
            if expected_uid is not None and original_euid != expected_uid:
                issues.append(f"runtime check must run as {user}")
        for raw_path in manifest.get("agent_readable_paths", []):
            path = Path(raw_path) if isinstance(raw_path, str) else None
            if path is None or not path.exists() or not os.access(path, os.R_OK):
                issues.append(f"agent-readable path is unavailable: {raw_path}")
        for raw_path in manifest.get("agent_writable_paths", []):
            path = Path(raw_path) if isinstance(raw_path, str) else None
            if path is None:
                issues.append("agent_writable_paths contains an invalid entry")
                continue
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".environment-write-probe"
                probe.write_text("ok\n", encoding="utf-8")
                probe.unlink()
            except OSError:
                issues.append(f"agent-writable path is not writable: {raw_path}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("/opt/task/environment_manifest.json"))
    parser.add_argument("--phase", choices=("build", "runtime"), default="build")
    args = parser.parse_args()
    try:
        issues = validate_environment(load_manifest(args.manifest), phase=args.phase)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"environment check failed: {exc}", file=sys.stderr)
        return 1
    for issue in issues:
        print(f"environment check failed: {issue}", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
