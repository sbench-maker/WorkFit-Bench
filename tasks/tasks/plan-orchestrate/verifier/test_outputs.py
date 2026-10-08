from __future__ import annotations

import os
import re
import shlex
from collections import Counter
from pathlib import Path

import pytest


TASK_ROOT = Path(os.environ.get("TASK_ROOT", "/root")).resolve()
OUTPUT_PATH = TASK_ROOT / "results/orchestration.md"
PLAN_PATH = TASK_ROOT / "data/workspace/docs/merchant_assist_rollout.md"
PROJECT_PATH = TASK_ROOT / "data/workspace/pyproject.toml"

EXPECTED_TITLES = {
    1: "Choose gateway boundaries and record the architecture RFC",
    2: "Implement tenant authorization guards for operator actions",
    3: "Resolve PyTorch image compilation failures in the release pipeline",
    4: "Run the end-to-end checkout recovery integration test",
    5: "Refresh the operator README and release changelog",
    6: "Review release-candidate readiness and record the decision",
    7: "Ramp the pilot cohort in three traffic increments",
}

EXPECTED_CHAINS = {
    1: ["ecc:planner", "ecc:architect"],
    2: ["ecc:tdd-guide", "ecc:python-reviewer", "ecc:security-reviewer"],
    3: ["ecc:pytorch-build-resolver"],
    4: ["ecc:tdd-guide", "ecc:e2e-runner"],
    5: ["ecc:doc-updater"],
    6: ["ecc:python-reviewer", "ecc:code-reviewer"],
    7: ["ecc:code-reviewer"],
}

CATALOGUE = {
    "planner", "architect", "tdd-guide", "code-reviewer", "security-reviewer",
    "refactor-cleaner", "doc-updater", "docs-lookup", "e2e-runner",
    "database-reviewer", "harness-optimizer", "loop-operator", "chief-of-staff",
    "build-error-resolver", "cpp-build-resolver", "go-build-resolver",
    "java-build-resolver", "kotlin-build-resolver", "rust-build-resolver",
    "pytorch-build-resolver", "python-reviewer", "typescript-reviewer",
    "go-reviewer", "rust-reviewer", "cpp-reviewer", "java-reviewer",
    "kotlin-reviewer", "flutter-reviewer",
}


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _load_text() -> tuple[str, str | None]:
    try:
        text = OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "", f"cannot read {OUTPUT_PATH}: {exc}"
    if not text.strip():
        return "", f"{OUTPUT_PATH} is empty"
    return text, None


def _commands(text: str) -> tuple[list[dict], list[str]]:
    parsed: list[dict] = []
    errors: list[str] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        candidate = raw.strip().strip("`").strip()
        if not candidate.startswith(("/ecc:orchestrate", "/orchestrate")):
            continue
        try:
            tokens = shlex.split(candidate, posix=True)
        except ValueError as exc:
            errors.append(f"line {line_number}: {exc}")
            continue
        if len(tokens) < 4:
            errors.append(f"line {line_number}: command has fewer than four arguments")
            continue
        description = tokens[3]
        match = re.search(r"#step-(\d+)\]", description, flags=re.IGNORECASE)
        parsed.append(
            {
                "line": line_number,
                "raw": candidate,
                "command": tokens[0],
                "subcommand": tokens[1],
                "agents": [item.strip() for item in tokens[2].split(",") if item.strip()],
                "description": description,
                "step": int(match.group(1)) if match else None,
                "extra": tokens[4:],
            }
        )
    return parsed, errors


def _require_parseable() -> tuple[str, list[dict]]:
    text, issue = _load_text()
    if issue:
        pytest.skip(f"artifact root failure is scored by artifact criterion: {issue}")
    commands, errors = _commands(text)
    if errors or not commands:
        pytest.skip(
            "command parse failure is scored by artifact criterion: "
            + ("; ".join(errors) if errors else "no commands found")
        )
    return text, commands


def _overview_line(text: str, title: str) -> str | None:
    wanted = _norm(title)
    for line in text.splitlines():
        if wanted in _norm(line):
            return line
    return None


