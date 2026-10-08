from __future__ import annotations

import csv
import html as html_lib
import json
import math
import os
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
import re

import pytest


ROOT = Path(os.environ.get("TASK_ROOT", "/root"))
DATA = ROOT / "data"
OUTPUT = ROOT / "results" / "index.html"


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"style", "script", "template"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"style", "script", "template"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            self.parts.append(data)


def _norm(value: str) -> str:
    value = html_lib.unescape(value).lower().replace("小红书", "xiaohongshu")
    value = re.sub(r"[^\w%+./:-]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=1)
def _artifact() -> tuple[str, str | None]:
    try:
        source = OUTPUT.read_text(encoding="utf-8")
    except OSError as exc:
        return "", f"index.html is unavailable: {exc}"
    if not source.strip():
        return "", "index.html is empty"
    return source, None


def _source() -> str:
    source, error = _artifact()
    assert error is None, error
    return source


def _visible(source: str) -> str:
    parser = _VisibleText()
    try:
        parser.feed(source)
    except Exception:
        return ""
    return " ".join(parser.parts)


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=1)
def _config() -> dict:
    return json.loads((DATA / "campaign_config.json").read_text(encoding="utf-8"))


def _integer(row: dict[str, str], key: str) -> int:
    return int(row[key]) if row.get(key) else 0


def _sum(rows: list[dict[str, str]], key: str) -> int:
    return sum(_integer(row, key) for row in rows)


def _rate(rows: list[dict[str, str]]) -> float:
    reach = _sum(rows, "reach")
    return round(100 * _sum(rows, "engagements") / reach, 2)


def _last_follower(rows: list[dict[str, str]], day: str) -> int:
    found = [row for row in rows if row["date"] <= day and row["followers_end"]]
    return int(max(found, key=lambda row: row["date"])["followers_end"])


def _number_values(source: str) -> list[float]:
    values: list[float] = []
    pattern = r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*[kmbKMB]?%?"
    for match in re.finditer(pattern, source):
        token = match.group(0).strip().replace(",", "")
        if token.endswith("%"):
            token = token[:-1]
        multiplier = 1.0
        if token[-1:].lower() in {"k", "m", "b"}:
            multiplier = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}[token[-1].lower()]
            token = token[:-1].strip()
        try:
            values.append(float(token) * multiplier)
        except ValueError:
            pass
    return values


def _has_number(source: str, expected: float, *, tolerance: float | None = None) -> bool:
    if tolerance is None:
        tolerance = 0.06 if abs(expected) < 100 else max(0.5, abs(expected) * 0.006)
    return any(math.isclose(value, expected, rel_tol=0, abs_tol=tolerance) for value in _number_values(source))


def _platform_segment(source: str, platform: str) -> str:
    aliases = [platform]
    if platform == "Xiaohongshu":
        aliases.append("小红书")
    chunks: list[str] = []
    for alias in aliases:
        for match in re.finditer(re.escape(alias), source, flags=re.I):
            chunks.append(source[max(0, match.start() - 450): min(len(source), match.end() + 2600)])
    return "\n".join(chunks)


def _expected_platform(platform: str) -> dict:
    config = _config()
    rows = [row for row in _read_csv("daily_platform_metrics.csv") if row["platform"] == platform]
    cs, ce = config["current_window"]["start"], config["current_window"]["end"]
    ps, pe = config["prior_window"]["start"], config["prior_window"]["end"]
    current = [row for row in rows if cs <= row["date"] <= ce and row["data_status"] != "export_unavailable"]
    prior = [row for row in rows if ps <= row["date"] <= pe and row["data_status"] != "export_unavailable"]
    current_er, prior_er = _rate(current), _rate(prior)
    change = round(100 * (current_er - prior_er) / prior_er, 1)
    followers = _last_follower(rows, ce)
    prior_followers = _last_follower(rows, pe)
    approved = [
        row for row in _read_csv("content_posts.csv")
        if row["platform"] == platform and row["moderation_status"] == "approved"
    ]
    top = max(approved, key=lambda row: (_integer(row, "conversions"), _integer(row, "clicks")))
    mean_sla = round(sum(_integer(row, "response_minutes_median") for row in current) / len(current), 1)
    alerts = []
    if change <= -15:
        alerts.append("ER_DROP")
    if mean_sla > 45:
        alerts.append("SLA_BREACH")
    return {
        "followers": followers,
        "growth": followers - prior_followers,
        "engagement_rate": current_er,
        "prior_engagement_rate": prior_er,
        "er_change": change,
        "impressions": _sum(current, "impressions"),
        "conversions": _sum(current, "conversions"),
        "coverage": len(current),
        "top": top,
        "alerts": alerts,
    }


