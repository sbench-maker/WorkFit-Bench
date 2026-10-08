from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import pytest


TASK_ROOT = Path(os.environ.get("TASK_ROOT", "/root")).resolve()
OUT = TASK_ROOT / "results" / "review.json"
REPO = TASK_ROOT / "data" / "inference-gateway"


@dataclass(frozen=True)
class Finding:
    reviewer: str
    issue: str | None
    severity: str
    file: str
    line: int | None
    text: str


@dataclass(frozen=True)
class Submission:
    raw: dict[str, Any] | None
    reviewers: dict[str, tuple[Finding, ...]]
    error: str | None


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _pick(mapping: Any, *names: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    normalized = {_key(name): value for name, value in mapping.items()}
    for name in names:
        if _key(name) in normalized:
            return normalized[_key(name)]
    return None


def _reviewer_name(value: Any) -> str | None:
    normalized = _key(value)
    if "codex" in normalized or "openai" in normalized:
        return "codex"
    if "gemini" in normalized or "google" in normalized:
        return "gemini"
    return None


def _review_sections(raw: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    container = _pick(raw, "reviewers", "reviews", "model_reviews", "review_results")
    if isinstance(container, dict):
        for name, value in container.items():
            reviewer = _reviewer_name(name) or _reviewer_name(_pick(value, "reviewer", "tool", "model", "name"))
            if reviewer:
                result[reviewer] = value
    elif isinstance(container, list):
        for value in container:
            reviewer = _reviewer_name(_pick(value, "reviewer", "tool", "model", "name"))
            if reviewer:
                result[reviewer] = value
    for name, value in raw.items():
        reviewer = _reviewer_name(name)
        if reviewer and reviewer not in result and isinstance(value, (dict, list)):
            result[reviewer] = value
    return result


def _all_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_all_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_all_text(item) for item in value)
    return str(value or "")


def _location(finding: dict[str, Any]) -> tuple[str, int | None]:
    location = _pick(finding, "location", "code_location", "codeLocation")
    file_value = _pick(finding, "file", "file_path", "path", "filename")
    line_value = _pick(finding, "line", "start_line", "line_number")
    top_level_range = _pick(finding, "line_range", "lines", "range")
    if isinstance(top_level_range, dict):
        line_value = line_value or _pick(top_level_range, "start", "line", "start_line")
    elif line_value is None and top_level_range is not None:
        line_value = top_level_range
    if isinstance(location, dict):
        file_value = file_value or _pick(location, "file", "file_path", "path", "filename")
        line_value = line_value or _pick(location, "line", "start", "start_line", "line_number")
        line_range = _pick(location, "line_range", "range")
        if isinstance(line_range, dict):
            line_value = line_value or _pick(line_range, "start", "line", "start_line")
    file_name = str(file_value or "").replace("\\", "/")
    marker = "inference-gateway/"
    if marker in file_name:
        file_name = file_name.split(marker, 1)[1]
    file_name = file_name.lstrip("./")
    match = re.search(r"\d+", str(line_value or ""))
    return file_name, int(match.group()) if match else None


def _severity(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {0: "info", 1: "low", 2: "medium", 3: "high"}.get(int(value), str(value))
    normalized = _key(value)
    aliases = {"p0": "critical", "p1": "high", "p2": "medium", "p3": "low", "blocker": "critical"}
    return aliases.get(normalized, normalized)


def _classify_issue(value: Any, file_name: str = "") -> str | None:
    text = _all_text(value).lower()
    explicit = re.search(r"\b([QARB])[-_ ]?0*0?1\b", text, flags=re.I)
    if explicit:
        return explicit.group(1).upper() + "001"
    source = (file_name + " " + text).lower()
    if "quota" in source and "tenant" in source and "cache" in source:
        return "Q001"
    if "auth.py" in source and ("metadata" in source or "x_internal" in source) and ("scope" in source or "bypass" in source):
        return "A001"
    if "router.py" in source and ("exception" in source or "error" in source) and ("fallback" in source or "retry" in source):
        return "R001"
    if "batch" in source and "token" in source and ("budget" in source or "oversiz" in source or "reject" in source):
        return "B001"
    return None


def _findings(reviewer: str, section: Any) -> tuple[Finding, ...]:
    values = section if isinstance(section, list) else _pick(section, "findings", "issues", "comments", "problems")
    if not isinstance(values, list):
        return ()
    result = []
    for item in values:
        if not isinstance(item, dict):
            continue
        file_name, line = _location(item)
        severity = _severity(_pick(item, "severity", "priority", "risk", "level"))
        result.append(Finding(reviewer, _classify_issue(item, file_name), severity, file_name, line, _all_text(item)))
    return tuple(result)


@lru_cache(maxsize=1)
def load_submission() -> Submission:
    if not OUT.is_file():
        return Submission(None, {}, f"requested artifact is missing: {OUT}")
    try:
        raw = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Submission(None, {}, f"review.json is not readable JSON: {exc}")
    if not isinstance(raw, dict):
        return Submission(None, {}, "review.json must contain a JSON object")
    sections = _review_sections(raw)
    reviewers = {name: _findings(name, section) for name, section in sections.items()}
    return Submission(raw, reviewers, None)


def _require_semantics() -> Submission:
    submission = load_submission()
    if submission.error:
        pytest.skip(f"semantic checks skipped because the artifact root is unusable: {submission.error}")
    return submission


def _finding(submission: Submission, reviewer: str, issue: str) -> Finding | None:
    return next((finding for finding in submission.reviewers.get(reviewer, ()) if finding.issue == issue), None)


def test_artifact_and_reviewer_coverage():
    submission = load_submission()
    assert submission.error is None, submission.error
    assert set(submission.reviewers) >= {"codex", "gemini"}, "both Codex and Gemini reviews must be separately attributable"
    assert submission.reviewers["codex"], "Codex review contains no findings"
    assert submission.reviewers["gemini"], "Gemini review contains no findings"


@pytest.mark.parametrize(
    "reviewer,issue,accepted_severities",
    [
        ("codex", "Q001", {"high", "critical"}),
        ("codex", "B001", {"medium", "high", "critical"}),
        ("codex", "R001", {"high", "critical"}),
        ("gemini", "Q001", {"high", "critical"}),
        ("gemini", "A001", {"high", "critical"}),
        ("gemini", "R001", {"high", "critical"}),
    ],
)
def test_material_reviewer_findings(reviewer: str, issue: str, accepted_severities: set[str]):
    submission = _require_semantics()
    finding = _finding(submission, reviewer, issue)
    assert finding is not None, f"{reviewer} findings omit {issue}"
    assert finding.severity in accepted_severities, f"{reviewer} under-prioritizes {issue} as {finding.severity!r}"


def _changed_lines() -> dict[str, set[int]]:
    completed = subprocess.run(
        ["git", "diff", "--unified=0", "main...HEAD"],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    changed: dict[str, set[int]] = {}
    current = ""
    for line in completed.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            changed.setdefault(current, set())
        elif line.startswith("@@") and current:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                changed[current].update(range(start, start + count))
    return changed


def test_patch_scope_and_citations():
    submission = _require_semantics()
    changed = _changed_lines()
    all_findings = [finding for values in submission.reviewers.values() for finding in values]
    assert all(finding.file in changed for finding in all_findings), "a finding cites a file outside the main...HEAD patch"
    expected_locations = {
        ("codex", "Q001"): ("src/gateway/quota.py", {7}),
        ("codex", "B001"): ("src/gateway/batching.py", {9, 10}),
        ("codex", "R001"): ("src/gateway/router.py", {7, 8}),
        ("gemini", "Q001"): ("src/gateway/quota.py", {7}),
        ("gemini", "A001"): ("src/gateway/auth.py", {5, 6}),
        ("gemini", "R001"): ("src/gateway/router.py", {7, 8}),
    }
    problems = []
    for key, (file_name, lines) in expected_locations.items():
        finding = _finding(submission, *key)
        if finding is not None and (finding.file != file_name or finding.line not in lines):
            problems.append(f"{key[0]} {key[1]} cites {finding.file}:{finding.line}, expected {file_name}:{sorted(lines)}")
    assert not problems, "; ".join(problems)


def _issue_set(value: Any) -> set[str]:
    if isinstance(value, list):
        result = set()
        for item in value:
            issue = _classify_issue(item)
            if issue:
                result.add(issue)
        return result
    issue = _classify_issue(value)
    return {issue} if issue else set()


def _comparison_sets(raw: dict[str, Any]) -> tuple[set[str], set[str], set[str]]:
    comparison = _pick(raw, "comparison", "synthesis", "cross_review", "review_comparison")
    agreements: set[str] = set()
    codex_only: set[str] = set()
    gemini_only: set[str] = set()
    if isinstance(comparison, dict):
        agreements = _issue_set(_pick(comparison, "agreements", "agreement", "shared", "consensus", "both"))
        differences = _pick(comparison, "differences", "difference", "unique", "disagreements")
        for source in (comparison, differences if isinstance(differences, dict) else {}):
            codex_only |= _issue_set(_pick(source, "codex_only", "codex_unique", "only_codex"))
            gemini_only |= _issue_set(_pick(source, "gemini_only", "gemini_unique", "only_gemini"))
        if isinstance(differences, list):
            for item in differences:
                text = _all_text(item).lower()
                issue = _classify_issue(item)
                if issue and "codex" in text and ("only" in text or "unique" in text):
                    codex_only.add(issue)
                if issue and "gemini" in text and ("only" in text or "unique" in text):
                    gemini_only.add(issue)
    else:
        for sentence in re.split(r"[.\n;]+", _all_text(comparison)):
            lowered = sentence.lower()
            issue = _classify_issue(sentence)
            if not issue:
                continue
            if "codex" in lowered and ("only" in lowered or "alone" in lowered or "unique" in lowered):
                codex_only.add(issue)
            elif "gemini" in lowered and ("only" in lowered or "alone" in lowered or "unique" in lowered):
                gemini_only.add(issue)
            elif "both" in lowered or "agree" in lowered or "shared" in lowered:
                agreements.add(issue)
    return agreements, codex_only, gemini_only


def test_comparison_consistency():
    submission = _require_semantics()
    agreements, codex_only, gemini_only = _comparison_sets(submission.raw or {})
    assert agreements == {"Q001", "R001"}, f"shared findings should be Q001 and R001, got {sorted(agreements)}"
    assert codex_only == {"B001"}, f"Codex-only findings should be B001, got {sorted(codex_only)}"
    assert gemini_only == {"A001"}, f"Gemini-only findings should be A001, got {sorted(gemini_only)}"


def test_merge_gate():
    submission = _require_semantics()
    recommendation = _pick(submission.raw or {}, "merge_recommendation", "merge_decision", "recommendation", "verdict", "merge")
    normalized = _key(recommendation)
    blocked = any(term in normalized for term in ("block", "donotmerge", "changesrequested", "reject", "unsafe"))
    assert blocked, f"merge recommendation must clearly block this branch, got {recommendation!r}"
