from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

import pytest


OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/brief.md"))

SOURCES = {
    "trialstone": {
        "aliases": ("trialstone-2025", "verified drafting in support escalations", "okafor"),
        "facts": (
            (r"12\.4\s*%", "12.4% resolution-time reduction"),
            (r"2\.7\s*%", "2.7% verified-draft critical-error rate"),
            (r"0\.8\s*%", "0.8% manual-note critical-error rate"),
        ),
        "reference_title": "verified drafting in support escalations: a cluster-randomized field trial",
        "reference_tokens": ("okafor", "wei", "serrat", "2025", "journal of service systems"),
    },
    "cedar": {
        "aliases": ("cedar-ops-2026", "escalation handoff pilot", "cedar & finch"),
        "facts": (
            (r"18\s*%", "18% handling-time decline"),
            (r"22\s*(?:percentage\s*points?|points?|pp)", "22 percentage-point completeness gain"),
            (r"61\s*%", "61% adoption"),
        ),
        "reference_title": "escalation handoff pilot: eight-week operations readout",
        "reference_tokens": ("cedar & finch", "2026", "escalation handoff pilot"),
    },
    "vectorloom": {
        "aliases": (
            "vectorloom-wp",
            "faster escalations with synapsenote assist",
            "vale, i.",
            "vale and buck",
            "vale & buck",
        ),
        "facts": (
            (r"31\s*%", "31% self-reported preparation-time reduction"),
            (r"65\s+(?:customer\s+)?organizations?|65\s+customers?", "65 participating organizations"),
            (r"(?:78[ ,]?000|78k)\s+handoffs?", "approximately 78,000 handoffs"),
        ),
        "reference_title": "faster escalations with synapsenote assist",
        "reference_tokens": ("vale", "buck", "faster escalations with synapsenote assist", "vectorloom"),
    },
    "reviewlab": {
        "aliases": ("reviewlab-2024", "human review as a safety control", "iqbal"),
        "facts": (
            (r"8\.6\s*%", "8.6% unreviewed critical-error rate"),
            (r"1\.9\s*%", "1.9% reviewed critical-error rate"),
            (r"1\.2\s*%", "1.2% manual critical-error rate"),
            (r"9\s*%", "9% reviewed-generation time benefit"),
        ),
        "reference_title": "human review as a safety control for generated handoff notes",
        "reference_tokens": ("iqbal", "mensah", "2024", "applied service science conference"),
    },
}


def _read_output() -> str:
    assert OUTPUT.is_file(), "the requested /root/results/brief.md artifact is missing"
    try:
        text = OUTPUT.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(f"brief.md is not readable UTF-8: {exc}")
    assert text.strip(), "brief.md is empty"
    return text


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("percentage-point", "percentage point")
    text = re.sub(r"\bpercent\b", "%", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _source_windows(text: str, aliases: tuple[str, ...], radius: int = 1100) -> str:
    windows = []
    for alias in aliases:
        for match in re.finditer(re.escape(_normalize(alias)), text):
            windows.append(text[max(0, match.start() - radius) : match.end() + radius])
    return " ".join(windows)


def _source_section(text: str, aliases: tuple[str, ...]) -> str:
    headings = list(re.finditer(r"(?m)^#{1,6}\s+.+$", text))
    for index, heading in enumerate(headings):
        if any(_normalize(alias) in heading.group(0) for alias in aliases):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            return text[heading.start():end]
    return ""


def _has_source(text: str, aliases: tuple[str, ...]) -> bool:
    return any(_normalize(alias) in text for alias in aliases)


def test_artifact_scope() -> None:
    text = _read_output()
    normalized = _normalize(text)
    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    assert word_count >= 350, (
        f"brief.md has {word_count} words; it is too short to cover the requested evidence"
    )
    missing = [name for name, source in SOURCES.items() if not _has_source(normalized, source["aliases"])]
    assert not missing, f"the brief omits supplied source(s): {', '.join(missing)}"
    assert "[" not in text or "[insert" not in normalized, "brief contains an unfilled placeholder"


@pytest.mark.parametrize("source_name", tuple(SOURCES))
def test_material_findings_fidelity(source_name: str) -> None:
    normalized = _normalize(_read_output())
    source = SOURCES[source_name]
    windows = _source_section(normalized, source["aliases"]) or _source_windows(normalized, source["aliases"])
    assert windows, f"could not locate a recognizable reference to {source_name}"
    missing = [label for pattern, label in source["facts"] if re.search(pattern, windows) is None]
    assert not missing, (
        f"material findings for {source_name} are missing or detached from the source: {', '.join(missing)}"
    )


def _anchor_count(text: str, aliases: tuple[str, ...]) -> int:
    locations: set[str] = set()
    for alias in aliases:
        escaped = re.escape(_normalize(alias))
        patterns = (
            rf"{escaped}[^;\]\)\n]{{0,80}}?(?:\bpp?\.?|\bpages?\b|\bsections?\b)\s*([0-9]+(?:\s*[-,]\s*[0-9]+)*)",
            rf"(?:\bpp?\.?|\bpages?\b|\bsections?\b)\s*([0-9]+(?:\s*[-,]\s*[0-9]+)*)[^;\[\(\n]{{0,50}}?{escaped}",
        )
        for pattern in patterns:
            locations.update(re.findall(pattern, text))
    section = _source_section(text, aliases)
    if section:
        locations.update(re.findall(r"\b(?:pp?\.?|pages?|sections?)\s*([0-9]+(?:\s*[-,]\s*[0-9]+)*)", section))
    return len(locations)


@pytest.mark.parametrize("source_name", tuple(SOURCES))
def test_traceability_and_reference_integrity(source_name: str) -> None:
    normalized = _normalize(_read_output())
    source = SOURCES[source_name]
    anchors = _anchor_count(normalized, source["aliases"])
    assert anchors >= 2, (
        f"{source_name} has only {anchors} distinct page/section anchor(s); material claims are not sufficiently traceable"
    )

    tokens = source["reference_tokens"]
    reference_windows = _source_windows(normalized, (source["reference_title"],), radius=420)
    assert reference_windows, f"no complete reference entry was found for {source_name}"
    missing_tokens = [token for token in tokens if _normalize(token) not in reference_windows]
    assert not missing_tokens, (
        f"the reference for {source_name} is missing supplied bibliographic metadata: {', '.join(missing_tokens)}"
    )
    if source_name == "vectorloom":
        assert re.search(r"\bn\.?\s*d\.?(?:\b|\))", reference_windows), (
            "the undated VectorLoom white paper must not be assigned a fabricated publication year"
        )
