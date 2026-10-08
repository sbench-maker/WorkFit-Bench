from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest


DATA = Path(os.environ.get("STANDUP_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("STANDUP_OUTPUT_PATH", "/root/results/standup.md"))


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _plain(value: str) -> str:
    value = value.lower().replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9:#+'-]+", " ", value)).strip()


def _has_ref(text: str, reference: str) -> bool:
    return _compact(reference) in _compact(text)


def _has_pr(text: str, number: int) -> bool:
    return bool(re.search(rf"(?:\bpr|pull\s+request)\s*#?\s*{number}\b|#\s*{number}\b", text, re.I))


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = _plain(text)
    return any(re.search(term, normalized, re.I) for term in terms)


def _heading_section(line: str) -> str | None:
    stripped = line.strip()
    is_markdown_heading = stripped.startswith("#")
    is_bold_heading = bool(re.fullmatch(r"\*\*[^*]{1,60}\*\*:?", stripped))
    is_short_label = len(stripped) <= 45 and stripped.endswith(":")
    if not (is_markdown_heading or is_bold_heading or is_short_label):
        return None
    label = _plain(re.sub(r"^[#* _]+|[#* _:]+$", "", stripped))
    if "yesterday" in label or "previous day" in label or label in {"completed", "done"}:
        return "yesterday"
    if "today" in label or label in {"next up", "plan", "planned"}:
        return "today"
    if any(term in label for term in ("blocker", "blocked", "blocking", "impediment")):
        return "blockers"
    return None


def _parse_sections(raw: str) -> dict[str, str]:
    buckets: dict[str, list[str]] = {"yesterday": [], "today": [], "blockers": []}
    current: str | None = None
    for line in raw.splitlines():
        section = _heading_section(line)
        if section is not None:
            current = section
            continue
        if current is not None and line.strip():
            buckets[current].append(line.strip())
    return {key: "\n".join(value).strip() for key, value in buckets.items()}


def _load_submission() -> tuple[str | None, dict[str, str], str | None]:
    if not OUTPUT.is_file():
        return None, {}, f"requested artifact is missing: {OUTPUT}"
    try:
        raw = OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, {}, f"standup.md is not readable UTF-8 text: {exc}"
    return raw, _parse_sections(raw), None


def _source_truth() -> dict[str, Any]:
    profile = json.loads((DATA / "profile.json").read_text(encoding="utf-8"))
    tickets = {row["ticket_id"]: row for row in json.loads((DATA / "tickets.json").read_text(encoding="utf-8"))}
    prs = json.loads((DATA / "pull_requests.json").read_text(encoding="utf-8"))
    with (DATA / "ticket_events.csv").open(newline="", encoding="utf-8") as handle:
        events = list(csv.DictReader(handle))
    with (DATA / "ci_runs.csv").open(newline="", encoding="utf-8") as handle:
        ci_runs = list(csv.DictReader(handle))
    messages = [json.loads(line) for line in (DATA / "chat_messages.jsonl").read_text(encoding="utf-8").splitlines()]
    latest_status: dict[str, str] = {}
    for event in sorted(events, key=lambda row: row["occurred_at_utc"]):
        if event["event_type"] == "status":
            latest_status[event["ticket_id"]] = event["to_value"]
    latest_ci: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in sorted(ci_runs, key=lambda item: item["completed_at_utc"]):
        latest_ci[(row["repository"], row["ref"], row["workflow"])] = row
    return {
        "profile": profile,
        "tickets": tickets,
        "prs": prs,
        "latest_status": latest_status,
        "latest_ci": latest_ci,
        "messages": messages,
    }


TRUTH = _source_truth()


def _section(name: str) -> str:
    raw, sections, error = _load_submission()
    assert error is None, error
    assert raw is not None
    assert sections.get(name), f"the {name} section is missing or empty, so its task content cannot be reviewed"
    return sections[name]


@pytest.mark.parametrize("case", ["webhook_delivery", "audit_panel", "code_review", "timezone_boundary"])
def test_yesterday_activity_coverage(case: str) -> None:
    yesterday = _section("yesterday")
    if case == "webhook_delivery":
        pr = next(row for row in TRUTH["prs"] if row["pr_id"] == "relay-service#318")
        assert _has_ref(yesterday, pr["linked_ticket"]) and _has_pr(yesterday, pr["number"]), "OPS-482 webhook work needs useful ticket and PR traceability"
        assert _has_any(yesterday, (r"webhook", r"delivery")) and _has_any(yesterday, (r"retr(?:y|ies)", r"backoff", r"jitter")), "yesterday omits the substance of the webhook retry work"
        assert _has_any(yesterday, (r"merged", r"landed", r"completed", r"done")), "the completed merge outcome for PR 318 is unclear"
        assert _has_any(yesterday, (r"staging", r"deploy")) and _has_any(yesterday, (r"success", r"passed", r"green", r"healthy")), "the successful current CI/deploy outcome is missing or misleading"
    elif case == "audit_panel":
        pr = next(row for row in TRUTH["prs"] if row["pr_id"] == "admin-console#912")
        assert _has_ref(yesterday, pr["linked_ticket"]) and _has_pr(yesterday, pr["number"]), "APP-771 audit-panel work needs useful ticket and PR traceability"
        assert _has_any(yesterday, (r"permission", r"role")) and _has_any(yesterday, (r"audit", r"diff")), "yesterday omits the substance of the permission-audit work"
        assert _has_any(yesterday, (r"progress", r"advanced", r"started", r"opened", r"built", r"implemented", r"worked")), "the in-progress outcome for APP-771 is unclear"
    elif case == "code_review":
        assert _has_pr(yesterday, 640), "Maya's September 8 review of PR 640 is missing"
        assert _has_any(yesterday, (r"review", r"approved", r"approval")), "PR 640 is mentioned without Maya's review/approval contribution"
    else:
        assert not _has_pr(yesterday, 911), "PR 911 merged at 23:55 local on September 7 and must not leak into September 8 work"


@pytest.mark.parametrize("case", ["audit_followup", "rollout_pairing"])
def test_today_plan_fidelity(case: str) -> None:
    today = _section("today")
    if case == "audit_followup":
        assert _has_ref(today, "APP-771") or _has_pr(today, 912), "today omits the APP-771/PR 912 follow-up"
        assert _has_any(today, (r"component", r"test", r"coverage")), "today omits the planned component-test work"
        assert _has_any(today, (r"review", r"feedback", r"comment")) and _has_any(today, (r"respond", r"address", r"resolve", r"reply")), "today omits the planned response to PR 912 review feedback"
    else:
        assert _has_any(today, (r"theo",)), "today omits the planned pairing partner"
        assert _has_ref(today, "OPS-482") or _has_pr(today, 318), "today's rollout check is not tied to OPS-482/PR 318"
        assert _has_any(today, (r"rollout", r"metric", r"monitor", r"verify")), "today omits the rollout-metrics verification"
        assert _has_any(today, (r"14:00", r"14 00", r"2\s*(?:pm|p\.m\.)")), "today omits the scheduled 14:00 pairing time"


def _actively_claimed(text: str, reference: str) -> bool:
    match = re.search(re.escape(_compact(reference)), _compact(text))
    if match is None:
        return False
    plain = _plain(text)
    tokens = _plain(reference).replace("-", "[- ]?")
    located = re.search(tokens, plain, re.I)
    context = plain if located is None else plain[max(0, located.start() - 55): located.end() + 55]
    return not _has_any(context, (r"\bnot\b", r"no longer", r"resolved", r"unblocked", r"cleared"))


@pytest.mark.parametrize("case", ["active_dependency", "resolved_ticket", "resolved_ci"])
def test_blocker_handling(case: str) -> None:
    blockers = _section("blockers")
    if case == "active_dependency":
        assert TRUTH["latest_status"]["DATA-205"] == "Blocked"
        assert _has_ref(blockers, "DATA-205"), "the still-blocked DATA-205 issue is missing"
        assert _has_any(blockers, (r"redacted",)) and _has_any(blockers, (r"replay", r"sample")), "the needed redacted replay sample is not clear"
        assert _has_any(blockers, (r"nia",)) and _has_any(blockers, (r"security", r"approval")), "the helper and approval dependency are not clear"
    elif case == "resolved_ticket":
        assert TRUTH["latest_status"]["AUTH-90"] == "Done"
        assert not _actively_claimed(blockers, "AUTH-90"), "AUTH-90 was unblocked and completed, so it cannot be presented as active"
    else:
        latest = TRUTH["latest_ci"][("admin-console", "912", "browser-e2e")]
        assert latest["conclusion"] == "success"
        assert not _actively_claimed(blockers, "PR-912") and not _actively_claimed(blockers, "#912"), "the earlier PR 912 browser failure was resolved by a later success and is not a blocker"
