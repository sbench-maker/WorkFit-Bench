from __future__ import annotations

import csv
import os
import re
from datetime import date, timedelta
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_PATH", "/root/results/metrics_dashboard.md"))
CURRENT = (date(2026, 8, 24), date(2026, 8, 30))
PRIOR = (date(2026, 8, 17), date(2026, 8, 23))


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def selected(rows: list[dict[str, str]], period: tuple[date, date]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if period[0] <= date.fromisoformat(row["date"]) <= period[1]
        and row.get("data_complete", "true").lower() == "true"
    ]


def expected_values() -> dict[str, tuple[float, ...]]:
    usage = read_csv("daily_product_usage.csv")
    health = read_csv("daily_service_health.csv")
    mrr = read_csv("daily_mrr.csv")
    roster = read_csv("account_roster.csv")

    def usage_for(period: tuple[date, date]) -> dict[str, float]:
        rows = selected(usage, period)
        production = sum(int(r["production_runs"]) for r in rows)
        successes = sum(int(r["successful_runs"]) for r in rows)
        template = sum(int(r["template_runs"]) for r in rows)
        published = sum(int(r["workflows_published"]) for r in rows)
        by_account: dict[str, int] = {}
        for row in rows:
            by_account[row["account_id"]] = by_account.get(row["account_id"], 0) + int(
                row["production_runs"]
            )
        active = sum(value >= 10 for value in by_account.values())
        return {
            "successes": successes,
            "success_rate": successes / production * 100,
            "active": active,
            "published_per_active": published / active,
            "template_rate": template / production * 100,
        }

    def scheduler_for(period: tuple[date, date]) -> dict[str, float]:
        rows = [r for r in selected(health, period) if r["service"] == "scheduler"]
        return {
            "error_rate": sum(int(r["error_count"]) for r in rows)
            / sum(int(r["request_count"]) for r in rows)
            * 100,
            "worst_p95": max(int(r["p95_latency_ms"]) for r in rows),
        }

    def mrr_for(period: tuple[date, date]) -> int:
        end = period[1].isoformat()
        return sum(int(r["mrr_usd"]) for r in mrr if r["date"] == end and r["data_complete"] == "true")

    def churn_for(period: tuple[date, date]) -> float:
        start, end = period
        denominator = sum(
            r["date"] == (start - timedelta(days=1)).isoformat()
            and r["active_subscription"] == "true"
            for r in mrr
        )
        numerator = sum(
            bool(r["churn_effective_date"])
            and start <= date.fromisoformat(r["churn_effective_date"]) <= end
            for r in roster
        )
        return numerator / denominator * 100

    cur, prev = usage_for(CURRENT), usage_for(PRIOR)
    cur_sched, prev_sched = scheduler_for(CURRENT), scheduler_for(PRIOR)
    cur_mrr, prev_mrr = mrr_for(CURRENT), mrr_for(PRIOR)
    return {
        "successful_runs": (
            cur["successes"],
            prev["successes"],
            (cur["successes"] / prev["successes"] - 1) * 100,
        ),
        "success_rate": (
            cur["success_rate"],
            prev["success_rate"],
            cur["success_rate"] - prev["success_rate"],
        ),
        "active_accounts": (cur["active"], prev["active"]),
        "template_rate": (cur["template_rate"], prev["template_rate"]),
        "scheduler_error": (
            cur_sched["error_rate"],
            prev_sched["error_rate"],
        ),
        "scheduler_p95": (cur_sched["worst_p95"], prev_sched["worst_p95"]),
        "mrr": (cur_mrr, prev_mrr, (cur_mrr / prev_mrr - 1) * 100),
        "churn": (churn_for(CURRENT), churn_for(PRIOR)),
    }


def artifact_text() -> str:
    assert OUTPUT.is_file(), (
        "The requested /root/results/metrics_dashboard.md artifact is missing; "
        "the product team has no dashboard specification to review."
    )
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        pytest.fail(f"The dashboard specification is not readable UTF-8 Markdown: {exc}")


def normalize(text: str) -> str:
    return (
        text.lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("％", "%")
        .replace("$", "$ ")
    )


def contexts(text: str, aliases: tuple[str, ...]) -> str:
    lines = text.splitlines()
    hits: list[str] = []
    for index, line in enumerate(lines):
        lowered = normalize(line)
        if any(alias in lowered for alias in aliases):
            hits.append(line)
            # Support a metric heading followed by a wrapped definition, while keeping
            # adjacent Markdown table rows from donating unrelated values or routing.
            if len(line.strip()) < 80:
                hits.extend(lines[index + 1 : min(len(lines), index + 3)])
    return normalize("\n".join(hits))


NUMBER_RE = re.compile(
    r"(?<![a-z0-9])([-+]?\d[\d,]*(?:\.\d+)?)\s*(k|thousand|s|sec|secs|second|seconds)?\b",
    re.IGNORECASE,
)


def numeric_values(text: str) -> list[float]:
    values: list[float] = []
    for match in NUMBER_RE.finditer(text):
        value = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix in {"k", "thousand"}:
            value *= 1000
        elif suffix in {"s", "sec", "secs", "second", "seconds"} and abs(value) < 100:
            value *= 1000
        values.append(value)
    return values


def has_number(text: str, expected: float) -> bool:
    tolerance = 0.51 if abs(expected) >= 100 else 0.16
    return any(abs(actual - expected) <= tolerance for actual in numeric_values(text))


def has_response_time(text: str, expected_minutes: int) -> bool:
    if has_number(text, expected_minutes):
        return True
    if expected_minutes == 1440:
        return any(
            phrase in text
            for phrase in (
                "1 day",
                "one day",
                "1 business day",
                "one business day",
                "24 h",
                "24 hour",
            )
        )
    return False


