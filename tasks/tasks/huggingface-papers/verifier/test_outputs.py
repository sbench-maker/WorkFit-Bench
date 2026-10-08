from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest


RESULTS_DIR = Path(os.environ.get("SKILLSBENCH_RESULTS_DIR", "/root/results"))
DATA_DIR = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data"))
OUTPUT_PATH = RESULTS_DIR / "output.json"


@dataclass(frozen=True)
class Artifact:
    payload: object | None
    raw: str
    error: str | None


def _load_artifact() -> Artifact:
    try:
        raw = OUTPUT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        return Artifact(None, "", f"cannot read {OUTPUT_PATH}: {exc}")
    try:
        return Artifact(json.loads(raw), raw, None)
    except json.JSONDecodeError as exc:
        return Artifact(None, raw, f"invalid JSON: {exc}")


def _flatten(value: object) -> list[str]:
    parts: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            parts.append(str(key))
            parts.extend(_flatten(child))
    elif isinstance(value, list):
        for child in value:
            parts.extend(_flatten(child))
    elif value is not None:
        parts.append(str(value))
    return parts


def _normalized_text(artifact: Artifact) -> str:
    source = " ".join(_flatten(artifact.payload)) if artifact.payload is not None else artifact.raw
    return re.sub(r"\s+", " ", source.replace(",", "")).casefold()


def _require_parseable(artifact: Artifact) -> None:
    if artifact.error:
        pytest.skip("semantic checks skipped because artifact usability already records: " + artifact.error)


@pytest.fixture(scope="session")
def artifact() -> Artifact:
    return _load_artifact()


def test_paper_identity_and_authors(artifact: Artifact) -> None:
    _require_parseable(artifact)
    metadata = json.loads((DATA_DIR / "paper_metadata.json").read_text(encoding="utf-8"))
    text = _normalized_text(artifact)
    assert metadata["paperId"].casefold() in text, "the requested paper revision is not identified"
    title_markers = ("cedarswitch", "budget-aware", "sparse", "summarization")
    assert all(marker in text for marker in title_markers), "the paper title is missing or refers to another work"
    missing_authors = [author["name"] for author in metadata["authors"] if author["name"].casefold() not in text]
    assert not missing_authors, f"paper authors missing from the brief: {missing_authors}"


@pytest.mark.parametrize(
    ("asset_kind", "source_file"),
    [
        ("models", "linked_models.json"),
        ("datasets", "linked_datasets.json"),
        ("spaces", "linked_spaces.json"),
    ],
    ids=["models", "datasets", "spaces"],
)
def test_linked_asset_coverage(artifact: Artifact, asset_kind: str, source_file: str) -> None:
    _require_parseable(artifact)
    expected = json.loads((DATA_DIR / source_file).read_text(encoding="utf-8"))
    text = _normalized_text(artifact)
    missing = [row["id"] for row in expected if row["id"].casefold() not in text]
    assert not missing, f"linked {asset_kind} missing from the brief: {missing}"


@pytest.mark.parametrize(
    ("fact_group", "required_markers"),
    [
        ("english_quality", ["english", "36.9", "31.8", "5.1", "0.884", "5.6"]),
        ("spanish_quality", ["spanish", "33.1", "27.4", "5.7", "0.868", "7.1"]),
        ("device_efficiency", ["16", "508", "526", "38.0", "37.8", "7.4", "9"]),
    ],
    ids=["english-quality", "spanish-quality", "device-efficiency"],
)
def test_core_quantitative_evidence(artifact: Artifact, fact_group: str, required_markers: list[str]) -> None:
    _require_parseable(artifact)
    text = _normalized_text(artifact)
    missing = [marker for marker in required_markers if marker not in text]
    assert not missing, f"{fact_group} omits or changes decision-relevant paper values: {missing}"
