from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest


RESULTS = Path("/root/results")
PLAN = RESULTS / "plan.md"
TODO = RESULTS / "todo.md"


def _read(path: Path) -> tuple[str, str | None]:
    if not path.is_file():
        return "", f"missing requested artifact: {path}"
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return "", f"cannot read {path} as UTF-8 Markdown: {exc}"


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("–", "-").replace("—", "-").replace("_", " ")
    text = re.sub(r"[`*#>|()[\]{}:,;/\\]+", " ", text)
    text = re.sub(r"[-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _submission() -> tuple[str, list[str], str, str]:
    plan, plan_error = _read(PLAN)
    todo, todo_error = _read(TODO)
    return _normalize(plan + "\n" + todo), [e for e in (plan_error, todo_error) if e], plan, todo


def _has_any(text: str, alternatives: tuple[str, ...]) -> bool:
    return any(_normalize(option) in text for option in alternatives)


def _missing_concepts(text: str, concepts: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    return [name for name, alternatives in concepts if not _has_any(text, alternatives)]


COVERAGE_CASES = [
    pytest.param(
        "versioned persistence and safe migration",
        (
            ("one schedule per project", ("one schedule per project", "unique project id", "unique project")),
            ("versioned/stale-write protection", ("stale version", "stale write", "409 conflict", "versioned write")),
            ("next occurrence storage", ("next run at", "next future occurrence", "next future run")),
            ("unique schedule occurrence", ("schedule id scheduled for", "unique occurrence", "one run for a schedule occurrence")),
            ("backward-safe no-backfill migration", ("no backfill", "no rows for existing projects", "no existing project receives a schedule")),
            ("migration rollback", ("down migration", "migration down", "schema rollback")),
        ),
        id="persistence",
    ),
    pytest.param(
        "API authorization, validation, and preview contract",
        (
            ("schedule read/write endpoints", ("get returns a schedule", "get /api/projects", "schedule read")),
            ("write endpoint", ("put rejects", "put /api/projects", "versioned upsert")),
            ("active-member read and admin/owner write", ("active member", "member read", "admin owner write", "admins owners")),
            ("IANA rather than fixed-offset zone", ("iana", "fixed utc offset", "fixed offset")),
            ("time/weekday/mode validation", ("time weekday mode", "time weekday recipient", "weekday local time recipient mode")),
            ("preview authorization", ("preview enforces role", "preview to admins", "preview admin owner")),
        ),
        id="api",
    ),
    pytest.param(
        "digest content and side-effect-free preview",
        (
            ("prior seven complete days", ("seven complete days", "prior seven complete days", "previous seven complete days")),
            ("activity totals", ("activity totals", "type totals", "totals and")),
            ("20-item cap", ("20 item", "at most 20", "limit of 20")),
            ("stable newest-first tie-break", ("occurred at activity id", "activity id tie", "stable newest first", "deterministic tie break")),
            ("no preview side effects", ("no database side effects", "zero side effects", "creates no schedule run outbox", "without touching schedule run audit or outbox")),
        ),
        id="content_preview",
    ),
    pytest.param(
        "due scheduling and exactly-once occurrence claim",
        (
            ("five-minute poll", ("five minute poll", "polls every five minutes", "five minute due scan")),
            ("enabled due selection", ("enabled due schedule", "disabled future rows are ignored", "next run at <= now")),
            ("overlap/concurrency protection", ("overlapping workers", "concurrent pollers", "two worker overlap")),
            ("one claimed run", ("exactly one run", "one run for", "never duplicate a run", "one ledger row")),
            ("no replay on re-enable", ("missed weeks are not replayed", "never replays missed weeks", "rather than catch up runs")),
        ),
        id="scheduling",
    ),
    pytest.param(
        "recipient filtering and zero-recipient behavior",
        (
            ("active membership", ("active member", "active project members")),
            ("admins-only role restriction", ("admins only", "admin owner")),
            ("email opt-out exclusion", ("opt out", "opted out", "email opt out")),
            ("zero-recipient skipped run", ("zero recipients", "zero eligible recipients")),
            ("ZERO_RECIPIENTS reason", ("zero recipients",)),
            ("no outbox when empty", ("without outbox", "no outbox", "creates no outbox")),
        ),
        id="recipients",
    ),
    pytest.param(
        "transactional outbox and existing mail delivery path",
        (
            ("transactional outbox", ("transactional outbox",)),
            ("project.digest.requested event", ("project.digest.requested", "project digest requested")),
            ("stable occurrence dedupe", ("stable occurrence dedupe", "stable schedule occurrence dedupe", "same occurrence and dedupe")),
            ("atomic claim/advance/outbox", ("claim advance run and one outbox", "claim run state schedule advancement and outbox", "atomically append")),
            ("existing retry with sent/failed state", ("existing retry", "existing retry policy", "sent or failed")),
            ("no new/direct send path", ("no second queue", "does not create a queue", "without introducing a new queue")),
        ),
        id="delivery",
    ),
    pytest.param(
        "audit privacy contract",
        (
            ("schedule update audit", ("project digest schedule updated", "schedule updated audit", "append a redacted audit")),
            ("actor/project/changed fields", ("actor project and changed field", "actor project changed field")),
            ("no recipient email in audit/outbox", ("no email address", "without recording email", "email addresses in run or audit")),
        ),
        id="audit_security",
    ),
    pytest.param(
        "settings UI states and accessibility",
        (
            ("project digest settings panel", ("project digest panel", "settings panel")),
            ("loading/no-schedule/edit/save states", ("loading no schedule edit saving", "loading empty edit save", "loading no schedule editable saving")),
            ("stale/conflict and generic error", ("conflict and generic error", "stale version generic error", "conflict error")),
            ("preserve failed-save values", ("preserving failed save input", "preserve unsaved", "do not discard schedule edits")),
            ("associated accessible labels/errors", ("associating labels errors", "accessible label", "remain accessible")),
        ),
        id="ui",
    ),
    pytest.param(
        "flag-off enforcement across system boundaries",
        (
            ("all four flag boundaries", ("api poller consumer and ui", "api scheduler mail consumer and settings ui")),
            ("default-off flag", ("default off", "off by default")),
        ),
        id="rollout",
    ),
]


@pytest.mark.parametrize(("case_name", "concepts"), COVERAGE_CASES)
def test_feature_coverage(case_name: str, concepts: tuple[tuple[str, tuple[str, ...]], ...]) -> None:
    text, errors, _, _ = _submission()
    assert not errors, "; ".join(errors)
    missing = _missing_concepts(text, concepts)
    assert not missing, (
        f"{case_name} is incomplete; missing material concepts: {', '.join(missing)}. "
        "Equivalent wording is accepted, but omitting these source obligations would leave the implementation plan unsafe or incomplete."
    )
