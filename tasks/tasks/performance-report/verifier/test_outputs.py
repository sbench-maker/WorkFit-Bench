from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from pathlib import Path


RESULT_PATH = Path(os.environ.get("SKILLSBENCH_RESULTS_DIR", "/root/results")) / "august_performance_report.md"
DATA_DIR = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data"))


CHANNEL_ALIASES = {
    "Paid Search": ("paid search", "search ads", "search advertising", "ppc search"),
    "Paid Social": ("paid social", "social ads", "social advertising"),
    "Email": ("email", "email marketing"),
    "Organic Search": ("organic search", "organic", "seo"),
}


def clean(text: str) -> str:
    return re.sub(r"[*_`]", "", text).lower()


def numbers(text: str) -> list[float]:
    values = []
    for raw in re.findall(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?", text):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    return values


def close_to_any(text: str, expected: float, tolerance: float) -> bool:
    return any(abs(value - expected) <= tolerance for value in numbers(text))


def fragments_with_alias(text: str, aliases: tuple[str, ...], radius: int = 0) -> list[str]:
    lines = text.splitlines()
    found: list[str] = []
    for index, line in enumerate(lines):
        normalized = clean(line)
        if any(alias in normalized for alias in aliases):
            lo, hi = max(0, index - radius), min(len(lines), index + radius + 1)
            found.append("\n".join(lines[lo:hi]))
    paragraphs = re.split(r"\n\s*\n", text)
    found.extend(p for p in paragraphs if any(alias in clean(p) for alias in aliases))
    return found


def fragment_has_values(fragments: list[str], expected: list[tuple[float, float]]) -> bool:
    return any(all(close_to_any(fragment, value, tolerance) for value, tolerance in expected) for fragment in fragments)


def load_report() -> str:
    try:
        return RESULT_PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def load_daily() -> list[dict]:
    with (DATA_DIR / "daily_channel_performance.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ("spend_usd", "leads", "mqls", "new_customers", "attributed_revenue_usd", "revenue_tracking_coverage"):
            row[key] = float(row[key])
    return rows


def aggregate(rows: list[dict], month: str, channel: str | None = None) -> dict[str, float]:
    result = defaultdict(float)
    for row in rows:
        if not row["date"].startswith(month) or (channel is not None and row["channel"] != channel):
            continue
        for key in ("spend_usd", "leads", "mqls", "new_customers", "attributed_revenue_usd"):
            result[key] += row[key]
    result["cpa"] = result["spend_usd"] / result["new_customers"] if result["spend_usd"] else 0.0
    result["roas"] = result["attributed_revenue_usd"] / result["spend_usd"] if result["spend_usd"] else 0.0
    return dict(result)


def change(current: float, prior: float) -> float:
    return (current / prior - 1.0) * 100.0


def test_artifact_readable_and_in_scope():
    assert RESULT_PATH.is_file(), "the requested August Markdown report is missing"
    report = load_report()
    assert len(report.strip()) >= 900, "the report is too small to contain the requested analysis and actions"
    normalized = clean(report)
    missing = []
    for cue, aliases in {
        "July comparison": ("july", "jul 2026", "2026-07"),
        "August reporting period": ("august", "aug 2026", "2026-08"),
        "September priorities": ("september", "sep 2026", "2026-09"),
        "targets": ("target", "goal", "plan"),
        "impact prioritization": ("impact", "expected effect"),
        "effort prioritization": ("effort", "complexity"),
        **CHANNEL_ALIASES,
    }.items():
        if not any(alias in normalized for alias in aliases):
            missing.append(cue)
    assert not missing, f"the report omits requested scope cues: {', '.join(missing)}"


def test_overall_kpis_and_comparisons():
    report = load_report()
    assert report, "overall KPI accuracy cannot be evaluated because the report is unreadable"
    rows = load_daily()
    july, august = aggregate(rows, "2026-07"), aggregate(rows, "2026-08")
    checks = [
        (("lead", "leads", "inquiry", "inquiries"), [(july["leads"], 0.1), (august["leads"], 0.1), (change(august["leads"], july["leads"]), 0.15), (1750, 0.1)]),
        (("mql", "mqls", "marketing qualified"), [(july["mqls"], 0.1), (august["mqls"], 0.1), (change(august["mqls"], july["mqls"]), 0.15), (900, 0.1)]),
        (("customer", "customers", "acquisition", "conversions"), [(july["new_customers"], 0.1), (august["new_customers"], 0.1), (change(august["new_customers"], july["new_customers"]), 0.15)]),
        (("paid spend", "media spend", "ad spend"), [(july["spend_usd"], 1.0), (august["spend_usd"], 1.0), (change(august["spend_usd"], july["spend_usd"]), 0.15), (62000, 1.0)]),
        (("attributed revenue", "reported revenue", "marketing revenue"), [(july["attributed_revenue_usd"], 1.0), (august["attributed_revenue_usd"], 1.0), (change(august["attributed_revenue_usd"], july["attributed_revenue_usd"]), 0.15)]),
    ]
    failures = []
    for aliases, expected in checks:
        fragments = fragments_with_alias(report, aliases, radius=1)
        if not fragment_has_values(fragments, expected):
            failures.append(aliases[0])
    assert not failures, "incorrect or unreconciled July/August KPI, change, or target values for: " + ", ".join(failures)


def test_channel_results_and_targets():
    report = load_report()
    assert report, "channel metric accuracy cannot be evaluated because the report is unreadable"
    rows = load_daily()
    target_leads = {"Paid Search": 650, "Paid Social": 330, "Email": 400, "Organic Search": 360}
    efficiency_targets = {
        "Paid Search": [(300, 0.05), (16.0, 0.02)],
        "Paid Social": [(700, 0.05), (5.3, 0.02)],
    }
    failures = []
    for channel, aliases in CHANNEL_ALIASES.items():
        july, august = aggregate(rows, "2026-07", channel), aggregate(rows, "2026-08", channel)
        expected = [
            (july["leads"], 0.1),
            (august["leads"], 0.1),
            (change(august["leads"], july["leads"]), 0.15),
            (august["mqls"], 0.1),
            (august["new_customers"], 0.1),
            (target_leads[channel], 0.1),
        ]
        if august["spend_usd"]:
            expected.extend([
                (august["spend_usd"], 1.0),
                (august["cpa"], 0.05),
                (august["roas"], 0.02),
            ])
            expected.extend(efficiency_targets[channel])
        fragments = fragments_with_alias(report, aliases, radius=1)
        joined = "\n".join(fragments)
        normalized = clean(joined)
        if channel == "Paid Social":
            outcome_ok = any(cue in normalized for cue in ("miss", "off track", "below target", "under target", "over ceiling", "✗"))
        else:
            outcome_ok = any(cue in normalized for cue in ("met", "on track", "beat", "exceed", "above target", "pass", "✓"))
        if not all(close_to_any(joined, value, tolerance) for value, tolerance in expected) or not outcome_ok:
            failures.append(channel)
    assert not failures, "channel rows/sections do not reconcile to source data and targets for: " + ", ".join(failures)


def test_attribution_gap_is_quantified():
    report = load_report()
    assert report, "attribution handling cannot be evaluated because the report is unreadable"
    rows = load_daily()
    social = [row for row in rows if row["date"].startswith("2026-08") and row["channel"] == "Paid Social"]
    reported_revenue = sum(row["attributed_revenue_usd"] for row in social)
    adjusted_revenue = sum(row["attributed_revenue_usd"] / row["revenue_tracking_coverage"] for row in social)
    spend = sum(row["spend_usd"] for row in social)
    reported_roas, adjusted_roas = reported_revenue / spend, adjusted_revenue / spend
    social_fragments = fragments_with_alias(report, CHANNEL_ALIASES["Paid Social"], radius=2)
    joined = "\n".join(social_fragments)
    normalized = clean(joined)
    sentences = [segment for segment in re.split(r"(?<=[.!?])\s+|\n+", joined) if segment.strip()]
    reported_association = any(
        any(cue in clean(segment) for cue in ("reported", "observed", "captured"))
        and close_to_any(segment, reported_revenue, 1.0)
        and close_to_any(segment, reported_roas, 0.02)
        for segment in sentences
    )
    estimate_association = any(
        any(cue in clean(segment) for cue in ("adjusted", "estimated", "estimate", "directional"))
        and close_to_any(segment, adjusted_revenue, 1.0)
        and close_to_any(segment, adjusted_roas, 0.02)
        for segment in sentences
    )
    facts_ok = all([
        close_to_any(joined, 60.0, 0.05),
        close_to_any(joined, reported_revenue, 1.0),
        close_to_any(joined, adjusted_revenue, 1.0),
        close_to_any(joined, reported_roas, 0.02),
        close_to_any(joined, adjusted_roas, 0.02),
        close_to_any(joined, 5.3, 0.02),
    ])
    observed_cue = any(term in normalized for term in ("reported", "observed", "captured"))
    estimate_cue = any(term in normalized for term in ("adjusted", "estimated", "estimate", "directional"))
    assert facts_ok and observed_cue and estimate_cue and reported_association and estimate_association, (
        "Paid Social must quantify the 60% gap and distinguish reported $149,520 / 5.11x from "
        "coverage-adjusted $159,600 / 5.45x against the 5.30x target"
    )
