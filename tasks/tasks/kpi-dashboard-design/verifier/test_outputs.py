from __future__ import annotations

import csv
import html as html_module
import json
import math
import os
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data")).resolve()
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results")).resolve()
OUTPUT = RESULTS / "saas_kpi_dashboard.html"


METRIC_ALIASES = {
    "current_mrr": ["current mrr", "monthly recurring revenue", "closing mrr"],
    "mrr_growth_pct": ["mrr growth", "mrr change", "monthly mrr growth"],
    "logo_churn_pct": ["gross logo churn", "logo churn", "customer churn"],
    "gross_revenue_churn_pct": ["gross revenue churn", "revenue churn", "mrr churn rate"],
    "cac_usd": ["customer acquisition cost", "cac"],
    "ltv_cac_ratio": ["ltv/cac", "ltv to cac", "ltv : cac"],
    "arpa_usd": ["average revenue per account", "arpa"],
}


class DashboardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.visible_parts: list[str] = []
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.external_refs: list[str] = []
        self._ignored = 0
        self._alert_stack: list[dict | None] = []
        self.alert_blocks: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): (value or "") for key, value in attrs}
        self.tags.append((tag.lower(), values))
        for key in ("src", "href"):
            if key in values:
                self.external_refs.append(values[key].strip())
        if tag.lower() in {"script", "style"}:
            self._ignored += 1
        marker = " ".join([values.get("id", ""), values.get("class", ""), values.get("role", "")]).lower()
        if tag.lower() in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            return
        if any(word in marker for word in ("alert", "warning", "critical")):
            block = {"attrs": values, "text": []}
            self.alert_blocks.append(block)
            self._alert_stack.append(block)
        else:
            self._alert_stack.append(self._alert_stack[-1] if self._alert_stack else None)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored:
            self._ignored -= 1
        if self._alert_stack:
            self._alert_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._ignored and data.strip():
            self.visible_parts.append(data.strip())
            seen = set()
            for block in self._alert_stack:
                if block is not None and id(block) not in seen:
                    block["text"].append(data.strip())
                    seen.add(id(block))


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ground_truth() -> dict:
    customers = {row["customer_id"]: row for row in read_csv("customers.csv")}
    config = json.loads((DATA / "targets.json").read_text(encoding="utf-8"))
    snapshots = read_csv("monthly_subscription_snapshots.csv")
    spend = read_csv("acquisition_spend.csv")
    cancellations = read_csv("cancellations.csv")
    current = config["reporting_month"]
    by_month: dict[str, dict[str, float]] = defaultdict(dict)
    for row in snapshots:
        divisor = {"monthly": 1.0, "quarterly": 3.0, "annual": 12.0}[row["billing_interval"]]
        by_month[row["snapshot_month"]][row["customer_id"]] = float(row["contract_amount_usd"]) / divisor
    months = sorted(by_month)
    prior = months[months.index(current) - 1]
    cur, prev = by_month[current], by_month[prior]
    current_mrr, prior_mrr = sum(cur.values()), sum(prev.values())
    new_ids, churned_ids = set(cur) - set(prev), set(prev) - set(cur)
    common = set(cur) & set(prev)
    churned_mrr = sum(prev[cid] for cid in churned_ids)
    logo_churn = len(churned_ids) / len(prev) * 100
    arpa = current_mrr / len(cur)
    current_spend = sum(float(row["spend_usd"]) for row in spend if row["month"] == current)
    new_customer_count = sum(row["signup_date"][:7] == current for row in customers.values())
    cac = current_spend / new_customer_count
    ltv = arpa / (logo_churn / 100)
    metrics = {
        "current_mrr": current_mrr,
        "mrr_growth_pct": (current_mrr - prior_mrr) / prior_mrr * 100,
        "logo_churn_pct": logo_churn,
        "gross_revenue_churn_pct": churned_mrr / prior_mrr * 100,
        "cac_usd": cac,
        "arpa_usd": arpa,
        "ltv_cac_ratio": ltv / cac,
    }
    bridge = {
        "opening_mrr": prior_mrr,
        "new_mrr": sum(cur[cid] for cid in new_ids),
        "expansion_mrr": sum(max(cur[cid] - prev[cid], 0) for cid in common),
        "contraction_mrr": sum(max(prev[cid] - cur[cid], 0) for cid in common),
        "churned_mrr": churned_mrr,
        "closing_mrr": current_mrr,
    }
    reasons: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "lost_mrr": 0.0})
    segments: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "lost_mrr": 0.0})
    for row in cancellations:
        cid = row["customer_id"]
        if row["status"] == "completed" and row["effective_month"] == current and cid in churned_ids:
            reasons[row["reason"]]["count"] += 1
            reasons[row["reason"]]["lost_mrr"] += prev[cid]
            segment = customers[cid]["segment"]
            segments[segment]["count"] += 1
            segments[segment]["lost_mrr"] += prev[cid]
    breached = set()
    for target in config["targets"]:
        value = metrics[target["metric"]]
        is_breach = value < target["threshold"] if target["direction"] == "min" else value > target["threshold"]
        if is_breach and target["alert_enabled"]:
            breached.add(target["metric"])
    return {
        "metrics": metrics,
        "months": {month: sum(rows.values()) for month, rows in by_month.items()},
        "bridge": bridge,
        "reasons": dict(reasons),
        "segments": dict(segments),
        "breached": breached,
        "all_targets": config["targets"],
    }