def test_artifact_is_self_contained_and_readable() -> None:
    source = _source()
    lowered = source.lower()
    assert len(source.encode("utf-8")) >= 8_000, "index.html is too small to be a substantive data-dense interactive dashboard"
    assert re.search(r"<!doctype\s+html", source, re.I), "index.html is not a complete HTML document"
    for tag in ("html", "head", "body", "style", "script"):
        assert re.search(rf"<{tag}\b", source, re.I), f"standalone dashboard is missing <{tag}>"
    assert "http://" not in lowered and "https://" not in lowered, "dashboard contains a network URL despite the offline requirement"
    refs = re.findall(r"<(?:script|img|link|iframe|audio|video|source)\b[^>]+(?:src|href)\s*=\s*['\"]([^'\"]+)", source, re.I)
    assert all(ref.strip().lower().startswith(("data:", "#")) for ref in refs), "dashboard loads a separate resource instead of remaining self-contained"


@pytest.mark.parametrize("platform", ("TikTok", "Instagram", "YouTube", "Xiaohongshu"))
def test_platform_metrics_alerts_and_gaps(platform: str) -> None:
    source = _source()
    segment = _platform_segment(source, platform)
    assert segment, f"{platform} is absent from the social matrix"
    expected = _expected_platform(platform)
    for key in ("followers", "growth", "engagement_rate", "prior_engagement_rate", "er_change", "impressions", "conversions", "coverage"):
        tolerance = 0.06 if key in {"engagement_rate", "prior_engagement_rate"} else (0.11 if key == "er_change" else None)
        assert _has_number(segment, expected[key], tolerance=tolerance), (
            f"{platform} {key}={expected[key]} is not represented near its platform data; the 30-day review would be misleading"
        )
    top = expected["top"]
    top_prefix = " ".join(_norm(top["title"]).split()[:9])
    assert top_prefix in _norm(segment), f"{platform} highest-converting approved post {top['post_id']} is not represented"
    assert _has_number(segment, int(top["conversions"])), f"{platform} top-post conversions are inaccurate or absent"
    for alert_id in expected["alerts"]:
        assert alert_id.lower() in segment.lower(), f"{platform} active threshold alert {alert_id} is missing"
    if platform == "YouTube":
        normalized = _norm(segment)
        assert "2026-08-14" in normalized and ("unavailable" in normalized or "29/30" in normalized), (
            "the unavailable YouTube export day is not disclosed, risking a false zero or 30-day claim"
        )
    if platform == "Xiaohongshu":
        normalized = _norm(segment)
        assert "2026-08-17" in normalized and "follower" in normalized and ("missing" in normalized or "do not treat" in normalized), (
            "the missing follower snapshot is not disclosed as a gap with valid activity retained"
        )


@pytest.mark.parametrize("platform", ("TikTok", "Instagram", "YouTube", "Xiaohongshu"))
def test_platform_chart_series(platform: str) -> None:
    source = _source()
    segment = _platform_segment(source, platform)
    hourly = [row for row in _read_csv("hourly_engagement.csv") if row["platform"] == platform]
    assert all(_norm(row["hour_local"]) in _norm(segment) for row in hourly), f"{platform} hourly x-axis coverage is incomplete"
    assert all(_has_number(segment, float(row["engagement_rate_pct"]), tolerance=0.06) for row in hourly), (
        f"{platform} hourly engagement series does not agree with hourly_engagement.csv"
    )
    posts = [
        row for row in _read_csv("content_posts.csv")
        if row["platform"] == platform and row["moderation_status"] == "approved"
    ]
    for fmt in ("Video", "Thread", "Carousel"):
        value = _sum([row for row in posts if row["format"] == fmt], "engagements")
        assert fmt.lower() in segment.lower() and _has_number(segment, value), f"{platform} approved {fmt} engagement mix is missing or inaccurate"
    sentiment = [_sum(posts, key) for key in ("positive_comments", "neutral_comments", "negative_comments")]
    total = sum(sentiment)
    percentages = [round(100 * value / total, 1) for value in sentiment]
    percentages[-1] = round(100 - percentages[0] - percentages[1], 1)
    for label, value in zip(("positive", "neutral", "negative"), percentages):
        assert label in segment.lower() and _has_number(segment, value, tolerance=0.06), f"{platform} {label} sentiment share is missing or inaccurate"


