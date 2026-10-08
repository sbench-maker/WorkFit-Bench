from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest


OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/security-report.json"))


EXPECTED = [
    ("SCN-001", "settings.json", ("bash(*)", "unrestricted shell", "shell wildcard"), {"critical", "blocker"}),
    ("SCN-002", "settings.json", ("dangerouslyskippermissions", "permission checks bypass", "bypass"), {"critical", "blocker"}),
    ("SCN-003", "settings.json", ("enableallprojectmcpservers", "all project mcp", "mcp servers enabled automatically"), {"high", "pre-approval"}),
    ("SCN-004", "settings.json", ("write(**)", "repository-wide write", "unrestricted write"), {"high", "pre-approval"}),
    ("SCN-005", "settings.json", ("webfetch(*)", "unrestricted outbound", "unrestricted fetch"), {"high", "pre-approval"}),
    ("SCN-006", "claude.md", ("automatically execute", "automatic execution", "bootstrap"), {"high", "pre-approval"}),
    ("SCN-007", "claude.md", ("operator-message", "trusted system instruction", "promoted to instruction"), {"high", "pre-approval"}),
    ("SCN-008", "mcp.json", ("npx", "-y", "auto-install"), {"medium", "hardening"}),
    ("SCN-009", "mcp.json", ("launches through a shell", '"command": "sh"', "shell-running mcp", "shell execution"), {"critical", "blocker"}),
    ("SCN-010", "mcp.json", ("no description", "missing description"), {"info", "low", "medium", "documentation"}),
    ("SCN-011", "hooks/summarize_changes.sh", ("eval", "command injection", "shell re-parsing"), {"critical", "blocker"}),
    ("SCN-012", "hooks/publish_transcript.sh", ("transcript", "exfil", "transmits"), {"high", "pre-approval"}),
    ("SCN-013", "hooks/publish_transcript.sh", ("2>/dev/null", "|| true", "suppresses", "silent"), {"medium", "hardening"}),
    ("SCN-014", "agents/release-helper.md", ("bash(*)", "unrestricted shell", "shell wildcard"), {"critical", "blocker"}),
    ("SCN-015", "agents/release-helper.md", ("no model", "missing model", "model specification"), {"medium", "info", "low", "hardening"}),
    ("SCN-016", "agents/release-helper.md", ("ticket", "untrusted", "requested command"), {"high", "pre-approval"}),
    ("SCN-017", "agents/incident-triage.md", ("bash", "shell access", "unnecessary"), {"high", "pre-approval"}),
    ("SCN-018", "agents/incident-triage.md", ("no model", "missing model", "model specification"), {"medium", "info", "low", "hardening"}),
    ("SCN-019", "agents/db-migrator.md", ("bash", "shell access", "migration command"), {"high", "pre-approval"}),
    ("SCN-020", "agents/db-migrator.md", ("authoritative instructions", "customer reports", "untrusted directives"), {"high", "pre-approval"}),
]

SAFE_ONLY_FILES = {
    "agents/api-reviewer.md",
    "agents/dependency-notes.md",
    "agents/docs-researcher.md",
    "agents/localizer.md",
    "agents/test-reviewer.md",
    "hooks/check_filename.py",
    "hooks/policy_guard.py",
}


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def flatten_scalars(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, (str, int, float, bool)) or child is None:
                out.append(f"{key}: {child}")
            elif isinstance(child, list) and all(not isinstance(item, (dict, list)) for item in child):
                out.append(f"{key}: {' '.join(map(str, child))}")
    elif isinstance(value, list):
        out.extend(str(item) for item in value if not isinstance(item, (dict, list)))
    elif value is not None:
        out.append(str(value))
    return out


def looks_like_path(text: str) -> bool:
    lowered = norm(text)
    return any(suffix in lowered for suffix in (".md", ".json", ".sh", ".py"))


