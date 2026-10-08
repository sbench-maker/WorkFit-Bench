from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


DATA_DIR = Path("/root/data")
OUTPUT_PATH = Path("/root/results/mailbox_state.json")
TARGET_ID = "msg-8f3c91d0a7b2"
EXPECTED_TO = {"mina.chen@aster-ops.test", "devon.lee@aster-ops.test"}
EXPECTED_CC = {"procurement-archive@aster-ops.test"}
ACCOUNT = "aisha.rahman@aster-ops.test"
ALLOWED_ATTACHMENT = "hl-retail-kit-pricing-final.pdf"


def _norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _norm_text(value: object) -> str:
    return " ".join(str(value).casefold().replace("’", "'").split())


def _walk(node: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[Any, tuple[str, ...]]]:
    yield node, path
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, path + (str(key),))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, path + (str(index),))


def _field(node: dict, aliases: set[str]) -> Any:
    wanted = {_norm_key(alias) for alias in aliases}
    for key, value in node.items():
        if _norm_key(key) in wanted:
            return value
    return None


def _deep_text(node: Any) -> str:
    values: list[str] = []
    for value, _ in _walk(node):
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            values.append(str(value))
    return _norm_text("\n".join(values))


def _load_submission() -> tuple[Any, str | None]:
    if not OUTPUT_PATH.is_file():
        return {}, f"missing requested artifact: {OUTPUT_PATH}"
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, f"requested artifact is not readable JSON: {exc}"
    if not isinstance(payload, (dict, list)):
        return {}, "mailbox_state.json must contain a JSON object or collection"
    return payload, None


def _record_source_id(node: dict) -> str | None:
    value = _field(
        node,
        {
            "source_message_id",
            "source_id",
            "original_message_id",
            "original_id",
            "forwarded_from_id",
            "forward_of",
            "forwarded_message_id",
            "message_source_id",
        },
    )
    return str(value) if value is not None else None


def _find_forward(payload: Any) -> tuple[dict | None, tuple[str, ...], str | None]:
    candidates: list[tuple[int, dict, tuple[str, ...]]] = []
    for node, path in _walk(payload):
        if not isinstance(node, dict):
            continue
        score = 0
        if _record_source_id(node) == TARGET_ID:
            score += 6
        operation = _field(node, {"operation", "action", "kind", "type", "event"})
        if operation is not None and "forward" in _norm_text(operation):
            score += 4
        subject = _field(node, {"subject", "title"})
        if subject is not None and re.match(r"^\s*(fwd?|forward)\s*:", str(subject), re.I):
            score += 3
        if _field(node, {"draft_id", "draftid"}) not in (None, "", False):
            score += 2
        if TARGET_ID in _deep_text(node):
            score += 1
        if score:
            candidates.append((score, node, path))
    if not candidates:
        return None, (), "no forward operation is identifiable after normalizing common field aliases"
    candidates.sort(key=lambda item: item[0], reverse=True)
    best = candidates[0]
    if best[0] < 7:
        return None, (), "the artifact mentions the source but does not identify a usable forward operation"
    return best[1], best[2], None


