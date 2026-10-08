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
PLATFORMS = ("X", "LinkedIn", "YouTube", "Instagram")


class _MarkupText(HTMLParser):
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
    value = html_lib.unescape(value).lower()
    value = value.replace("twitter", "x")
    value = re.sub(r"[^\w%+.-]+", " ", value, flags=re.UNICODE)
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


def _visible_text(source: str) -> str:
    parser = _MarkupText()
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
    return json.loads((DATA / "report_config.json").read_text(encoding="utf-8"))


def _number_values(source: str) -> list[float]:
    values: list[float] = []
    pattern = r"(?<![A-Za-z0-9_])[-+]?\d[\d,]*(?:\.\d+)?\s*[kmbKMB]?%?"
    for match in re.finditer(pattern, source):
        token = match.group(0).strip().replace(",", "")
        percent = token.endswith("%")
        if percent:
            token = token[:-1]
        multiplier = 1.0
        if token and token[-1:].lower() in {"k", "m", "b"}:
            multiplier = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}[token[-1].lower()]
            token = token[:-1].strip()
        try:
            values.append(float(token) * multiplier)
        except ValueError:
            pass
    return values


def _has_number(source: str, expected: float, *, tolerance: float | None = None) -> bool:
    tolerance = tolerance if tolerance is not None else (0.06 if abs(expected) < 100 else max(0.5, abs(expected) * 0.001))
    return any(math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance) for actual in _number_values(source))


def _parse_compact_number(token: str) -> float:
    cleaned = token.strip().replace(",", "").replace("%", "")
    multiplier = 1.0
    if cleaned[-1:].lower() in {"k", "m", "b"}:
        multiplier = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}[cleaned[-1].lower()]
        cleaned = cleaned[:-1]
    return float(cleaned) * multiplier


def _metric_expectations(platform: str) -> dict[str, float]:
    config = _config()
    rows = [row for row in _read_csv("daily_metrics.csv") if row["platform"] == platform]
    current_start, current_end = config["comparison_windows"]["current_7d"]
    prior_start, prior_end = config["comparison_windows"]["prior_7d"]
    current = [row for row in rows if current_start <= row["date"] <= current_end and row["is_complete"] == "true"]
    prior = [row for row in rows if prior_start <= row["date"] <= prior_end and row["is_complete"] == "true"]
    sum_key = lambda selected, key: sum(int(row[key]) for row in selected)
    engagement = sum(sum_key(current, key) for key in ("likes", "comments", "reposts", "saves")) / sum_key(current, "impressions") * 100
    follower_end = next(int(row["followers_end"]) for row in rows if row["date"] == current_end)
    prior_follower_end = next(int(row["followers_end"]) for row in rows if row["date"] == prior_end)
    return {
        "followers": follower_end,
        "followers_added": follower_end - prior_follower_end,
        "engagement_rate": round(engagement, 2),
        "likes": sum_key(current, "likes"),
        "reposts": sum_key(current, "reposts"),
    }


def _has_platform_control(source: str, platform: str) -> bool:
    name = re.escape(platform)
    patterns = [
        rf"<(?:button|option|div|a)[^>]*>[^<]*(?:<[^>]+>[^<]*){{0,5}}{name}",
        rf"<(?:button|option|div|a)[^>]*(?:aria-label|data-platform|value)\s*=\s*['\"][^'\"]*{name}",
        rf"<input[^>]*type\s*=\s*['\"]radio['\"][^>]*(?:value|aria-label)\s*=\s*['\"][^'\"]*{name}",
    ]
    return any(re.search(pattern, source, flags=re.I | re.S) for pattern in patterns)


def test_artifact_is_self_contained_and_readable() -> None:
    source = _source()
    lowered = source.lower()
    assert len(source.encode("utf-8")) >= 3000, "index.html is too small to be a substantive multi-platform review dashboard"
    assert re.search(r"<!doctype\s+html", source, re.I), "index.html is not a complete HTML document"
    for tag in ("html", "head", "body", "style"):
        assert re.search(rf"<{tag}\b", source, re.I), f"standalone dashboard is missing <{tag}>"
    assert re.search(r"<main\b|\brole\s*=\s*['\"]main['\"]", source, re.I), (
        "standalone dashboard needs a semantic main landmark"
    )
    assert "http://" not in lowered and "https://" not in lowered, "dashboard references a network URL despite the offline requirement"
    resource_refs = re.findall(
        r"<(?:script|img|link|iframe)\b[^>]+(?:src|href)\s*=\s*['\"]([^'\"]+)['\"]",
        source,
        re.I,
    )
    assert all(ref.strip().lower().startswith(("data:", "#")) for ref in resource_refs), (
        "dashboard loads a separate resource instead of remaining self-contained"
    )


