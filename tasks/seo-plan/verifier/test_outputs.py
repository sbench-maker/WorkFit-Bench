from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


RESULTS = Path(os.environ.get("SUBMISSION_DIR", "/root/results/seo-plan"))
EXPECTED_FILES = [
    "SEO-STRATEGY.md",
    "COMPETITOR-ANALYSIS.md",
    "CONTENT-CALENDAR.md",
    "IMPLEMENTATION-ROADMAP.md",
    "SITE-STRUCTURE.md",
]


def read_file(name: str) -> str:
    path = RESULTS / name
    assert path.is_file(), f"missing requested deliverable: {path}"
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(f"{path} is not readable UTF-8 Markdown: {exc}")


def read_optional(name: str) -> str:
    """Read supporting prose without turning one missing file into repeated parse errors."""
    path = RESULTS / name
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def normalized(text: str) -> str:
    text = text.casefold().replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text)


def numeric_text(text: str) -> str:
    return re.sub(r"(?<=\d)[,_](?=\d)", "", normalized(text))


def has_nearby(text: str, groups: list[tuple[str, ...]], span: int = 900) -> bool:
    """Accept synonyms when one term from each group occurs in a compact passage."""
    text = normalized(text)
    starts = []
    for first in groups[0]:
        starts.extend(match.start() for match in re.finditer(re.escape(first), text))
    for start in starts:
        window = text[max(0, start - span // 3): start + span]
        if all(any(term in window for term in group) for group in groups[1:]):
            return True
    return False


def test_requested_deliverables_are_readable() -> None:
    """All explicitly requested artifacts must be present and usable."""
    assert RESULTS.is_dir(), f"requested output directory does not exist: {RESULTS}"
    for name in EXPECTED_FILES:
        body = read_file(name)
        assert len(body.strip()) >= 700, f"{name} is too sparse to be a usable strategic deliverable"
        assert len(re.findall(r"\b[A-Za-z][A-Za-z0-9/-]*\b", body)) >= 100, (
            f"{name} does not contain enough substantive planning content"
        )


@pytest.mark.parametrize(
    "case",
    [
        "company_and_competitors",
        "organic_sessions_baseline",
        "qualified_demos_baseline",
        "indexed_pages_baseline",
        "month_3_targets",
        "month_6_targets",
        "month_12_targets",
    ],
)
def test_snapshot_baseline_and_competitor_scope(case: str) -> None:
    """Frozen identities and KPI checkpoints should be reported without numeric drift."""
    strategy = numeric_text(read_file("SEO-STRATEGY.md"))
    competitor = normalized(read_file("COMPETITOR-ANALYSIS.md"))
    if case == "company_and_competitors":
        assert "closepilot" in strategy, "the strategy does not identify the company in the supplied snapshot"
        missing = [name for name in ["numericone", "reconflow", "monthendly", "ledgerbeam", "clearclose"] if name not in competitor]
        assert not missing, f"competitor analysis omits supplied competitors: {missing}"
    elif case == "organic_sessions_baseline":
        assert "118121" in strategy, "organic-session baseline is missing or differs from the frozen snapshot"
    elif case == "qualified_demos_baseline":
        assert "1443" in strategy, "qualified-demo baseline is missing or differs from the frozen snapshot"
    elif case == "indexed_pages_baseline":
        assert re.search(r"indexed.{0,80}\b103\b|\b103\b.{0,80}indexed", strategy), (
            "the 103-page indexed baseline is not tied to indexation"
        )
    elif case == "month_3_targets":
        assert has_nearby(strategy, [("month 3", "m3", "3 month"), ("8%", "8 percent", "+8"), ("12%", "12 percent", "+12"), ("24",)]), (
            "month-3 KPI targets are incomplete or not tied to the checkpoint"
        )
    elif case == "month_6_targets":
        assert has_nearby(strategy, [("month 6", "m6", "6 month"), ("22%", "22 percent", "+22"), ("32%", "32 percent", "+32"), ("38",)]), (
            "month-6 KPI targets are incomplete or not tied to the checkpoint"
        )
    elif case == "month_12_targets":
        assert has_nearby(strategy, [("month 12", "m12", "12 month"), ("55%", "55 percent", "+55"), ("75%", "75 percent", "+75"), ("65",)]), (
            "month-12 KPI targets are incomplete or not tied to the checkpoint"
        )


@pytest.mark.parametrize(
    "case",
    ["pricing_noindex", "wrong_canonical", "orphan_page", "checklist_conflict", "sap_gate", "beta_gate"],
)
def test_material_site_and_launch_constraints(case: str) -> None:
    """Material page-state and launch constraints must result in a safe planning action."""
    site = read_optional("SITE-STRUCTURE.md")
    calendar = read_optional("CONTENT-CALENDAR.md")
    roadmap = read_optional("IMPLEMENTATION-ROADMAP.md")
    combined = "\n".join([site, calendar, roadmap])
    if case == "pricing_noindex":
        assert has_nearby(combined, [("/pricing", "p001"), ("noindex", "indexable"), ("remove", "fix", "correct")]), (
            "the accidental pricing-page noindex is not paired with a corrective action"
        )
    elif case == "wrong_canonical":
        assert has_nearby(combined, [("p002", "/product/close-automation"), ("canonical",), ("self", "correct", "fix")]), (
            "the wrong P002 canonical is not resolved while preserving its distinct commercial intent"
        )
    elif case == "orphan_page":
        assert has_nearby(combined, [("p003", "/features/account-reconciliation"), ("link",)]), (
            "the high-value P003 orphan is not given an internal-link remedy"
        )
    elif case == "checklist_conflict":
        assert has_nearby(combined, [("p006",), ("p007",), ("301", "redirect", "consolidat", "merge")]), (
            "the two indexable C06 checklist pages are not given a concrete consolidation or intent-resolution action"
        )
    elif case == "sap_gate":
        assert has_nearby(combined, [("sap", "p005", "c11"), ("month 8", "m8"), ("ga", "general availability", "publish")]), (
            "SAP content is not clearly gated to month-8 general availability"
        )
    elif case == "beta_gate":
        assert has_nearby(combined, [("intercompany", "c16"), ("beta",), ("not general", "no general", "private", "invite-only", "exclude")]), (
            "intercompany reconciliation is not preserved as beta-only rather than public GA"
        )
