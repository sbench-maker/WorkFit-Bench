from __future__ import annotations

import csv
import os
import re
from pathlib import Path

import pytest


RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results/launch_pack"))
DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _markdown_files() -> list[Path]:
    return sorted(path for path in RESULTS.rglob("*.md") if path.is_file()) if RESULTS.is_dir() else []


def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path else ""


def _find_doc(kind: str) -> Path | None:
    files = _markdown_files()
    name_tokens = {
        "brief": ("project_brief", "project-brief", "brief"),
        "brainstorm": ("brainstorm", "consilium"),
        "plan": ("plan", "sprint_plan", "sprint-plan"),
        "progress": ("progress", "tracker", "status"),
        "done": ("done", "handoff", "closeout"),
    }[kind]
    for path in files:
        lower = path.relative_to(RESULTS).as_posix().casefold()
        if any(token in lower for token in name_tokens):
            return path
    signatures = {
        "brief": ("evalharbor", "tech stack", "security"),
        "brainstorm": ("brainstorm", "kira", "debate"),
        "plan": ("sprint 1", "prioritized", "success criteria"),
        "progress": ("sprint 1", "status", "resume"),
        "done": ("sprint 1", "what was built", "known issues"),
    }[kind]
    for path in files:
        normalized = _norm(_read(path))
        if all(_norm(token) in normalized for token in signatures):
            return path
    return None


