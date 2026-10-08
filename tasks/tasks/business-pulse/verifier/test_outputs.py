from __future__ import annotations

import csv
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

import pytest


DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/business_pulse.md"))
if not DATA.is_absolute() or not OUTPUT.is_absolute():
    raise ValueError("Verifier data and output paths must be absolute")
OPEN_STAGES = {"discovery", "qualification", "proposal", "negotiation"}


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def output_text() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("–", "-").replace("—", "-"))


def lines_for(text: str, labels: tuple[str, ...]) -> list[str]:
    wanted = tuple(normalized(label) for label in labels)
    return [line for line in text.splitlines() if any(label in normalized(line) for label in wanted)]


MONEY_RE = re.compile(
    r"(?:\$\s*(?P<dollar>[\d,]+(?:\.\d+)?)\s*(?P<suffix>[kKmM])?|(?P<plain>[\d,]+(?:\.\d+)?)\s*(?:USD|usd))"
)


def money_values(fragment: str) -> list[float]:
    values = []
    for match in MONEY_RE.finditer(fragment):
        raw = match.group("dollar") or match.group("plain")
        value = float(raw.replace(",", ""))
        suffix = (match.group("suffix") or "").casefold()
        if suffix == "k":
            value *= 1_000
        elif suffix == "m":
            value *= 1_000_000
        values.append(value)
    return values


def has_money(fragment: str, expected: float, rel_tol: float = 0.002) -> bool:
    tolerance = max(5.0, abs(expected) * rel_tol)
    return any(abs(value - expected) <= tolerance for value in money_values(fragment))


def assert_labeled_money(text: str, labels: tuple[str, ...], expected: float, message: str) -> str:
    candidates = lines_for(text, labels)
    assert candidates, f"No line identifies {message}; the owner cannot trace that requested metric."
    assert any(has_money(line, expected) for line in candidates), (
        f"{message} is not reported as {expected:,.2f} (allowing display rounding); "
        "the pulse would give the owner a wrong operating figure."
    )
    return " ".join(candidates)


def assert_change_direction(fragment: str, direction: str, message: str) -> None:
    flat = normalized(fragment)
    if direction == "down":
        found = "▼" in fragment or bool(re.search(r"\b(down|decrease|decline|fell|lower)\b", flat)) or bool(re.search(r"-\s*\d", fragment))
    else:
        found = "▲" in fragment or bool(re.search(r"\b(up|increase|growth|grew|higher)\b", flat)) or bool(re.search(r"\+\s*\d", fragment))
    assert found, f"{message} has the wrong or missing change direction."


