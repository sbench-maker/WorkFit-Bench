from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path


RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = RESULTS_DIR / "onboarding_sequence.md"


METRIC_ALIASES = {
    "open": ("open rate", "opens"),
    "click": ("click-through rate", "click through rate", "ctr", "click rate", "clicks"),
    "activation": ("activation rate", "activation within", "activations", "conversion rate"),
    "unsubscribe": ("unsubscribe rate", "unsub rate", "unsubscribes"),
}


def read_output() -> str:
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def normalized(value: str) -> str:
    value = value.replace("→", "-->").replace("–", "-").replace("—", "-")
    return re.sub(r"[ \t]+", " ", value).lower()


def labeled_email_slots(text: str) -> set[int]:
    patterns = [
        r"(?im)^\s*#{0,6}\s*(?:email|message|touch)\s*#?\s*([1-6])(?:\s*[a-z])?\b",
        r"(?im)^\s*\|\s*(?:email|message|touch)?\s*#?\s*([1-6])(?:\s*[a-z])?\s*\|",
    ]
    slots: set[int] = set()
    for pattern in patterns:
        slots.update(int(match) for match in re.findall(pattern, text))
    return slots


def approved_urls() -> set[str]:
    payload = json.loads((DATA_DIR / "approved_assets.json").read_text(encoding="utf-8"))
    return {row["url"] for row in payload["approved_destinations"]}


def reported_metric_values(text: str, aliases: tuple[str, ...]) -> list[float]:
    """Extract labeled percentages from prose/lists and simple Markdown tables."""
    values: list[float] = []
    label_pattern = "(?:" + "|".join(re.escape(alias) for alias in aliases) + ")"
    for match in re.finditer(
        rf"(?i){label_pattern}[^\n%]{{0,55}}?(\d+(?:\.\d+)?)\s*%",
        text,
    ):
        values.append(float(match.group(1)))

    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    for index, line in enumerate(lines):
        header = [cell.strip().lower() for cell in line.strip("|").split("|")]
        columns = [
            column_index
            for column_index, cell in enumerate(header)
            if any(alias in cell for alias in aliases)
        ]
        if not columns:
            continue
        for candidate in lines[index + 1 :]:
            cells = [cell.strip() for cell in candidate.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                continue
            if len(cells) != len(header):
                break
            if any(any(alias in cell.lower() for alias in aliases) for cell in cells):
                break
            for column_index in columns:
                match = re.search(r"(\d+(?:\.\d+)?)\s*%", cells[column_index])
                if match:
                    values.append(float(match.group(1)))
    return values


def historical_candidates() -> dict[str, list[float]]:
    with (DATA_DIR / "onboarding_history.csv").open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["record_scope"] == "production"]

    def rates(group: list[dict]) -> dict[str, float]:
        delivered = sum(int(row["delivered"]) for row in group)
        return {
            "open": 100 * sum(int(row["unique_opens"]) for row in group) / delivered,
            "click": 100 * sum(int(row["unique_clicks"]) for row in group) / delivered,
            "activation": 100 * sum(int(row["activations_within_3d"]) for row in group) / delivered,
            "unsubscribe": 100 * sum(int(row["unsubscribes"]) for row in group) / delivered,
        }

    candidates = {metric: [] for metric in METRIC_ALIASES}
    groups = [rows]
    groups.extend(
        [row for row in rows if int(row["email_number"]) == email_number]
        for email_number in range(1, 7)
    )
    for group in groups:
        for metric, value in rates(group).items():
            candidates[metric].append(value)
    return candidates


def test_artifact_usability() -> None:
    text = read_output()
    assert OUTPUT.is_file(), "onboarding_sequence.md is missing; the requested campaign cannot be handed to marketing"
    assert len(text.strip()) >= 3000, "the Markdown file is too short to contain six copy-ready emails and their flow"
    assert labeled_email_slots(text) == set(range(1, 7)), (
        "the deliverable must expose all six numbered email slots; branch variants may share a slot number"
    )
    lower = normalized(text)
    has_flow_label = any(label in lower for label in ("flow diagram", "journey map", "sequence flow", "automation flow"))
    has_flow_edges = "-->" in lower and "exit" in lower and ("suppress" in lower or "hold" in lower)
    assert has_flow_label and has_flow_edges, (
        "a labeled text flow with transitions, exits, and a suppression/hold path is needed for configuration"
    )


def test_campaign_facts_and_destinations() -> None:
    text = read_output()
    lower = normalized(text)
    assert re.search(r"connect(?:ed|ing)?\s+(?:at least\s+)?(?:one\s+)?(?:git\s+)?repositor", lower), (
        "the sequence does not preserve repository connection as an activation requirement"
    )
    assert re.search(r"(?:invite|invited|invitation)[^\n.]{0,45}(?:at least\s+)?(?:two|2)\s+teammate", lower), (
        "the sequence does not preserve the requirement to invite at least two teammates"
    )
    assert re.search(r"publish(?:ed|ing)?[^\n.]{0,45}(?:first\s+)?release\s+checklist", lower), (
        "the sequence does not preserve first-checklist publication as an activation requirement"
    )
    assert re.search(r"(?:all\s+three|three[- ](?:part|step)|\band\b[^\n]{0,80}\band\b)", lower), (
        "the three activation actions are present but are not clearly combined into one completion definition"
    )

    urls = {
        raw.rstrip(".,;:'\"`")
        for raw in re.findall(r"https://[^\s)\]>]+", text)
        if ".test" in raw
    }
    allowed = approved_urls()
    assert urls <= allowed, f"unapproved destination(s) appear in the ready-to-configure sequence: {sorted(urls - allowed)}"
    assert urls, "the ready-to-configure sequence does not wire any of the supplied approved destinations"

    forbidden = [
        "guaranteed results",
        "guaranteed activation",
        "zero setup",
        "no setup required",
        "instant setup",
        "50% off",
        "limited-time discount",
    ]
    found = [phrase for phrase in forbidden if phrase in lower]
    assert not found, f"the copy uses an expressly unapproved promise or offer: {found}"


def test_historical_benchmarks() -> None:
    text = read_output()
    candidates = historical_candidates()
    tolerances = {"open": 2.0, "click": 1.25, "activation": 1.0, "unsubscribe": 0.18}
    missing_or_wrong: list[str] = []
    for metric, aliases in METRIC_ALIASES.items():
        reported = reported_metric_values(text, aliases)
        if not reported or not any(
            abs(actual - expected) <= tolerances[metric]
            for actual in reported
            for expected in candidates[metric]
        ):
            missing_or_wrong.append(metric)
    assert not missing_or_wrong, (
        "these benchmark metrics are missing or inconsistent with production-scope history: "
        + ", ".join(missing_or_wrong)
    )

    for line in normalized(text).splitlines():
        if ("overall" in line or "weighted" in line or "baseline" in line) and re.search(r"\b100(?:\.0+)?\s*%", line):
            raise AssertionError("a 100% overall/weighted baseline indicates that internal QA rows contaminated the benchmark")