def test_cross_platform_chart_series() -> None:
    source = _source()
    normalized = _norm(source)
    assert len(re.findall(r"<canvas\b", source, re.I)) >= 7, "the required data-dense multi-chart scope is incomplete"
    headings = {
        "conversion funnel": ("conversion funnel", "campaign funnel"),
        "response SLA": ("response sla", "response time"),
        "ROI": ("roi", "revenue vs content cost", "return on"),
        "retention": ("cohort retention", "audience retention"),
        "geography": ("geo contribution", "geographic contribution", "regional contribution"),
    }
    for label, aliases in headings.items():
        assert any(alias in normalized for alias in aliases), f"the required {label} chart section is absent"
    daily = _read_csv("daily_platform_metrics.csv")
    config = _config()
    cs, ce = config["current_window"]["start"], config["current_window"]["end"]
    current = [row for row in daily if cs <= row["date"] <= ce and row["data_status"] != "export_unavailable"]
    funnel = [_sum(current, key) for key in ("impressions", "profile_visits", "link_clicks", "conversions")]
    assert all(_has_number(source, value) for value in funnel), "conversion funnel values do not reconcile to complete activity rows"
    weekly = _read_csv("weekly_operations.csv")
    for key in ("response_sla_minutes", "roi_multiplier", "cohort_retention_pct"):
        for row in weekly:
            expected = float(row[key])
            assert _has_number(source, expected, tolerance=0.06 if key == "roi_multiplier" else None), f"weekly {key} series is incomplete or inaccurate"
    for row in _read_csv("geo_conversions.csv"):
        assert _norm(row["region"]) in normalized and _has_number(source, int(row["conversions"])), f"geo contribution for {row['region']} is absent or inaccurate"
    assert re.search(r"(?:minutes?|\bm\b)", normalized), "response SLA unit is not identified as minutes"
    assert re.search(r"(?:multiplier|\bx\b)", normalized), "ROI values are not identified as multipliers"
    assert "%" in source, "percentage units are missing from rate and retention charts"


def test_requested_interaction_contract() -> None:
    source = _source()
    lowered = source.lower()
    visible = _norm(_visible(source))
    for platform in ("TikTok", "Instagram", "YouTube", "Xiaohongshu"):
        static_control = re.search(rf"<(?:button|option)[^>]*>[^<]*{re.escape(platform)}", source, re.I | re.S)
        dynamic_control = platform.lower() in lowered and "data-platform" in lowered and re.search(r"<button[^>]*\$\{|createelement\s*\(\s*['\"]button", lowered)
        assert static_control or dynamic_control, (
            f"{platform} is not exposed through a selectable platform control"
        )
    assert "dark" in visible and "light" in visible and ("data-theme" in lowered or re.search(r"classlist\.(?:add|toggle).*theme", lowered)), (
        "dark/light controls or theme state switching are missing"
    )
    assert re.search(r"(?:pointermove|mousemove|touchmove|onmousemove)", lowered), "charts have no hover/pointer-move detail wiring"
    assert "tooltip" in lowered and re.search(r"(?:innerwidth|clientwidth|getboundingclientrect)", lowered), (
        "hover tooltips are missing or show no viewport-aware positioning logic"
    )
    assert "pin" in lowered and re.search(r"(?:click|pointerdown|mousedown|touchstart)", lowered), "point pinning state or activation is missing"
    assert re.search(r"(?:pointerdown|mousedown|touchstart)", lowered) and re.search(r"(?:pointerup|mouseup|touchend)", lowered), (
        "drag interval selection lacks a complete start/end interaction"
    )
    assert "shiftkey" in lowered and re.search(r"ranges?|compar", lowered), "Shift+drag saved-range comparison is not implemented"
    assert re.search(r"insight", lowered) and re.search(r"(?:innerhtml|textcontent)", lowered), "chart interactions do not update a live insight region"
