from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "assumption_priority.md"
ID_RE = re.compile(r"(?<![A-Za-z0-9])A(?:0[1-9]|1[0-9]|20)(?![A-Za-z0-9])", re.IGNORECASE)


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_text() -> str:
    assert OUTPUT_PATH.is_file(), "assumption_priority.md is missing, so the roadmap brief cannot be used"
    try:
        return OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        pytest.fail(f"assumption_priority.md is not readable UTF-8 Markdown: {exc}")


def load_text_optional() -> str | None:
    """Avoid cascading one file/readability defect into all semantic criteria."""
    if not OUTPUT_PATH.is_file():
        return None
    try:
        return OUTPUT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def expected_decisions() -> dict[str, dict[str, object]]:
    assumptions = read_csv("assumptions.csv")
    observations: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv("research_observations.csv"):
        observations[row["assumption_id"]].append(row)
    expected: dict[str, dict[str, object]] = {}
    for row in assumptions:
        assumption_id = row["assumption_id"]
        linked = observations[assumption_id]
        opportunity = sum(
            (float(item["importance_1_5"]) / 5.0)
            * (1.0 - float(item["current_satisfaction_1_5"]) / 5.0)
            for item in linked
        ) / len(linked)
        impact = opportunity * int(row["quarterly_customers_affected"])
        risk = (1.0 - int(row["confidence_pct"]) / 100.0) * int(row["validation_effort_days"])
        if impact >= 100 and risk >= 2:
            quadrant, action = "HH", "test"
        elif impact >= 100:
            quadrant, action = "HL", "proceed"
        elif risk >= 2:
            quadrant, action = "LH", "reject"
        else:
            quadrant, action = "LL", "defer"
        expected[assumption_id] = {
            "impact": impact,
            "risk": risk,
            "quadrant": quadrant,
            "action": action,
        }
    return expected


def occurrence_blocks(text: str, assumption_id: str) -> list[str]:
    """Return layout-neutral local blocks for every mention of an assumption ID."""
    matches = list(ID_RE.finditer(text))
    blocks: list[str] = []
    for index, match in enumerate(matches):
        if match.group(0).upper() != assumption_id:
            continue
        headings = list(re.finditer(r"(?m)^#{1,6}\s+.+$", text[:match.start()]))
        section_start = headings[-1].start() if headings else max(0, match.start() - 400)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        end = min(next_start, match.start() + 900)
        blocks.append(text[section_start:end])
    return blocks


ACTION_PATTERNS = {
    "test": re.compile(r"\b(test|experiment|validate|validation)\w*\b", re.IGNORECASE),
    "proceed": re.compile(r"\b(proceed|implement|implementation|build|ship|commit)\w*\b", re.IGNORECASE),
    "reject": re.compile(r"\b(reject|drop|remove|decline)\w*\b|do\s+not\s+pursue", re.IGNORECASE),
    "defer": re.compile(r"\b(defer|deferred|backlog|later|postpone|park)\w*\b", re.IGNORECASE),
}


def quadrant_matches(block: str, quadrant: str) -> bool:
    labels = {
        "HH": ("high", "high"),
        "HL": ("high", "low"),
        "LH": ("low", "high"),
        "LL": ("low", "low"),
    }
    impact_label, risk_label = labels[quadrant]
    cleaned = re.sub(r"[`*_]", "", block.lower())
    patterns = [
        rf"impact\s*(?:level\s*)?[:=\-/|]?\s*{impact_label}.{{0,120}}risk\s*(?:level\s*)?[:=\-/|]?\s*{risk_label}",
        rf"{impact_label}[\s-]+impact.{{0,80}}{risk_label}[\s-]+risk",
        rf"risk\s*(?:level\s*)?[:=\-/|]?\s*{risk_label}.{{0,120}}impact\s*(?:level\s*)?[:=\-/|]?\s*{impact_label}",
        rf"\b{quadrant.lower()}\b",
    ]
    return any(re.search(pattern, cleaned, flags=re.DOTALL) for pattern in patterns)


def decision_is_present(text: str, assumption_id: str, quadrant: str, action: str) -> bool:
    return any(
        quadrant_matches(block, quadrant) and ACTION_PATTERNS[action].search(block)
        for block in occurrence_blocks(text, assumption_id)
    )


def test_all_assumptions_are_covered():
    """Criterion: assumption_coverage."""
    text = load_text_optional()
    if text is None:
        pytest.skip("readability is scored only by artifact_usability")
    expected_ids = set(expected_decisions())
    observed_ids = {match.group(0).upper() for match in ID_RE.finditer(text)}
    missing = sorted(expected_ids - observed_ids)
    assert not missing, (
        f"the brief omits assumptions {missing}; the council would make roadmap decisions from incomplete scope"
    )


@pytest.mark.parametrize("quadrant", ["HH", "HL", "LH", "LL"])
def test_matrix_decisions(quadrant: str):
    """Criterion: matrix_decisions."""
    text = load_text_optional()
    if text is None:
        pytest.skip("readability is scored only by artifact_usability")
    expected = expected_decisions()
    observed_ids = {match.group(0).upper() for match in ID_RE.finditer(text)}
    problems = []
    for assumption_id, item in expected.items():
        if item["quadrant"] != quadrant or assumption_id not in observed_ids:
            continue
        if not decision_is_present(text, assumption_id, quadrant, str(item["action"])):
            problems.append(assumption_id)
    assert not problems, (
        f"assumptions {problems} do not show the data-determined {quadrant} quadrant and its matching action; "
        "misclassification would send roadmap work to the wrong treatment"
    )
