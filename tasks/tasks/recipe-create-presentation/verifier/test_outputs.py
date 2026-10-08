from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
STATE_PATH = RESULTS_DIR / "workspace_state.json"
RECEIPT_PATH = RESULTS_DIR / "creation_receipt.json"


def load_json(path: Path) -> Any:
    assert path.is_file(), f"required artifact is missing: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AssertionError(f"artifact is not readable JSON: {path}: {exc}") from exc


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.replace("–", "-").replace("—", "-").replace("→", " to ")
    return re.sub(r"\s+", " ", text).strip()


def key_norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", norm(value))


def get_alias(mapping: dict[str, Any], *aliases: str, default: Any = None) -> Any:
    wanted = {key_norm(alias) for alias in aliases}
    for key, value in mapping.items():
        if key_norm(key) in wanted:
            return value
    return default


def deep_find_collection(value: Any, aliases: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if key_norm(key) in aliases and isinstance(item, (list, dict)):
                return item
        for item in value.values():
            found = deep_find_collection(item, aliases)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = deep_find_collection(item, aliases)
            if found is not None:
                return found
    return None


def as_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        records = []
        for record_id, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                if get_alias(row, "presentationId", "presentation_id", "id") is None:
                    row["id"] = record_id
                records.append(row)
        return records
    return []


def presentations(state: Any) -> list[dict[str, Any]]:
    collection = deep_find_collection(state, {"presentations", "decks"})
    rows = as_records(collection)
    assert rows, "workspace state does not expose any presentation records"
    return rows


def presentation_id(row: dict[str, Any]) -> str:
    return str(get_alias(row, "presentationId", "presentation_id", "deckId", "id", default=""))


def presentation_title(row: dict[str, Any]) -> str:
    return str(get_alias(row, "title", "name", "presentationTitle", default=""))


def slide_records(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = get_alias(row, "slides", "pages", default=[])
    return as_records(value)


def collect_content_text(value: Any, *, parent_key: str = "") -> list[str]:
    allowed_scalars = {
        "text",
        "content",
        "title",
        "subtitle",
        "body",
        "bullets",
        "bullet",
        "paragraphs",
        "runs",
    }
    output: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            output.extend(collect_content_text(item, parent_key=key_norm(key)))
    elif isinstance(value, list):
        for item in value:
            output.extend(collect_content_text(item, parent_key=parent_key))
    elif value is not None and (parent_key in allowed_scalars or parent_key.endswith("text")):
        output.append(str(value))
    return output


def slide_text(slide: dict[str, Any]) -> str:
    return norm("\n".join(collect_content_text(slide)))


def scalar_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            values.extend(scalar_strings(item))
    elif isinstance(value, list):
        for item in value:
            values.extend(scalar_strings(item))
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        values.append(norm(value))
    return values


def find_new_presentation(state: Any, seed: Any) -> dict[str, Any]:
    existing_ids = {presentation_id(row) for row in presentations(seed)}
    new_rows = [row for row in presentations(state) if presentation_id(row) not in existing_ids]
    assert len(new_rows) == 1, (
        f"expected exactly one newly created presentation, found {len(new_rows)}; "
        "the request was for a fresh deck without altering or duplicating other workspace files"
    )
    return new_rows[0]


def permission_records(state: Any) -> list[dict[str, Any]]:
    collection = deep_find_collection(state, {"permissions", "sharing", "shares"})
    return as_records(collection)


def permission_signature(permission: dict[str, Any]) -> tuple[str, str, str, str]:
    file_id = get_alias(permission, "fileId", "file_id", "presentationId", "presentation_id", default="")
    email = get_alias(permission, "emailAddress", "email", "user", default="")
    role = get_alias(permission, "role", "accessRole", "access", default="")
    permission_type = get_alias(permission, "type", "permissionType", "principalType", default="")
    return norm(file_id), norm(email), norm(role), norm(permission_type)


def test_new_presentation_identity() -> None:
    state = load_json(STATE_PATH)
    seed = load_json(DATA_DIR / "workspace_seed.json")
    brief = load_json(DATA_DIR / "launch_brief.json")
    created = find_new_presentation(state, seed)
    assert presentation_title(created) == brief["presentation"]["title"], (
        "the newly created presentation does not have the requested title"
    )

    actual_by_id = {presentation_id(row): row for row in presentations(state)}
    for old in presentations(seed):
        old_id = presentation_id(old)
        assert old_id in actual_by_id, f"existing presentation {old_id} was removed"
        actual = actual_by_id[old_id]
        assert norm(presentation_title(actual)) == norm(presentation_title(old)), (
            f"existing presentation {old_id} was renamed instead of leaving it intact"
        )
        assert [slide_text(s) for s in slide_records(actual)] == [
            slide_text(s) for s in slide_records(old)
        ], f"existing presentation {old_id} was edited instead of creating a fresh deck"


def test_initial_slide_content() -> None:
    state = load_json(STATE_PATH)
    seed = load_json(DATA_DIR / "workspace_seed.json")
    brief = load_json(DATA_DIR / "launch_brief.json")
    created = find_new_presentation(state, seed)
    actual_slides = slide_records(created)
    expected_slides = brief["presentation"]["slides"]
    assert len(actual_slides) == len(expected_slides), (
        f"new deck has {len(actual_slides)} slides, expected {len(expected_slides)} initial slides"
    )

    for position, (actual, expected) in enumerate(zip(actual_slides, expected_slides), start=1):
        actual_text = slide_text(actual)
        required = [expected["title"]]
        if "subtitle" in expected:
            required.append(expected["subtitle"])
        required.extend(expected.get("bullets", []))
        missing = [piece for piece in required if norm(piece) not in actual_text]
        assert not missing, (
            f"slide {position} is missing brief content: {missing}; the kickoff facts would be incomplete"
        )
        assert actual_text, f"slide {position} is blank and not usable in the kickoff"


def test_editor_permission() -> None:
    state = load_json(STATE_PATH)
    seed = load_json(DATA_DIR / "workspace_seed.json")
    brief = load_json(DATA_DIR / "launch_brief.json")
    created = find_new_presentation(state, seed)
    new_id = norm(presentation_id(created))
    target = brief["sharing"]
    signatures = [permission_signature(row) for row in permission_records(state)]

    target_matches = [
        sig
        for sig in signatures
        if sig[0] == new_id
        and sig[1] == norm(target["email"])
        and sig[2] in {"writer", "editor"}
        and sig[3] in {"user", "individual"}
    ]
    assert target_matches, (
        "the pilot operations address does not have user-level editor access on the new presentation"
    )
    unsafe = [sig for sig in signatures if sig[0] == new_id and sig[3] in {"anyone", "domain", "public"}]
    assert not unsafe, "the new deck was shared more broadly than the requested individual editor access"

    seed_signatures = {permission_signature(row) for row in permission_records(seed)}
    actual_existing = {sig for sig in signatures if sig[0] in {item[0] for item in seed_signatures}}
    assert actual_existing == seed_signatures, (
        "permissions on an existing presentation were changed while fulfilling the new-deck request"
    )


def test_confirmation_receipt() -> None:
    receipt = load_json(RECEIPT_PATH)
    state = load_json(STATE_PATH)
    seed = load_json(DATA_DIR / "workspace_seed.json")
    brief = load_json(DATA_DIR / "launch_brief.json")
    created = find_new_presentation(state, seed)
    values = set(scalar_strings(receipt))
    new_id = norm(presentation_id(created))
    assert new_id in values, "creation confirmation does not identify the newly created presentation"
    assert norm(brief["sharing"]["email"]) in values, (
        "creation confirmation does not identify the editor who received access"
    )
    assert values.intersection({"writer", "editor"}), (
        "creation confirmation does not report that editor access was granted"
    )
    assert any(value.startswith("perm_") for value in values) or values.intersection(
        {"success", "created_and_shared", "shared", "completed"}
    ), "creation confirmation lacks a successful sharing result or permission identifier"