def collect_records(value: Any, inherited_path: str = "", inherited_severity: str = "") -> list[dict]:
    records: list[dict] = []
    if isinstance(value, dict):
        local_path = inherited_path
        local_severity = inherited_severity
        for key, child in value.items():
            key_n = norm(key)
            if key_n in {"file", "path", "source", "location", "filename"} and isinstance(child, str):
                local_path = child
            if key_n in {"severity", "risk_level", "risklevel", "level"} and isinstance(child, (str, int)):
                local_severity = str(child)

        semantic_value = {
            key: child for key, child in value.items()
            if norm(key) not in {
                "file", "path", "source", "location", "filename",
                "severity", "risk_level", "risklevel", "level",
            }
        }
        scalar_text = " ".join(flatten_scalars(semantic_value))
        key_text = norm(" ".join(map(str, value.keys())))
        has_finding_shape = bool(local_path) and (
            bool(local_severity)
            or any(token in key_text for token in ("severity", "risk", "remediation", "recommendation", "fix"))
        )
        if has_finding_shape:
            records.append({
                "path": norm(local_path),
                "severity": norm(local_severity),
                "text": norm(scalar_text),
            })

        for key, child in value.items():
            child_path = local_path
            child_severity = local_severity
            if looks_like_path(str(key)):
                child_path = str(key)
            severity_groups = {
                "critical": "critical", "launch_blockers": "critical", "blockers": "critical",
                "high": "high", "high_risk": "high", "pre_approval": "high",
                "medium": "medium", "moderate": "medium", "medium_risk": "medium", "hardening": "medium",
                "low": "low", "info": "info", "informational": "info", "documentation": "info",
            }
            if norm(key) in severity_groups:
                child_severity = severity_groups[norm(key)]
            records.extend(collect_records(child, child_path, child_severity))
    elif isinstance(value, list):
        for child in value:
            records.extend(collect_records(child, inherited_path, inherited_severity))
    return records


def collect_section_text(value: Any, active: bool = False) -> list[str]:
    texts: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_n = norm(key)
            next_active = active or any(token in key_n for token in ("safe", "positive", "passed", "existing control", "strength"))
            texts.extend(collect_section_text(child, next_active))
    elif isinstance(value, list):
        for child in value:
            texts.extend(collect_section_text(child, active))
    elif active and value is not None:
        texts.append(norm(value))
    return texts


def load_report() -> tuple[Any | None, str | None]:
    if not OUTPUT.is_file():
        return None, f"missing requested artifact: {OUTPUT}"
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"requested artifact is not readable JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "security assessment must be a JSON object"
    return payload, None


def matching_record(records: list[dict], path: str, signatures: tuple[str, ...]) -> dict | None:
    path_n = norm(path)
    candidates = [record for record in records if record["path"].endswith(path_n)]
    for record in candidates:
        if any(norm(signature) in record["text"] for signature in signatures):
            return record
    return None


def canonical_severity(value: str) -> str:
    value = norm(value)
    aliases = {
        "p0": "critical",
        "urgent": "critical",
        "p1": "high",
        "moderate": "medium",
        "p2": "medium",
        "informational": "info",
        "advisory": "info",
    }
    for token, canonical in aliases.items():
        if re.search(rf"(^|[^a-z0-9]){re.escape(token)}([^a-z0-9]|$)", value):
            return canonical
    for token in ("critical", "blocker", "high", "pre-approval", "medium", "hardening", "info", "low", "documentation"):
        if token in value:
            return token
    return value


@pytest.mark.parametrize("issue_id,path,signatures,accepted_severities", EXPECTED, ids=[row[0] for row in EXPECTED])
def test_material_findings_and_severity(issue_id, path, signatures, accepted_severities):
    payload, error = load_report()
    assert error is None, error
    record = matching_record(collect_records(payload), path, signatures)
    assert record is not None, (
        f"{issue_id} is missing: expected a finding tied to {path} with evidence for {signatures}"
    )
    actual = canonical_severity(record["severity"])
    assert actual in accepted_severities, (
        f"{issue_id} has severity {record['severity']!r}; expected one of {sorted(accepted_severities)}"
    )


def test_existing_safe_controls_recognized():
    payload, error = load_report()
    assert error is None, error
    safe_text = " ".join(collect_section_text(payload))
    checks = {
        "settings deny protections": ("deny", "destructive", "sensitive-file"),
        "PreToolUse guard": ("pretool", "policy hook", "policy_guard"),
        "local-docs MCP": ("local-docs", "read-only documentation", "environment references"),
        "restricted agents": ("no shell access", "explicit model", "read-only"),
    }
    recognized = sum(any(token in safe_text for token in tokens) for tokens in checks.values())
    assert recognized >= 3, (
        f"only {recognized} of 4 safe-control families are positively identified; the report may drive removal of useful protections"
    )


def test_safe_only_files_not_reported_as_vulnerabilities():
    payload, error = load_report()
    assert error is None, error
    finding_paths = {record["path"] for record in collect_records(payload)}
    false_positives = sorted(
        safe for safe in SAFE_ONLY_FILES
        if any(path.endswith(safe) for path in finding_paths)
    )
    assert not false_positives, (
        f"benign restricted definitions were reported as vulnerabilities: {false_positives}"
    )