@pytest.mark.parametrize("platform", PLATFORMS)
def test_complete_period_metrics_and_cutoff(platform: str) -> None:
    source = _source()
    expected = _metric_expectations(platform)
    for field, value in expected.items():
        tolerance = 0.06 if field == "engagement_rate" else None
        assert _has_number(source, value, tolerance=tolerance), (
            f"{platform} {field}={value} is not represented; campaign review metrics must use complete-day records"
        )
    normalized = _norm(source)
    assert ("data through sep 7" in normalized or "data through 2026-09-07" in normalized or "complete through 2026-09-07" in normalized), (
        "the dashboard does not clearly disclose the last complete data date"
    )
    assert "partial" in normalized and ("sep 8" in normalized or "2026-09-08" in normalized), (
        "the partial-day status and date are not disclosed, risking a false performance decline"
    )


def test_platform_controls_and_synchronized_regions() -> None:
    source = _source()
    normalized = _norm(source)
    for platform in PLATFORMS:
        assert _has_platform_control(source, platform), f"{platform} is not exposed as a selectable platform control"
    interaction = bool(re.search(r"addEventListener\s*\(|\bon(?:click|change)\s*=|type\s*=\s*['\"]radio|<select\b", source, re.I))
    assert interaction, "platform controls have no observable switching mechanism"
    requested_regions = {
        "followers": ("followers", "audience"),
        "engagement": ("engagement",),
        "likes": ("likes",),
        "reposts": ("reposts", "shares"),
        "growth": ("follower growth", "audience growth"),
        "top post": ("top post", "best post"),
        "topics": ("trending topics", "trending on", "topics"),
        "comments": ("top comments", "comments"),
    }
    for region, aliases in requested_regions.items():
        assert any(alias in normalized for alias in aliases), f"the synchronized {region} region is missing"


@pytest.mark.parametrize("platform", PLATFORMS)
def test_platform_trends_and_ranked_content(platform: str) -> None:
    source = _source()
    normalized = _norm(source)
    config = _config()
    growth_start, growth_end = config["comparison_windows"]["growth_30d"]
    daily = [
        row for row in _read_csv("daily_metrics.csv")
        if row["platform"] == platform and growth_start <= row["date"] <= growth_end and row["is_complete"] == "true"
    ]
    annotations = [row["annotation"] for row in daily if row["annotation"]]
    assert len(daily) == 30, "fixture drift: growth window is no longer 30 complete days"
    assert len(annotations) >= 2, "fixture drift: expected two named growth events"
    for annotation in annotations:
        match = re.match(r"(.+?)\s+([+-][\d,.]+[kKmMbB]?)$", annotation)
        assert match is not None, f"fixture drift: malformed annotation {annotation!r}"
        assert _norm(match.group(1)) in normalized and _has_number(source, _parse_compact_number(match.group(2))), (
            f"{platform} follower trend is missing the named event {annotation!r}"
        )
    assert re.search(r"<svg\b", source, re.I) and re.search(r"<(?:path|polyline)\b|createElementNS", source, re.I), (
        "follower trend is not represented as an inline SVG line/area visualization"
    )

    current_start, current_end = config["comparison_windows"]["current_7d"]
    posts = [
        row for row in _read_csv("posts.csv")
        if row["platform"] == platform and current_start <= row["published_at"][:10] <= current_end and row["is_complete"] == "true"
    ]
    top = max(posts, key=lambda row: int(row["clicks"]))
    post_prefix = " ".join(_norm(top["text"]).split()[:8])
    assert post_prefix in normalized, f"{platform} highest-click complete-week post is not shown as the top post"
    expected_ctr = round(int(top["clicks"]) / int(top["impressions"]) * 100, 2)
    assert _has_number(source, expected_ctr, tolerance=0.06), f"{platform} top-post click-through rate is inaccurate or absent"

    topics = sorted(
        (row for row in _read_csv("trending_topics.csv") if row["platform"] == platform),
        key=lambda row: int(row["rank"]),
    )[:3]
    for topic in topics:
        assert _norm(topic["topic"]) in normalized, f"leading {platform} topic {topic['topic']!r} is missing"
        assert _has_number(source, int(topic["post_count_24h"])), f"post count for {platform} topic {topic['topic']!r} is missing"

    comments = [
        row for row in _read_csv("comments.csv")
        if row["platform"] == platform and row["moderation_status"] == "approved"
    ]
    comments.sort(key=lambda row: int(row["likes"]) + 2 * int(row["replies"]), reverse=True)
    for comment in comments[:2]:
        comment_prefix = " ".join(_norm(comment["body"]).split()[:7])
        assert comment_prefix in normalized, f"leading approved {platform} comment {comment['comment_id']} is missing"
