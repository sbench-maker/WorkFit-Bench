from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path


DATA = Path(os.environ.get("SKILLSBENCH_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("SKILLSBENCH_OUTPUT_PATH", "/root/results/kb_article.md"))
if not DATA.is_absolute() or not OUTPUT.is_absolute():
    raise ValueError("Verifier data and output paths must be absolute")


def output_text() -> str:
    if not OUTPUT.is_file():
        return ""
    try:
        return OUTPUT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def normalized(value: str) -> str:
    table = str.maketrans({
        "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
        "→": ">", "›": ">", "\u00a0": " ",
    })
    value = value.translate(table).casefold()
    value = re.sub(r"[`*_#|]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def lines(text: str) -> list[str]:
    return [normalized(line) for line in text.splitlines() if line.strip()]


def has_any(flat: str, options: tuple[str, ...]) -> bool:
    return any(normalized(option) in flat for option in options)


def has_date(text: str, year: int, month: int, day: int) -> bool:
    patterns = (
        rf"\b{year}-{month:02d}-{day:02d}\b",
        rf"\b(?:sep(?:tember)?)[ .-]+{day}(?:st|nd|rd|th)?[,]?[ .-]+{year}\b",
        rf"\b{day}[ .-]+(?:sep(?:tember)?)[, .-]+{year}\b",
    )
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def sequence_positions(flat: str, option_groups: list[tuple[str, ...]], start: int = 0) -> list[int]:
    positions: list[int] = []
    cursor = start
    for options in option_groups:
        candidates = []
        for option in options:
            at = flat.find(normalized(option), cursor)
            if at >= 0:
                candidates.append(at)
        if not candidates:
            return []
        found = min(candidates)
        positions.append(found)
        cursor = found + 1
    return positions


def current_reference() -> dict:
    return json.loads((DATA / "product_support_reference.json").read_text(encoding="utf-8"))["issue"]


def test_exact_symptom_and_root_condition():
    text = output_text()
    flat = normalized(text)
    reference = current_reference()
    assert OUTPUT.is_file() and text.strip(), "The requested Markdown article is missing or unreadable."
    assert normalized(reference["exact_error"]) in flat, (
        "The exact customer-visible MAP-403 message is missing or altered, so customers searching their pasted error may not find the article."
    )
    saved_mapping = has_any(flat, ("saved mapping", "saved import mapping", "reusable mapping"))
    deactivated_owner = (
        has_any(flat, ("original owner", "mapping owner", "member who created"))
        and has_any(flat, ("deactivated", "disabled member", "inactive member"))
    )
    assert saved_mapping and deactivated_owner, (
        "The article does not connect the failure to a saved mapping whose original owner was deactivated; readers could apply the workaround to the wrong import failure."
    )


def test_affected_and_unaffected_scope():
    flat = normalized(output_text())
    assert has_any(flat, ("arcway crm web app", "arcway web app", "web app")), "The affected application surface is not identified."
    assert "business" in flat and "enterprise" in flat, "Both affected plans, Business and Enterprise, must be clear."
    assert has_any(flat, ("workspace admin", "workspace administrator")), "The reader is not told that a Workspace Admin must apply the workaround."
    exclusions = {
        "fresh import": ("fresh csv import", "new csv import", "without a saved mapping", "no saved mapping"),
        "API import": ("contacts api", "api import"),
        "other CSV errors": ("column validation", "csv-102", "file encoding", "encoding error", "csv-201"),
    }
    missing = [name for name, options in exclusions.items() if not has_any(flat, options)]
    assert not missing, f"The article fails to distinguish nearby but unaffected cases: {missing}."


def test_supported_workaround():
    text = output_text()
    flat = normalized(text)
    settings_at = flat.find("settings")
    assert settings_at >= 0, "The workaround never directs the admin to Settings."
    order = sequence_positions(flat, [
        ("settings",),
        ("data management",),
        ("import mappings", "saved mappings"),
        ("deactivated", "inactive owner"),
        ("duplicate", "make a copy", "copy the mapping"),
        ("active workspace admin", "active admin", "workspace administrator"),
        ("save",),
        ("contacts > import", "contacts / import", "contacts import"),
        ("duplicated mapping", "copied mapping", "new mapping"),
        ("run import", "start import"),
    ], start=settings_at)
    assert order, (
        "The approved sequence is incomplete or out of order: locate the deactivated owner's mapping, duplicate it, assign the copy to an active admin, save it, then run the contact import with the copy."
    )

    unsafe_lines = []
    for line in lines(text):
        if "reactivat" in line and not has_any(line, ("do not", "don't", "never", "avoid", "no need", "should not", "must not", "excluded", "unsupported")):
            unsafe_lines.append(line)
        if ("change" in line or "rename" in line) and "csv header" in line and not has_any(line, ("do not", "don't", "not need", "no need", "should not", "must not")):
            unsafe_lines.append(line)
    assert not unsafe_lines, f"The article presents a contradicted legacy or unrelated action as usable guidance: {unsafe_lines[:2]}."


def test_verification_and_escalation():
    flat = normalized(output_text())
    verification = {
        "start banner": ("import started",),
        "activity path": ("activity > imports", "activity / imports", "activity imports"),
        "completed state": ("completed", "completion status"),
        "row outcome": ("imported and skipped", "imported rows", "skipped row", "row counts"),
    }
    missing_verify = [name for name, options in verification.items() if not has_any(flat, options)]
    assert not missing_verify, f"Success cannot be verified from the article; missing: {missing_verify}."

    assert "map-403" in flat and has_any(flat, ("still", "continues", "again", "persists")), "The escalation trigger does not cover MAP-403 persisting after the copy."
    assert has_any(flat, ("no active workspace admin", "administrator cannot", "admin can't", "admin cannot")), "The no-admin-access escalation case is missing."
    evidence = {
        "failed import run ID": ("imp-...", "import run id", "run id"),
        "mapping ID": ("map-...", "mapping id"),
        "timestamp and time zone": ("timestamp with time zone", "timestamp and time zone", "time zone"),
        "browser version": ("browser name and version", "browser version"),
    }
    missing_evidence = [name for name, options in evidence.items() if not has_any(flat, options)]
    assert not missing_evidence, f"The escalation package omits diagnostic evidence: {missing_evidence}."
    assert "csv" in flat and has_any(flat, ("do not attach", "don't attach", "only attach", "unless support", "secure upload")), (
        "The article does not preserve the source-CSV privacy boundary for escalation."
    )


def test_artifact_and_publishing_context():
    text = output_text()
    flat = normalized(text)
    assert OUTPUT.is_file() and text.strip(), "The requested Markdown article is missing or unreadable."

    metadata = {
        "troubleshooting type": ("type: troubleshooting", "article type: troubleshooting", "document kind: troubleshooting"),
        "category": ("category: imports & data", "topic area: imports & data", "imports & data"),
        "tags": ("tags:", "keywords:"),
        "audience": ("audience:", "readers:"),
        "last updated": ("last updated:", "updated:"),
    }
    missing = [name for name, options in metadata.items() if not has_any(flat, options)]
    assert not missing, f"The publishing metadata is incomplete: {missing}."
    assert has_date(text, 2026, 9, 9), "The metadata is not anchored to the 2026-09-09 editorial snapshot."

    assert has_any(flat, ("publishing notes", "editorial handoff", "publication notes", "handoff notes")), "Internal publishing handoff notes are missing."
    assert "bug-2841" in flat and re.search(r"\b24\b.{0,40}\bresolved ticket", flat), (
        "The handoff does not identify the approved evidence base of 24 resolved tickets and BUG-2841."
    )
    assert has_any(flat, ("publish as a new", "new troubleshooting article", "create a new article")), "The supported create-versus-update decision is missing."
    assert "kb-104" in flat and "kb-077" in flat, "The handoff does not name the two existing articles that should link to the new article."
    assert "import engineering" in flat and "support operations" in flat, "Both required reviewing teams are not named."
    assert has_date(text, 2026, 9, 16), "The open known issue lacks its next weekly review date of 2026-09-16."


def test_confidentiality_and_status_hygiene():
    text = output_text()
    flat = normalized(text)
    with (DATA / "accounts.csv").open(encoding="utf-8", newline="") as handle:
        accounts = list(csv.DictReader(handle))
    tickets = [json.loads(line) for line in (DATA / "support_tickets.jsonl").read_text(encoding="utf-8").splitlines() if line]
    messages = [json.loads(line) for line in (DATA / "ticket_messages.jsonl").read_text(encoding="utf-8").splitlines() if line]

    forbidden_identities = {row["account_name"] for row in accounts}
    forbidden_identities.update(row["primary_admin_alias"] for row in accounts)
    forbidden_identities.update(row["requester_alias"] for row in tickets)
    forbidden_identities.update(row["author_alias"] for row in messages if row["author_alias"])
    leaked = sorted(identity for identity in forbidden_identities if len(identity) >= 5 and normalized(identity) in flat)
    assert not leaked, f"The draft exposes fixture identities that are not needed in a public handoff: {leaked[:3]}."
    assert not re.search(r"\bacct-\d{3}\b", flat), "An internal customer account ID appears in the draft."
    assert "lantern-door" not in flat, "The internal project codename appears in the draft."
    assert not has_date(text, 2026, 9, 18), "The superseded September 18 hotfix hope is presented in the draft."
    misleading = (
        "fix will ship", "fix ships", "scheduled fix", "target release", "resolved in version",
        "hotfix is coming", "fix in progress",
    )
    assert not has_any(flat, misleading), "The article implies a fix commitment that the current issue record does not support."