def percentages(fragment: str) -> list[float]:
    return [float(value) for value in re.findall(r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*%", fragment)]


def assert_percent(fragment: str, expected_magnitude: float, message: str) -> None:
    assert any(abs(abs(value) - abs(expected_magnitude)) <= 0.25 for value in percentages(fragment)), (
        f"{message} is missing or materially wrong; expected about {expected_magnitude:.1f}%."
    )


def source_truth() -> dict:
    snapshot = json.loads((DATA / "connector_snapshot.json").read_text(encoding="utf-8"))
    summary = json.loads((DATA / "quickbooks_summary.json").read_text(encoding="utf-8"))
    prefs = json.loads((DATA / "owner_preferences.json").read_text(encoding="utf-8"))
    invoices = read_csv("quickbooks_invoices.csv")
    payments = read_csv("payment_transactions.csv")
    deals = read_csv("hubspot_deals.csv")
    report_date = date.fromisoformat(snapshot["report_date"])
    current_start = date.fromisoformat(snapshot["current_7_day_window"]["start"])
    prior_start = date.fromisoformat(snapshot["prior_7_day_window"]["start"])
    prior_end = date.fromisoformat(snapshot["prior_7_day_window"]["end"])

    open_invoices = [row for row in invoices if row["status"] == "open"]
    aging = {"0-30": 0.0, "31-60": 0.0, "61+": 0.0}
    overdue = []
    for row in open_invoices:
        days = (report_date - date.fromisoformat(row["due_date"])).days
        amount = float(row["amount_usd"])
        bucket = "0-30" if days <= 30 else "31-60" if days <= 60 else "61+"
        aging[bucket] += amount
        if days > prefs["receivable_attention_days_past_due"]:
            overdue.append({**row, "days": days})

    def local_day(row: dict[str, str]) -> date:
        return datetime.fromisoformat(row["transaction_at"]).date()

    current_completed = [row for row in payments if row["status"] == "completed" and current_start <= local_day(row) <= report_date]
    prior_completed = [row for row in payments if row["status"] == "completed" and prior_start <= local_day(row) <= prior_end]
    current_settlements = sum(float(row["amount_usd"]) for row in current_completed)
    prior_settlements = sum(float(row["amount_usd"]) for row in prior_completed)
    payment_risks = [
        row for row in payments
        if row["status"] in {"failed", "pending"}
        and float(row["amount_usd"]) >= prefs["material_failed_or_pending_payment_usd"]
        and current_start <= local_day(row) <= report_date
    ]

    open_deals = [row for row in deals if row["stage"] in OPEN_STAGES]
    weighted = sum(float(row["amount_usd"]) * float(row["probability"]) for row in open_deals)
    prior_weighted = sum(
        float(row["previous_week_amount_usd"]) * float(row["previous_week_probability"])
        for row in deals
        if row["previous_week_stage"] in OPEN_STAGES and row["previous_week_amount_usd"]
    )
    deal_risks = [
        row for row in open_deals
        if (report_date - date.fromisoformat(row["last_activity_date"])).days >= prefs["stale_open_deal_days_without_activity"]
        or date.fromisoformat(row["close_date"]) < report_date
    ]
    closed_won = [row for row in deals if row["stage"] == "closed-won" and current_start <= date.fromisoformat(row["close_date"]) <= report_date]
    new_deals = [row for row in deals if current_start <= date.fromisoformat(row["created_date"]) <= report_date]
    return {
        "snapshot": snapshot,
        "summary": summary,
        "prefs": prefs,
        "report_date": report_date,
        "open_invoices": open_invoices,
        "aging": aging,
        "ar_total": sum(float(row["amount_usd"]) for row in open_invoices),
        "overdue": overdue,
        "current_settlements": current_settlements,
        "prior_settlements": prior_settlements,
        "payment_risks": payment_risks,
        "weighted": weighted,
        "prior_weighted": prior_weighted,
        "coverage": weighted / prefs["monthly_revenue_target_usd"],
        "closed_won": closed_won,
        "new_deals": new_deals,
        "deal_risks": deal_risks,
    }


TRUTH = source_truth()


def test_artifact_usability_and_requested_scope():
    text = output_text()
    assert OUTPUT.is_file() and text.strip(), "The requested Markdown pulse is missing or unreadable."
    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    assert 180 <= word_count <= 1800, (
        f"The pulse contains {word_count} words; it is too sparse to cover the request or too long for a one-page owner check-in."
    )
    flat = normalized(text)
    concepts = {
        "overall health": ("overall", "business health", "health summary"),
        "cash and receivables": ("cash", "receivable", "accounts receivable", "ar aging"),
        "sales": ("sales", "settlement", "payments"),
        "pipeline": ("pipeline", "deals"),
        "commitments": ("this week", "commitment", "calendar", "upcoming"),
        "single priority": ("#1 priority", "top priority", "most important action", "action today"),
        "source availability": ("sources unavailable", "unavailable sources", "data availability", "source status"),
    }
    missing = [name for name, aliases in concepts.items() if not any(alias in flat for alias in aliases)]
    assert not missing, f"The owner pulse omits requested decision areas: {missing}."


def test_finance_metrics_and_changes():
    text = output_text()
    summary = TRUTH["summary"]
    cash_lines = assert_labeled_money(text, ("cash balance", "cash position", "cash on hand"), summary["cash_balance_usd"], "current cash balance")
    assert has_money(cash_lines, abs(summary["cash_balance_usd"] - summary["cash_balance_prior_week_usd"])), "The cash line lacks the correct week-over-week delta."
    assert_change_direction(cash_lines, "down", "Cash WoW delta")

    mtd_lines = assert_labeled_money(text, ("mtd revenue", "month-to-date revenue", "revenue mtd"), summary["mtd_revenue_usd"], "month-to-date revenue")
    assert has_money(mtd_lines, summary["prior_month_comparable_mtd_revenue_usd"]), "The MTD line lacks the comparable prior-period baseline."
    mtd_change = (summary["mtd_revenue_usd"] / summary["prior_month_comparable_mtd_revenue_usd"] - 1) * 100
    assert_percent(mtd_lines, mtd_change, "MTD revenue change")
    assert_change_direction(mtd_lines, "down", "MTD revenue change")

    ar_lines = assert_labeled_money(text, ("outstanding ar", "accounts receivable", "outstanding receivables", "ar is"), TRUTH["ar_total"], "outstanding receivables")
    assert str(len(TRUTH["open_invoices"])) in ar_lines, "The open-invoice count does not reconcile with the receivables total."
    for bucket, aliases in {
        "0-30": ("0-30", "0 to 30"),
        "31-60": ("31-60", "31 to 60"),
        "61+": ("61+", "61 plus", "over 60"),
    }.items():
        assert_labeled_money(text, aliases, TRUTH["aging"][bucket], f"AR aging bucket {bucket}")


def test_sales_metrics_and_changes():
    text = output_text()
    sales_lines = assert_labeled_money(text, ("7-day settlements", "7 day settlements", "weekly settlements", "settled in 7 days"), TRUTH["current_settlements"], "current seven-day settlements")
    assert has_money(sales_lines, TRUTH["prior_settlements"]), "The sales comparison omits the prior seven-day baseline."
    expected_change = (TRUTH["current_settlements"] / TRUTH["prior_settlements"] - 1) * 100
    assert_percent(sales_lines, expected_change, "seven-day settlement change")
    assert_change_direction(sales_lines, "up", "Seven-day settlement change")


def test_pipeline_metrics_and_movement():
    text = output_text()
    pipeline_lines = assert_labeled_money(text, ("weighted pipeline",), TRUTH["weighted"], "weighted pipeline")
    assert has_money(pipeline_lines, abs(TRUTH["weighted"] - TRUTH["prior_weighted"])), "Weighted pipeline lacks the correct WoW dollar change."
    assert_change_direction(pipeline_lines, "down", "Weighted pipeline WoW change")
    coverage_lines = " ".join(lines_for(text, ("coverage", "times target", "x target")))
    coverage_values = [float(value) for value in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*x", coverage_lines, flags=re.I)]
    assert any(abs(value - TRUTH["coverage"]) <= 0.06 for value in coverage_values), "Pipeline coverage versus the configured monthly target is wrong or missing."
    won_total = sum(float(row["amount_usd"]) for row in TRUTH["closed_won"])
    won_lines = assert_labeled_money(text, ("closed-won", "closed won", "won this week"), won_total, "current-window closed-won total")
    assert str(len(TRUTH["closed_won"])) in won_lines, "Closed-won deal count does not match the current window."
    new_total = sum(float(row["amount_usd"]) for row in TRUTH["new_deals"])
    new_lines = assert_labeled_money(text, ("new deals", "deals created"), new_total, "new-deal total")
    assert str(len(TRUTH["new_deals"])) in new_lines, "New-deal count does not match the current window."


RISK_CASES = []
for row in TRUTH["overdue"]:
    RISK_CASES.append(pytest.param("invoice", row["customer"], row["invoice_id"], float(row["amount_usd"]), str(row["days"]), id=row["invoice_id"]))
for row in TRUTH["payment_risks"]:
    RISK_CASES.append(pytest.param("payment", row["customer"], row["payment_id"], float(row["amount_usd"]), row["status"], id=row["payment_id"]))
for row in TRUTH["deal_risks"]:
    reason = "slip" if date.fromisoformat(row["close_date"]) < TRUTH["report_date"] else "stal"
    RISK_CASES.append(pytest.param("deal", row["deal_name"], row["deal_id"], float(row["amount_usd"]), reason, id=row["deal_id"]))


@pytest.mark.parametrize("kind,name,record_id,amount,reason", RISK_CASES)
def test_material_risk_coverage(kind: str, name: str, record_id: str, amount: float, reason: str):
    text = output_text()
    relevant_lines = [line for line in text.splitlines() if normalized(name) in normalized(line) or normalized(record_id) in normalized(line)]
    assert relevant_lines, f"Material {kind} {record_id} ({name}) is absent, so the owner could miss a configured attention item."
    evidence = " ".join(relevant_lines)
    assert has_money(evidence, amount), f"{record_id} is named without its material amount, weakening traceability and prioritization."
    assert normalized(reason) in normalized(evidence), f"{record_id} is present but its {reason} reason/status is not explained."


def test_source_availability_and_signal_filtering():
    text = output_text()
    flat = normalized(text)
    snapshot = TRUTH["snapshot"]
    for row in snapshot["sources"]:
        assert normalized(row["name"]) in flat, f"Source status for {row['name']} is not disclosed."
        if row["status"] != "available":
            name = re.escape(row["name"])
            reason_terms = ("unavailable", "not connected", "auth", "no export")
            nearby = [line for line in text.splitlines() if re.search(name, line, flags=re.I)]
            assert any(any(term in normalized(line) for term in reason_terms) for line in nearby), f"{row['name']} is unavailable in the snapshot but is not honestly labeled as such."
    pulled_lines = lines_for(text, ("sources pulled", "data sources used", "available sources"))
    assert pulled_lines, "The report does not distinguish sources used from sources unavailable."
    assert all("gmail" not in normalized(line) for line in pulled_lines), "Gmail is falsely represented as a pulled source despite its authentication failure."
    assert "snack poll" not in flat and "pretzels or fruit" not in flat, "Routine internal noise was elevated as an urgent business signal."