def _work_items() -> list[dict[str, str]]:
    with (DATA / "work_items.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _scheduled_text(plan_text: str) -> str:
    lines = plan_text.splitlines()
    cut = len(lines)
    exclusion_heading = re.compile(r"^#{1,6}\s+.*(not\s+in|out\s+of|excluded|deferred|later\s+work)", re.I)
    for index, line in enumerate(lines):
        if exclusion_heading.search(line.strip()):
            cut = index
            break
    return "\n".join(lines[:cut])


def _line_for_id(text: str, item_id: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(rf"(?<![A-Z0-9]){re.escape(item_id)}(?![A-Z0-9])", line, re.I):
            start = max(0, index - 2)
            end = min(len(lines), index + 3)
            return " ".join(lines[start:end])
    return ""


def _exact_line_for_id(text: str, item_id: str) -> str:
    for line in text.splitlines():
        if re.search(rf"(?<![A-Z0-9]){re.escape(item_id)}(?![A-Z0-9])", line, re.I):
            return line
    return ""


def _primary_item_line(text: str, row: dict[str, str]) -> str:
    matches = [
        line for line in text.splitlines()
        if re.search(rf"(?<![A-Z0-9]){re.escape(row['item_id'])}(?![A-Z0-9])", line, re.I)
    ]
    for line in matches:
        if _norm(row["title"]) in _norm(line):
            return line
    for line in matches:
        if _norm(row["suggested_owner"]) in _norm(line):
            return line
    return matches[0] if matches else ""


def test_artifact_usability() -> None:
    """The five requested artifact types exist as readable, substantive Markdown."""
    assert RESULTS.is_dir(), f"missing requested launch pack directory: {RESULTS}"
    found = {kind: _find_doc(kind) for kind in ("brief", "brainstorm", "plan", "progress", "done")}
    missing = [kind for kind, path in found.items() if path is None]
    assert not missing, f"launch pack is missing recognizable requested docs: {missing}"
    too_small = [f"{kind}:{path}" for kind, path in found.items() if path and len(_read(path).strip()) < 180]
    assert not too_small, f"requested docs are too skeletal to use: {too_small}"


@pytest.mark.parametrize(
    "fact_group",
    [
        ("product", ["EvalHarbor", "internal", "release owner", "reviewer", "deterministic mock"]),
        ("frontend", ["React 18", "TypeScript", "Vite", "apps/web"]),
        ("backend", ["Python 3.12", "FastAPI", "services/api"]),
        ("storage", ["PostgreSQL 16", "Redis 7"]),
        ("identity and tests", ["OIDC", "local mock", "Pytest", "Playwright"]),
        ("run contract", ["queued", "running", "succeeded", "failed", "cancelled"]),
        ("score summary", ["pass count", "fail count", "pass rate", "p50 latency"]),
        ("local commands", ["docker compose up --build", "npm run dev --workspace apps/web", "pytest services/api/tests", "npm run test:e2e"]),
    ],
)
def test_project_fidelity(fact_group: tuple[str, list[str]]) -> None:
    """Accepted product and architecture facts are carried into the durable brief."""
    label, facts = fact_group
    brief = _norm(_read(_find_doc("brief")))
    missing = [fact for fact in facts if _norm(fact) not in brief]
    assert not missing, f"project brief loses fixed {label} facts: {missing}"


def test_security_controls_are_preserved() -> None:
    """The pack communicates the input, audit, and provider boundaries users rely on."""
    all_text = _norm("\n".join(_read(path) for path in _markdown_files()))
    required = [
        "5 MiB", ".jsonl", "UTF-8", "case_id", "duplicate", "reject",
        "dataset row", "bearer token", "authorization header", "environment variable",
        "PF-016", "Sprint 3", "live provider",
    ]
    missing = [item for item in required if _norm(item) not in all_text]
    assert not missing, f"material security or privacy constraints are missing: {missing}"


def test_no_credential_values_are_exposed() -> None:
    """No submitted Markdown contains a credential-like concrete value."""
    text = "\n".join(_read(path) for path in _markdown_files())
    patterns = {
        "OpenAI-style secret": r"\bsk-[A-Za-z0-9_-]{8,}",
        "AWS access key": r"\bAKIA[A-Z0-9]{16}\b",
        "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "database password in URI": r"\b(?:postgres(?:ql)?|redis)://[^\s:@/]+:[^\s@/]+@",
        "OIDC secret assignment": r"OIDC_CLIENT_SECRET\s*=\s*(?!<|\$|\{|\[|REDACTED)[^\s`]+",
    }
    hits = [label for label, pattern in patterns.items() if re.search(pattern, text, re.I)]
    assert not hits, f"launch pack appears to expose credential values: {hits}"


def test_committed_scope_and_capacity() -> None:
    """Every frozen Sprint 1 commitment appears in the scheduled plan."""
    plan_text = _read(_find_doc("plan"))
    scheduled = _scheduled_text(plan_text)
    committed = [row for row in _work_items() if row["status"] == "committed" and row["target_sprint"] == "1"]
    missing = [row["item_id"] for row in committed if not re.search(rf"\b{row['item_id']}\b", scheduled, re.I)]
    assert not missing, f"committed Sprint 1 IDs are missing from scheduled scope: {missing}"
    expected_points = sum(int(row["effort_points"]) for row in committed)
    normalized = _norm(plan_text)
    assert str(expected_points) in normalized and "50" in normalized, (
        "plan must make the 49-point commitment and 50-point capacity visible for scope control"
    )


def test_dependency_and_owner_integrity() -> None:
    """Committed work retains dependency order/annotations and accountable owners."""
    plan_text = _scheduled_text(_read(_find_doc("plan")))
    committed = [row for row in _work_items() if row["status"] == "committed" and row["target_sprint"] == "1"]
    positions = {row["item_id"]: plan_text.casefold().find(row["item_id"].casefold()) for row in committed}
    problems: list[str] = []
    for row in committed:
        primary_line = _primary_item_line(plan_text, row)
        context = _norm(primary_line or _line_for_id(plan_text, row["item_id"]))
        if _norm(row["suggested_owner"]) not in context:
            problems.append(f"{row['item_id']} lacks owner {row['suggested_owner']}")
        for dep in filter(None, row["depends_on"].split(";")):
            explicit = _norm(dep) in _norm(primary_line)
            ordered = 0 <= positions.get(dep, -1) < positions[row["item_id"]]
            if not (explicit or ordered):
                problems.append(f"{row['item_id']} does not preserve dependency {dep}")
    assert not problems, "; ".join(problems)


def test_out_of_scope_and_team_boundaries() -> None:
    """Rejected/blocked work is not scheduled, and cross-chat role boundaries remain explicit."""
    plan_text = _read(_find_doc("plan"))
    scheduled = _scheduled_text(plan_text)
    bad_ids = ["PF-016", "PF-017", "PF-018", "PF-019", "PF-020"]
    wrongly_scheduled = [item_id for item_id in bad_ids if re.search(rf"\b{item_id}\b", scheduled, re.I)]
    assert not wrongly_scheduled, f"blocked, rejected, or deferred items are scheduled in Sprint 1: {wrongly_scheduled}"
    pack = _norm("\n".join(_read(path) for path in _markdown_files()))
    expectations = [
        ("producer boundary", ("remy", "does not", "code")),
        ("QA boundary", ("ivy", "does not", "source")),
        ("development branch", ("feature", "sprint 1")),
        ("QA branch", ("feature", "qa 1")),
        ("DevOps branch", ("feature", "devops 1")),
        ("merge policy", ("regular merge", "never", "rebase")),
    ]
    missing = [label for label, tokens in expectations if not all(token in pack for token in tokens)]
    assert not missing, f"team boundaries or safe merge workflow are missing: {missing}"