def load_dashboard() -> tuple[str, DashboardParser, str]:
    raw = OUTPUT.read_text(encoding="utf-8")
    parser = DashboardParser()
    parser.feed(raw)
    visible = re.sub(r"\s+", " ", " ".join(parser.visible_parts)).strip()
    return raw, parser, visible


def number_candidates(text: str) -> list[tuple[float, str, str]]:
    candidates = []
    pattern = re.compile(r"(?P<prefix>[$€£]?)\s*(?P<open>\()?\s*(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<close>\))?\s*(?P<suffix>%|x)?", re.I)
    for match in pattern.finditer(text):
        try:
            value = float(match.group("num").replace(",", ""))
        except ValueError:
            continue
        if match.group("open") and match.group("close"):
            value = -abs(value)
        candidates.append((value, match.group("prefix") or "", (match.group("suffix") or "").lower()))
    return candidates


def close_enough(actual: float, expected: float, kind: str) -> bool:
    tolerance = {"money": max(1.0, abs(expected) * 0.00005), "percent": 0.03, "ratio": 0.03, "count": 0.01}[kind]
    return math.isclose(actual, expected, abs_tol=tolerance)


def nearby_value(visible: str, labels: list[str], expected: float, kind: str, *, absolute: bool = False) -> bool:
    lowered = visible.lower()
    for label in labels:
        start = 0
        while True:
            pos = lowered.find(label.lower(), start)
            if pos < 0:
                break
            window = visible[max(0, pos - 45): pos + len(label) + 170]
            for value, prefix, suffix in number_candidates(window):
                if kind == "percent" and suffix != "%":
                    continue
                if kind == "ratio" and suffix != "x":
                    continue
                if kind == "money" and not prefix and abs(value) < 100:
                    continue
                left = abs(value) if absolute else value
                right = abs(expected) if absolute else expected
                if close_enough(left, right, kind):
                    return True
            start = pos + len(label)
    return False


def semantic_metrics(parser: DashboardParser) -> dict[str, float]:
    result = {}
    for _, attrs in parser.tags:
        key, raw_value = attrs.get("data-metric"), attrs.get("data-value")
        if key and raw_value:
            try:
                result[key.lower()] = float(raw_value.replace(",", ""))
            except ValueError:
                pass
    return result


def metric_present(parser: DashboardParser, visible: str, key: str, expected: float, kind: str) -> bool:
    semantic = semantic_metrics(parser)
    for alias in [key, *METRIC_ALIASES.get(key, [])]:
        if alias.lower() in semantic and close_enough(semantic[alias.lower()], expected, kind):
            return True
    return nearby_value(visible, METRIC_ALIASES[key], expected, kind)


def test_dashboard_artifact_is_readable_and_offline() -> None:
    assert OUTPUT.is_file(), "The requested SaaS dashboard HTML is missing."
    raw, parser, visible = load_dashboard()
    assert len(raw) >= 1500 and "<html" in raw.lower(), "The deliverable is not a usable HTML dashboard."
    assert len(visible) >= 400, "The dashboard has too little human-readable content for an executive view."
    remote_refs = [value for value in parser.external_refs if re.match(r"^(?:https?:)?//", value, re.I)]
    remote_css = re.findall(r"url\(\s*['\"]?(https?://|//)", raw, re.I)
    assert not remote_refs and not remote_css, f"The dashboard depends on remote resources and will not work offline: {remote_refs}"


def test_current_kpis_are_correct() -> None:
    _, parser, visible = load_dashboard()
    truth = ground_truth()["metrics"]
    expected = [
        ("current_mrr", "money"),
        ("mrr_growth_pct", "percent"),
        ("logo_churn_pct", "percent"),
        ("gross_revenue_churn_pct", "percent"),
        ("cac_usd", "money"),
        ("ltv_cac_ratio", "ratio"),
    ]
    missing = [key for key, kind in expected if not metric_present(parser, visible, key, truth[key], kind)]
    assert not missing, f"Headline KPI values are missing or inconsistent with the supplied snapshots: {missing}"