def test_artifact_and_command_usability():
    text, issue = _load_text()
    assert issue is None, issue
    commands, errors = _commands(text)
    assert not errors, "ready-to-paste command lines are malformed: " + "; ".join(errors)
    assert commands, "no /orchestrate custom command was found in the requested Markdown"
    assert all(item["command"] == "/ecc:orchestrate" for item in commands), (
        "the image contains the ECC plugin marker, so every command must use /ecc:orchestrate"
    )
    assert all(item["subcommand"] == "custom" and not item["extra"] for item in commands), (
        "each runnable line must have exactly the command, custom subcommand, chain, and task description"
    )
    assert all(item["step"] is not None for item in commands), (
        "every command description must identify its source step"
    )
    assert not re.search(r"--(?:mode|gate|agents)(?:=|\s)", text), (
        "the output contains an unsupported orchestrator flag"
    )
    assert not re.search(r"\{(?:ORCH_CMD|AGENT)[^}]*\}", text), (
        "the output still contains an unresolved command or agent placeholder"
    )


def test_plan_coverage_and_scope():
    text, commands = _require_parseable()
    plan = PLAN_PATH.read_text(encoding="utf-8")
    source_steps = {
        int(number): title.strip()
        for number, title in re.findall(r"^## Step (\d+) — (.+)$", plan, flags=re.MULTILINE)
    }
    assert source_steps == EXPECTED_TITLES, "the verifier fixture's plan outline is inconsistent"
    for step_id, title in source_steps.items():
        assert _overview_line(text, title) is not None, (
            f"the full-plan overview omits step {step_id}: {title}"
        )
    counts = Counter(item["step"] for item in commands)
    assert set(counts) == set(range(2, 7)), (
        "runnable commands must cover exactly steps 2–6, excluding overview-only steps 1 and 7"
    )
    assert all(counts[step_id] >= 2 for step_id in range(2, 7)), (
        "each scoped step needs both a detail command and a copy in the batch block"
    )
    remaining = [item["step"] for item in commands]
    target = list(range(2, 7))
    for pass_number in (1, 2):
        cursor = 0
        for index, step_id in enumerate(remaining):
            if step_id == target[cursor]:
                cursor += 1
                if cursor == len(target):
                    remaining = remaining[index + 1 :]
                    break
        assert cursor == len(target), (
            f"could not find ordered {'detail' if pass_number == 1 else 'batch'} "
            "commands for steps 2–6"
        )
    for step_id in range(2, 7):
        assert _norm(text).count(_norm(source_steps[step_id])) >= 2, (
            f"step {step_id} needs both overview and per-step detail context"
        )


def test_agent_chain_decisions():
    text, commands = _require_parseable()
    project = PROJECT_PATH.read_text(encoding="utf-8")
    assert "torch==" in project.casefold(), "the verifier fixture no longer declares PyTorch"

    by_step: dict[int, set[tuple[str, ...]]] = {}
    for item in commands:
        chain = item["agents"]
        assert len(chain) <= 4, f"step {item['step']} chain exceeds four agents"
        assert len(chain) == len(set(chain)), f"step {item['step']} chain contains a duplicate agent"
        bare = [name.removeprefix("ecc:") for name in chain]
        assert all(name.startswith("ecc:") for name in chain), (
            f"step {item['step']} mixes bare and plugin-prefixed agent names"
        )
        assert set(bare) <= CATALOGUE, f"step {item['step']} contains an unknown agent"
        by_step.setdefault(item["step"], set()).add(tuple(chain))

    for step_id in range(2, 7):
        assert by_step.get(step_id) == {tuple(EXPECTED_CHAINS[step_id])}, (
            f"step {step_id} has the wrong or inconsistent chain; expected "
            + ",".join(EXPECTED_CHAINS[step_id])
        )

    for step_id, title in EXPECTED_TITLES.items():
        line = _overview_line(text, title)
        assert line is not None
        expected = EXPECTED_CHAINS[step_id]
        positions = [_norm(line).find(_norm(agent)) for agent in expected]
        assert all(position >= 0 for position in positions), (
            f"overview chain for step {step_id} omits an expected agent"
        )
        assert positions == sorted(positions), (
            f"overview chain for step {step_id} presents agents in the wrong order"
        )
        present_catalogue = {
            name
            for name in CATALOGUE
            if re.search(rf"(?<![a-z0-9-])(?:ecc:)?{re.escape(name)}(?![a-z0-9-])", line, re.I)
        }
        assert present_catalogue == {name.removeprefix("ecc:") for name in expected}, (
            f"overview chain for step {step_id} includes an unexpected agent"
        )
