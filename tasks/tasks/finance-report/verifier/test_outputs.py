from __future__ import annotations

import csv
import html as html_lib
import os
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

import pytest


RESULTS = Path(os.environ.get("RESULTS_DIR", "/root/results"))
DATA = Path(os.environ.get("DATA_DIR", "/root/data"))
REPORT = RESULTS / "index.html"


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: Counter[str] = Counter()
        self.attrs: list[tuple[str, dict[str, str]]] = []
        self.text_chunks: list[str] = []
        self.rows: list[str] = []
        self._row_chunks: list[str] | None = None
        self._excluded_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.tags[tag] += 1
        self.attrs.append((tag, {key.lower(): value or "" for key, value in attrs}))
        if tag in {"style", "script"}:
            self._excluded_depth += 1
        if tag == "tr":
            self._row_chunks = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "tr" and self._row_chunks is not None:
            self.rows.append(normalize_text(" ".join(self._row_chunks)))
            self._row_chunks = None
        if tag in {"style", "script"} and self._excluded_depth:
            self._excluded_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._excluded_depth and data.strip():
            self.text_chunks.append(data)
            if self._row_chunks is not None:
                self._row_chunks.append(data)


def normalize_text(value: str) -> str:
    value = html_lib.unescape(value).replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip().lower()


@pytest.fixture(scope="session")
def report() -> dict:
    assert REPORT.is_file(), "index.html is missing; the requested management report cannot be reviewed"
    raw = REPORT.read_text(encoding="utf-8")
    assert raw.strip(), "index.html is empty"
    parser = ReportParser()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:
        pytest.fail(f"index.html cannot be parsed as HTML: {exc}")
    return {
        "raw": raw,
        "raw_norm": normalize_text(raw),
        "text": normalize_text(" ".join(parser.text_chunks)),
        "rows": parser.rows,
        "tags": parser.tags,
        "attrs": parser.attrs,
    }