def assert_metric_values(
    text: str,
    aliases: tuple[str, ...],
    expected: tuple[float, ...],
    impact: str,
) -> None:
    context = contexts(text, aliases)
    assert context, f"No dashboard entry could be located for {aliases[0]}; {impact}."
    missing = [value for value in expected if not has_number(context, value)]
    assert not missing, (
        f"The {aliases[0]} entry does not expose source-supported current/comparison values "
        f"near {missing}; {impact}. Context inspected: {context[:900]!r}"
    )
    if len(set(expected)) < len(expected):
        comparison_cues = (" vs ", "prior", "previous", "comparison", "unchanged", "both weeks", "flat", "0 (flat)")
        assert any(cue in context for cue in comparison_cues), (
            f"The {aliases[0]} value is unchanged, but the artifact does not make the "
            f"current-to-comparison relationship clear; {impact}."
        )


@pytest.mark.parametrize(
    "metric_key,aliases",
    [
        ("successful_runs", ("weekly successful production runs", "successful production runs")),
        ("success_rate", ("production run success rate", "run success rate")),
        ("active_accounts", ("weekly active accounts", "active accounts")),
        ("template_rate", ("template adoption rate", "template adoption")),
    ],
)
def test_core_weekly_comparisons(metric_key: str, aliases: tuple[str, ...]):
    """Product metrics use the complete weeks and aggregation rules in the local notes."""
    values = expected_values()[metric_key]
    assert_metric_values(
        artifact_text(),
        aliases,
        values,
        "a wrong weekly product comparison can send the team toward the wrong lever",
    )


@pytest.mark.parametrize(
    "metric_key,aliases",
    [
        ("scheduler_error", ("scheduler error rate", "scheduler errors")),
        ("scheduler_p95", ("scheduler worst daily p95", "scheduler p95", "scheduler latency")),
        ("mrr", ("monthly recurring revenue", "mrr")),
        ("churn", ("weekly gross logo churn rate", "logo churn rate", "logo churn")),
    ],
)
def test_service_and_business_comparisons(metric_key: str, aliases: tuple[str, ...]):
    """Important reliability and business comparisons reconcile with the frozen exports."""
    assert_metric_values(
        artifact_text(),
        aliases,
        expected_values()[metric_key],
        "an inaccurate guardrail can hide an incident or misstate business impact",
    )


def test_partial_day_is_not_used():
    """The early August 31 export is disclosed and excluded from completed-period decisions."""
    text = normalize(artifact_text())
    date_present = bool(
        re.search(r"(?:2026[-/]0?8[-/]31|aug(?:ust)?\s+31(?:st)?(?:,?\s+2026)?)", text)
    )
    partial_present = any(term in text for term in ("partial", "incomplete", "not complete"))
    exclusion_present = any(
        term in text
        for term in (
            "exclude",
            "excluded",
            "omit",
            "ignored",
            "not use",
            "do not use",
            "not count",
            "do not count",
            "not alert",
            "do not alert",
        )
    )
    assert date_present and partial_present and exclusion_present, (
        "The artifact must identify August 31 as partial and keep it out of complete-week trends/alerts; "
        "otherwise a routine early export looks like a severe decline."
    )


@pytest.mark.parametrize(
    "aliases,severity_terms,owner_terms,channel,response",
    [
        (
            ("production run success rate", "run success rate"),
            ("critical", "sev-1", "severity 1", "p1"),
            ("workflow reliability",),
            "#ops-alerts",
            30,
        ),
        (
            ("scheduler worst daily p95", "scheduler p95", "scheduler latency"),
            ("critical", "sev-1", "severity 1", "p1"),
            ("sre on-call", "sre on call"),
            "#ops-alerts",
            15,
        ),
        (
            ("scheduler error rate", "scheduler errors"),
            ("warning", "warn", "sev-2", "severity 2", "p2"),
            ("sre on-call", "sre on call"),
            "#ops-alerts",
            15,
        ),
        (
            ("weekly successful production runs", "successful production runs"),
            ("warning", "warn", "sev-2", "severity 2", "p2"),
            ("product operations", "product ops"),
            "#product-alerts",
            120,
        ),
        (
            ("monthly recurring revenue", "mrr"),
            ("critical", "sev-1", "severity 1", "p1"),
            ("revenue operations", "revenue ops"),
            "#business-metrics",
            1440,
        ),
        (
            ("weekly gross logo churn rate", "logo churn rate", "logo churn"),
            ("warning", "warn"),
            ("customer success operations", "customer success ops"),
            "#business-metrics",
            1440,
        ),
    ],
)
def test_breached_alerts_are_actionable(
    aliases: tuple[str, ...],
    severity_terms: tuple[str, ...],
    owner_terms: tuple[str, ...],
    channel: str,
    response: int,
):
    """Breached thresholds are routed with the frozen severity and response contract."""
    context = contexts(artifact_text(), aliases)
    assert context, f"No actionable alert entry was found for {aliases[0]}."
    assert any(term in context for term in severity_terms), (
        f"{aliases[0]} is assigned the wrong or no current severity; the escalation queue would be misleading."
    )
    assert any(term in context for term in owner_terms), (
        f"{aliases[0]} lacks its accountable owner; the alert may go unacknowledged."
    )
    assert channel in context, f"{aliases[0]} is not routed to {channel}, contrary to the local alert contract."
    assert has_response_time(context, response), (
        f"{aliases[0]} omits the {response}-minute response expectation; responders cannot prioritize it."
    )