def test_mrr_bridge_reconciles_month_over_month_change() -> None:
    _, parser, visible = load_dashboard()
    expected = ground_truth()["bridge"]
    semantic = {}
    for _, attrs in parser.tags:
        key, raw_value = attrs.get("data-bridge-component"), attrs.get("data-value")
        if key and raw_value:
            try:
                semantic[key.lower()] = float(raw_value)
            except ValueError:
                pass
    aliases = {
        "opening_mrr": ["opening mrr", "starting mrr"],
        "new_mrr": ["new mrr"],
        "expansion_mrr": ["expansion", "expansion mrr"],
        "contraction_mrr": ["contraction", "contraction mrr", "downgrade mrr"],
        "churned_mrr": ["churned mrr", "lost mrr"],
        "closing_mrr": ["closing mrr", "ending mrr", "current mrr"],
    }
    missing = []
    for key, labels in aliases.items():
        value = expected[key]
        semantic_value = semantic.get(key)
        ok = semantic_value is not None and close_enough(abs(semantic_value), abs(value), "money")
        ok = ok or nearby_value(visible, labels, value, "money", absolute=key in {"contraction_mrr", "churned_mrr"})
        if not ok:
            missing.append(key)
    assert not missing, f"The MRR movement drilldown does not reconcile the opening and closing totals: {missing}"


def test_historical_trend_and_churn_drilldown_are_supported() -> None:
    _, parser, visible = load_dashboard()
    truth = ground_truth()
    semantic_months = {}
    reason_rows, segment_rows = {}, {}
    for _, attrs in parser.tags:
        if attrs.get("data-month") and attrs.get("data-mrr"):
            try:
                semantic_months[attrs["data-month"]] = float(attrs["data-mrr"])
            except ValueError:
                pass
        for attr, destination in (("data-churn-reason", reason_rows), ("data-churn-segment", segment_rows)):
            if attrs.get(attr) and attrs.get("data-count"):
                try:
                    destination[attrs[attr].lower()] = float(attrs["data-count"])
                except ValueError:
                    pass
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    matched_months = 0
    for month, value in truth["months"].items():
        exact = month in semantic_months and close_enough(semantic_months[month], value, "money")
        year, number = month.split("-")
        labels = [month, f"{month_names[int(number)-1]} {year}", f"{month_names[int(number)-1]}-{year}"]
        if exact or nearby_value(visible, labels, value, "money"):
            matched_months += 1
    assert matched_months >= 7, f"Only {matched_months} of {len(truth['months'])} monthly MRR points can be validated; the trend lacks reliable historical context."

    reason_matches = 0
    for label, values in truth["reasons"].items():
        exact = label.lower() in reason_rows and close_enough(reason_rows[label.lower()], values["count"], "count")
        if exact or nearby_value(visible, [label], values["count"], "count"):
            reason_matches += 1
    segment_matches = 0
    for label, values in truth["segments"].items():
        exact = label.lower() in segment_rows and close_enough(segment_rows[label.lower()], values["count"], "count")
        if exact or nearby_value(visible, [label], values["count"], "count"):
            segment_matches += 1
    assert reason_matches >= min(3, len(truth["reasons"])) or segment_matches >= min(3, len(truth["segments"])), (
        "The churn drilldown does not correctly cover a useful causal dimension (reason or segment)."
    )


def test_actionable_alerts_match_enabled_target_breaches() -> None:
    _, parser, visible = load_dashboard()
    truth = ground_truth()
    semantic = {
        attrs["data-alert-metric"].lower()
        for _, attrs in parser.tags
        if attrs.get("data-alert-metric")
    }
    if semantic:
        observed = set()
        for key in truth["metrics"]:
            if key.lower() in semantic or any(alias in semantic for alias in METRIC_ALIASES.get(key, [])):
                observed.add(key)
    else:
        block_text = " ".join(" ".join(block["text"]) for block in parser.alert_blocks)
        if not block_text.strip():
            lowered = visible.lower()
            match = re.search(r"(?:actionable\s+)?alerts?", lowered)
            if match:
                end_positions = [lowered.find(term, match.end()) for term in ("mrr bridge", "churn drilldown", "metric definitions")]
                end_positions = [position for position in end_positions if position >= 0]
                block_text = visible[match.start(): min(end_positions) if end_positions else len(visible)]
        observed = {
            key for key, labels in METRIC_ALIASES.items()
            if any(re.search(rf"\b{re.escape(label)}\b", block_text, re.I) for label in labels)
        }
    assert observed == truth["breached"], (
        f"Actionable alerts are inconsistent with enabled breached targets: expected {sorted(truth['breached'])}, observed {sorted(observed)}. "
        "A disabled or healthy metric must not be presented as an active breach."
    )
