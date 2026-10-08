#!/usr/bin/env python3
"""Offline mock of `gws gmail +forward` for the frozen task mailbox."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sys
from copy import deepcopy
from pathlib import Path


VERSION = "0.22.5-offline"
DATA_DIR = Path(os.environ.get("GWS_MOCK_DATA_DIR", "/root/data"))
OUTPUT_PATH = Path(os.environ.get("GWS_MOCK_OUTPUT", "/root/results/mailbox_state.json"))
EMAIL_RE = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")


def fail(message: str, code: int = 2) -> int:
    print(message, file=sys.stderr)
    return code


def help_text() -> str:
    return """gws gmail +forward --message-id <ID> --to <EMAILS> [flags]

Offline Gmail forward simulator. Supported flags:
  --message-id ID               Gmail message ID to forward
  --to EMAILS                   comma-separated recipients
  --cc EMAILS                   comma-separated Cc recipients
  --bcc EMAILS                  comma-separated Bcc recipients
  --from EMAIL                  send-as address (default: mailbox account)
  --body TEXT                   note above the forwarded message
  --html                        treat body as an HTML fragment
  --no-original-attachments     omit every original file attachment
  -a, --attach PATH             add a local file; repeatable
  --draft                       save as a draft instead of sending
  --dry-run                     validate and print the request without changing state
"""


def parse(argv: list[str]) -> tuple[dict, str | None]:
    scalar = {"--message-id": "message_id", "--to": "to", "--cc": "cc", "--bcc": "bcc", "--from": "from", "--body": "body"}
    flags = {"--html": "html", "--no-original-attachments": "no_original_attachments", "--draft": "draft", "--dry-run": "dry_run"}
    result: dict[str, object] = {"attach": []}
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in scalar:
            if i + 1 >= len(argv):
                return {}, f"{token} requires a value"
            result[scalar[token]] = argv[i + 1]
            i += 2
        elif token in ("-a", "--attach"):
            if i + 1 >= len(argv):
                return {}, f"{token} requires a path"
            result["attach"].append(argv[i + 1])
            i += 2
        elif token in flags:
            result[flags[token]] = True
            i += 1
        elif token in ("--format", "--sanitize"):
            if i + 1 >= len(argv):
                return {}, f"{token} requires a value"
            result[token[2:].replace("-", "_")] = argv[i + 1]
            i += 2
        else:
            return {}, f"unsupported flag for offline +forward: {token}"
    return result, None


def addresses(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    seen: set[str] = set()
    parsed: list[str] = []
    for raw in value.split(","):
        email = raw.strip().casefold()
        if email and email not in seen:
            parsed.append(email)
            seen.add(email)
    return parsed


def forward_block(message: dict) -> str:
    sender = message["sender"]
    to_line = ", ".join(message.get("to", []))
    cc_line = ", ".join(message.get("cc", []))
    lines = [
        "---------- Forwarded message ---------",
        f"From: {sender['name']} <{sender['email']}>",
        f"Date: {message['received_at']}",
        f"Subject: {message['subject']}",
        f"To: {to_line}",
    ]
    if cc_line:
        lines.append(f"Cc: {cc_line}")
    lines.extend(["", message["body_text"]])
    return "\n".join(lines)


def attached_file(path_text: str) -> tuple[dict | None, str | None]:
    path = Path(path_text)
    if not path.is_file():
        return None, f"attachment does not exist: {path_text}"
    payload = path.read_bytes()
    return {
        "attachment_id": f"local-{hashlib.sha256(payload).hexdigest()[:16]}",
        "filename": path.name,
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source": "user_attachment",
    }, None


def main(argv: list[str]) -> int:
    if argv in (["--version"], ["version"]):
        print(f"gws {VERSION}")
        return 0
    if not argv or "--help" in argv or "-h" in argv:
        print(help_text())
        return 0
    if argv[:2] != ["gmail", "+forward"]:
        return fail("unsupported offline gws command; this fixture provides gmail +forward only")
    options, error = parse(argv[2:])
    if error:
        return fail(error)
    if not options.get("message_id") or not options.get("to"):
        return fail("--message-id and --to are required")

    to = addresses(options.get("to"))
    cc = addresses(options.get("cc"))
    bcc = addresses(options.get("bcc"))
    all_addresses = to + cc + bcc
    if not to or any(not EMAIL_RE.match(email) for email in all_addresses):
        return fail("recipient list contains an invalid email address")
    if len(set(all_addresses)) != len(all_addresses):
        return fail("a recipient may not appear in more than one recipient field")

    mailbox_path = DATA_DIR / "mailbox.json"
    mailbox = json.loads(mailbox_path.read_text(encoding="utf-8"))
    matches = [item for item in mailbox["messages"] if item.get("id") == options["message_id"]]
    if len(matches) != 1:
        return fail(f"message ID was not found exactly once: {options['message_id']}")
    original = matches[0]

    new_attachments: list[dict] = []
    if not options.get("no_original_attachments"):
        for item in original.get("attachments", []):
            copied = deepcopy(item)
            copied["source"] = "original_message"
            new_attachments.append(copied)
    for path_text in options["attach"]:
        item, attachment_error = attached_file(path_text)
        if attachment_error:
            return fail(attachment_error)
        new_attachments.append(item)
    if sum(int(item.get("size_bytes", 0)) for item in new_attachments) > 25 * 1024 * 1024:
        return fail("combined attachment size exceeds Gmail's 25MB limit")

    note = str(options.get("body", ""))
    forwarded = forward_block(original)
    body = f"{note}\n\n{forwarded}" if note else forwarded
    record = {
        "id": "msg-forward-0001",
        "draft_id": "draft-forward-0001" if options.get("draft") else None,
        "operation": "forward",
        "status": "draft" if options.get("draft") else "sent",
        "source_message_id": original["id"],
        "source_thread_id": original["thread_id"],
        "from": str(options.get("from") or mailbox["account"]["email"]).casefold(),
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": original["subject"] if original["subject"].casefold().startswith("fwd:") else f"Fwd: {original['subject']}",
        "note": note,
        "body_format": "html" if options.get("html") else "plain_text",
        "body": body,
        "original_snapshot": deepcopy(original),
        "attachments": new_attachments,
    }
    if options.get("dry_run"):
        print(json.dumps({"dry_run": True, "forward": record}, ensure_ascii=False, indent=2))
        return 0

    result = deepcopy(mailbox)
    result["operation_log"] = [
        {
            "operation": "gmail_forward",
            "source_message_id": original["id"],
            "result_message_id": record["id"],
            "state": record["status"],
        }
    ]
    if options.get("draft"):
        result.setdefault("drafts", []).append(record)
    else:
        result.setdefault("sent_messages", []).append(record)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"id": record["id"], "status": record["status"], "output": str(OUTPUT_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