def _addresses(value: Any) -> set[str]:
    found: set[str] = set()
    if value is None:
        return found
    if isinstance(value, str):
        found.update(
            item.casefold()
            for item in re.findall(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}", value, re.I)
        )
    elif isinstance(value, dict):
        email = _field(value, {"email", "address", "mail"})
        if email is not None:
            found.update(_addresses(email))
        else:
            for nested in value.values():
                found.update(_addresses(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_addresses(nested))
    return found


def _recipient_field(record: dict, kind: str) -> set[str]:
    aliases = {
        "to": {"to", "to_addresses", "to_recipients", "recipients_to"},
        "cc": {"cc", "cc_addresses", "cc_recipients", "recipients_cc"},
        "bcc": {"bcc", "bcc_addresses", "bcc_recipients", "recipients_bcc"},
    }[kind]
    value = _field(record, aliases)
    if value is None:
        recipients = _field(record, {"recipients", "addressees", "routing"})
        if isinstance(recipients, dict):
            value = _field(recipients, aliases | {kind})
    return _addresses(value)


def _status(record: dict, path: tuple[str, ...]) -> str:
    raw = _field(record, {"status", "state", "delivery_status", "message_state"})
    status = _norm_key(raw) if raw is not None else ""
    if not status and _field(record, {"is_draft", "draft"}) is True:
        status = "draft"
    if not status and _field(record, {"draft_id", "draftid"}) not in (None, "", False):
        status = "draft"
    if not status and any("draft" in _norm_key(part) for part in path):
        status = "draft"
    return status


def _forward_was_sent(payload: Any) -> bool:
    for node, path in _walk(payload):
        if not isinstance(node, dict):
            continue
        text = _deep_text(node)
        if TARGET_ID not in text or "forward" not in text:
            continue
        state = _field(node, {"status", "state", "delivery_status", "message_state"})
        if state is not None and _norm_key(state) in {"sent", "delivered", "transmitted"}:
            return True
        if any(_norm_key(part) in {"sent", "sentmessages", "delivered", "outbox"} for part in path):
            return True
    return False


def _attachment_items(record: dict) -> list[Any]:
    value = _field(record, {"attachments", "files", "enclosures", "file_items", "attached_files"})
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return [value]


def _attachment_name(item: Any) -> str:
    if isinstance(item, str):
        return Path(item).name.casefold()
    if isinstance(item, dict):
        value = _field(item, {"filename", "file_name", "name", "path", "local_path"})
        return Path(str(value)).name.casefold() if value is not None else ""
    return ""


def test_source_message_and_recipients():
    payload, error = _load_submission()
    assert error is None, error
    record, _, forward_error = _find_forward(payload)
    assert forward_error is None and record is not None, forward_error
    assert _record_source_id(record) == TARGET_ID, (
        "the forward does not identify msg-8f3c91d0a7b2 as its source; this risks using the earlier revision or look-alike sender"
    )
    assert _recipient_field(record, "to") == EXPECTED_TO, "the To recipients do not exactly match Mina Chen and Devon Lee"
    assert _recipient_field(record, "cc") == EXPECTED_CC, "the Cc recipient is not exactly Procurement Archive"
    assert not _recipient_field(record, "bcc"), "the handoff did not authorize any Bcc recipient"


def test_draft_only_state_transition():
    payload, error = _load_submission()
    assert error is None, error
    record, path, forward_error = _find_forward(payload)
    assert forward_error is None and record is not None, forward_error
    assert _status(record, path) == "draft", "the forward is not clearly stored as a draft for Aisha's review"
    from_addresses = _addresses(_field(record, {"from", "sender", "from_address", "account"}))
    assert not from_addresses or from_addresses == {ACCOUNT}, "the draft uses an unauthorized send-as identity"
    assert not _forward_was_sent(payload), "the mailbox state indicates that the forward was sent or delivered"


def test_note_and_forwarded_original_context():
    payload, error = _load_submission()
    assert error is None, error
    record, _, forward_error = _find_forward(payload)
    assert forward_error is None and record is not None, forward_error
    note = _field(record, {"note", "intro", "comment", "forward_note", "message_note"})
    note_text = _norm_text(
        note if note is not None else _field(record, {"body", "body_text", "content", "text"})
    )
    for fragment in ("thursday's review", "carton minimums", "15:00 wednesday"):
        assert fragment in note_text, f"the requested opening note is missing the material phrase: {fragment}"
    direct_subject = _norm_text(_field(record, {"subject", "title"}))
    assert re.match(r"^f(orward|wd)?\s*:", direct_subject), "the draft subject does not identify the message as a forward"
    context = _deep_text(record)
    for fragment in (
        "lina.ortiz@northstar-packaging.test",
        "harborlight retail kit",
        "final pricing package",
        "section 3",
        "launch volumes",
    ):
        assert fragment in context, f"the forwarded original context is missing: {fragment}"
    assert "2026-09-08" in context or "sep 8, 2026" in context or "september 8, 2026" in context, (
        "the forwarded original context is missing the source date"
    )
    assert "15:42" in context or "3:42 pm" in context, (
        "the forwarded original context is missing the source time"
    )


def test_only_approved_pricing_attachment():
    payload, error = _load_submission()
    assert error is None, error
    record, _, forward_error = _find_forward(payload)
    assert forward_error is None and record is not None, forward_error
    items = _attachment_items(record)
    names = [_attachment_name(item) for item in items]
    assert names == [ALLOWED_ATTACHMENT], (
        f"the draft must contain only {ALLOWED_ATTACHMENT}; observed attachment names were {names}"
    )
    expected_bytes = (DATA_DIR / "attachments" / "HL-retail-kit-pricing-final.pdf").read_bytes()
    expected_sha = hashlib.sha256(expected_bytes).hexdigest()
    if isinstance(items[0], dict):
        supplied_sha = _field(items[0], {"sha256", "checksum", "digest"})
        supplied_size = _field(items[0], {"size_bytes", "size", "bytes"})
        if supplied_sha is not None:
            assert str(supplied_sha).casefold() == expected_sha, "the attached PDF checksum does not match the bundled final pricing file"
        if supplied_size is not None:
            assert int(supplied_size) == len(expected_bytes), "the attached PDF size does not match the bundled final pricing file"