def ledger_truth() -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]], dict[str, int]]:
    quarterly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    monthly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    q3_costs: dict[str, int] = defaultdict(int)
    with (DATA / "ledger.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["include_in_report"].strip().lower() != "yes":
                continue
            value = int(row["amount_usd"])
            period = row["recognition_date"][:7]
            group = row["account_group"]
            quarterly[row["reporting_quarter"]][group] += value
            monthly[period][group] += value
            if row["reporting_quarter"] == "Q3 FY2025" and group == "Operating Expense":
                q3_costs[row["cost_center"]] -= value
    return quarterly, monthly, q3_costs


def amounts(text: str) -> list[float]:
    patterns = [
        re.compile(
            r"(?P<prefix>[\(\-]?)\s*(?:us\$|\$|usd\s*)\s*(?P<postsign>-?)\s*(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>m(?:illion)?|k|thousand)?\s*(?P<suffix>\)?)",
            re.I,
        ),
        re.compile(
            r"(?P<prefix>[\(\-]?)\s*(?P<postsign>-?)\s*(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>m(?:illion)?|k|thousand)?\s*usd\s*(?P<suffix>\)?)",
            re.I,
        ),
    ]
    values = []
    normalized = text.replace("−", "-")
    for pattern in patterns:
        for match in pattern.finditer(normalized):
            number = float(match.group("number").replace(",", ""))
            unit = (match.group("unit") or "").lower()
            if unit.startswith("m"):
                number *= 1_000_000
            elif unit in {"k", "thousand"}:
                number *= 1_000
            if match.group("prefix") in {"(", "-"} or match.group("postsign") == "-" or match.group("suffix") == ")":
                number *= -1
            values.append(number)
    return values


def has_amount(text: str, expected: float, *, relative_tolerance: float = 0.006, absolute_tolerance: float = 1100) -> bool:
    tolerance = max(abs(expected) * relative_tolerance, absolute_tolerance)
    return any(abs(value - expected) <= tolerance for value in amounts(text))


def numbers(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", text)]


def windows(text: str, aliases: list[str], radius: int = 260) -> list[str]:
    found = []
    for alias in aliases:
        for match in re.finditer(re.escape(normalize_text(alias)), text):
            found.append(text[max(0, match.start() - radius):match.end() + radius])
    return found


def row_or_window(report: dict, aliases: list[str]) -> str:
    for row in report["rows"]:
        if any(normalize_text(alias) in row for alias in aliases):
            return row
    candidates = windows(report["text"], aliases, 220)
    return " ".join(candidates)


def percent_near(report: dict, aliases: list[str], expected: float, tolerance: float = 0.2) -> bool:
    for window in windows(report["text"], aliases, 180):
        for value in re.findall(r"(-?\d+(?:\.\d+)?)\s*%", window):
            if abs(float(value) - expected) <= tolerance:
                return True
    return False


def test_artifact_usability(report: dict) -> None:
    tags = report["tags"]
    assert tags["html"] and tags["head"] and tags["body"], "index.html lacks a usable HTML document structure"
    assert tags["style"] >= 1, "the report has no inline styling and is not a usable self-contained finance page"
    external = []
    for tag, attrs in report["attrs"]:
        value = attrs.get("src") or attrs.get("href")
        if value and not value.startswith(("#", "data:")):
            external.append((tag, value))
    assert not external, (
        f"the report depends on external resources {external}; it must remain usable offline"
    )
    text = report["text"]
    assert "alder peak systems" in text and "q3 fy2025" in text, "company or reporting period is not clearly identified"
    requested = [
        ["executive", "kpi", "snapshot"],
        ["trailing 12", "12-month", "revenue trend"],
        ["operating cost", "cost breakdown", "operating expenses by", "expenses by cost center"],
        ["p&l", "profit and loss", "income statement"],
        ["top accounts", "top customers", "top 5 accounts", "accounts by"],
        ["q4 outlook", "q4 forecast", "outlook"],
    ]
    missing = [aliases for aliases in requested if not any(normalize_text(alias) in text for alias in aliases)]
    if ["executive", "kpi", "snapshot"] in missing:
        kpi_markup = any(
            "kpi" in (attrs.get("class", "") + " " + attrs.get("aria-label", "")).lower()
            for _, attrs in report["attrs"]
        )
        if kpi_markup and all(term in text for term in ("revenue", "gross margin", "runway")):
            missing.remove(["executive", "kpi", "snapshot"])
    assert not missing, f"requested report areas are not discoverable: {missing}"


@pytest.mark.parametrize(
    ("aliases", "kind", "expected"),
    [
        (["revenue"], "amount", 2_695_000),
        (["net new mrr"], "amount", 85_000),
        (["gross margin"], "percent", 76.6),
        (["cash runway", "runway"], "number", 19.6),
    ],
)
def test_kpi_values(report: dict, aliases: list[str], kind: str, expected: float) -> None:
    full_text = report["text"]
    analysis_starts = [
        full_text.find(anchor)
        for anchor in ("trailing 12", "12-month revenue", "revenue & operating cost", "revenue and operating cost")
        if full_text.find(anchor) >= 0
    ]
    kpi_text = full_text[:min(analysis_starts)] if analysis_starts else full_text[: max(600, len(full_text) // 3)]
    candidates = windows(kpi_text, aliases, 145)
    assert candidates, f"KPI label not found: {aliases[0]}"
    if kind == "amount":
        ok = any(has_amount(window, expected) for window in candidates)
    elif kind == "percent":
        ok = any(any(abs(value - expected) <= 0.15 for value in numbers(window)) for window in candidates)
    else:
        ok = any(any(abs(value - expected) <= 0.15 for value in numbers(window)) for window in candidates)
    assert ok, f"{aliases[0]} KPI does not show the value derived from reportable source data"


@pytest.mark.parametrize(
    ("aliases", "current", "prior"),
    [
        (["revenue"], 2_695_000, 2_445_000),
        (["cost of revenue"], -630_000, -585_000),
        (["gross profit"], 2_065_000, 1_860_000),
        (["operating expenses", "operating expense", "opex"], -2_970_000, -2_940_000),
        (["operating loss", "operating income", "net"], -905_000, -1_080_000),
    ],
)
def test_pnl_values(report: dict, aliases: list[str], current: int, prior: int) -> None:
    row = row_or_window(report, aliases)
    assert row, f"P&L line not found: {aliases[0]}"
    assert has_amount(row, current), f"{aliases[0]} does not show the correct Q3 value"
    assert has_amount(row, prior), f"{aliases[0]} does not show the correct Q2 comparison"


def test_revenue_trend_fidelity(report: dict) -> None:
    _, monthly, _ = ledger_truth()
    expected = [(month, values["Revenue"]) for month, values in sorted(monthly.items())]
    raw = report["raw_norm"]
    text = report["text"]
    assert any(token in raw for token in ("<svg", "<canvas", "role=\"img\"", "role='img'", "chart", "plot")), (
        "the trailing revenue view has no identifiable visual encoding"
    )
    assert any(alias in raw for alias in ("oct 24", "october 2024", "2024-10")), "the revenue view does not establish the TTM start month"
    assert any(alias in raw for alias in ("sep 25", "september 2025", "2025-09")), "the revenue view does not establish the TTM end month"
    represented = sum(has_amount(raw, value) for _, value in expected)
    assert represented >= 10, (
        f"only {represented} of 12 source revenue points are traceable in the HTML; the plotted series could materially differ from the ledger"
    )
    assert has_amount(text + " " + raw, 640_000) and has_amount(text + " " + raw, 930_000), "TTM revenue endpoints are not traceable"


def test_operating_cost_breakdown(report: dict) -> None:
    _, _, q3_costs = ledger_truth()
    aliases = {
        "Research & Development": ["research & development", "research and development", "r&d"],
        "Sales & Marketing": ["sales & marketing", "sales and marketing", "s&m"],
        "General & Administrative": ["general & administrative", "general and administrative", "g&a"],
        "Customer Success": ["customer success", "cs"],
        "People & Workplace": ["people & workplace", "people and workplace", "people", "workplace"],
    }
    missing = []
    wrong = []
    for name, value in q3_costs.items():
        candidate = row_or_window(report, aliases[name])
        if not candidate:
            missing.append(name)
        elif not has_amount(candidate, value):
            wrong.append(name)
    assert not missing, f"Q3 operating-cost categories are missing: {missing}"
    assert not wrong, f"Q3 operating-cost totals disagree with reportable ledger rows: {wrong}"


@pytest.mark.parametrize(
    ("name", "arr", "plan", "status"),
    [
        ("Juniper Freight", 600_000, "Enterprise", "Expanded"),
        ("Mosaic Healthworks", 528_000, "Enterprise", "Renewed"),
        ("Vector Forge", 504_000, "Enterprise", "In renewal"),
        ("Harbor & Pine", 402_000, "Enterprise", "At risk"),
        ("Lumen Foods", 378_000, "Enterprise", "Renewed"),
    ],
)
def test_top_account_details(report: dict, name: str, arr: int, plan: str, status: str) -> None:
    context = row_or_window(report, [name])
    assert context, f"top account {name} is absent"
    assert has_amount(context, arr), f"{name} has an incorrect or missing Q3 ending ARR"
    assert normalize_text(plan) in context, f"{name} has an incorrect or missing plan"
    assert normalize_text(status) in context, f"{name} has an incorrect or missing Q3 status"


def test_top_account_scope(report: dict) -> None:
    text = report["text"]
    assert "internal demo tenant" not in text, "the excluded internal tenant appears as a customer account"
    assert "west robotics" not in text, "a sixth-ranked account is included even though the supplied definition calls for the top five"
