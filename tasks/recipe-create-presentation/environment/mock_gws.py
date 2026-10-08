#!/usr/bin/env python3
"""Small deterministic offline subset of the Google Workspace CLI."""

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DATA_DIR = Path(os.environ.get("GWS_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("GWS_RESULTS_DIR", "/root/results"))
STATE_PATH = RESULTS_DIR / "workspace_state.json"
ACTIVITY_PATH = RESULTS_DIR / "activity_log.jsonl"


HELP = """Offline gws mock

Supported commands:
  gws slides presentations create --json JSON
  gws slides presentations get --params JSON
  gws slides presentations batchUpdate --params JSON --json JSON
  gws drive permissions create --params JSON --json JSON
  gws drive permissions list --params JSON

The state is initialized from /root/data/workspace_seed.json and persisted under
/root/results. Use role=writer for editor access.
"""


class CliError(Exception):
    pass


def fail(message: str, code: int = 2) -> int:
    print(json.dumps({"error": {"message": message}}, indent=2), file=sys.stderr)
    return code


def parse_options(items: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    index = 0
    while index < len(items):
        item = items[index]
        if not item.startswith("--"):
            raise CliError(f"unexpected argument: {item}")
        if "=" in item:
            key, value = item[2:].split("=", 1)
            options[key] = value
            index += 1
        else:
            key = item[2:]
            if index + 1 >= len(items):
                raise CliError(f"missing value for --{key}")
            options[key] = items[index + 1]
            index += 2
    return options


def json_option(options: dict[str, str], name: str, *, required: bool = True) -> dict[str, Any]:
    raw = options.get(name)
    if raw is None:
        if required:
            raise CliError(f"--{name} is required")
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"--{name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise CliError(f"--{name} must be a JSON object")
    return value


def load_state() -> dict[str, Any]:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    seed_path = DATA_DIR / "workspace_seed.json"
    if not seed_path.is_file():
        raise CliError(f"workspace seed not found: {seed_path}")
    return copy.deepcopy(json.loads(seed_path.read_text(encoding="utf-8")))


def save_state(state: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, STATE_PATH)


def event_time(state: dict[str, Any]) -> str:
    base = datetime.fromisoformat(state["clock"].replace("Z", "+00:00"))
    moment = base + timedelta(minutes=len(state.get("events", [])))
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def append_event(state: dict[str, Any], action: str, **fields: Any) -> None:
    event = {
        "sequence": len(state.setdefault("events", [])) + 1,
        "timestamp": event_time(state),
        "action": action,
        **fields,
    }
    state["events"].append(event)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with ACTIVITY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def find_presentation(state: dict[str, Any], presentation_id: str) -> dict[str, Any]:
    for presentation in state.get("presentations", []):
        if presentation.get("presentationId") == presentation_id:
            return presentation
    raise CliError(f"presentation not found: {presentation_id}")


def ensure_unique_object_id(presentation: dict[str, Any], object_id: str) -> None:
    used: set[str] = set()
    for slide in presentation.get("slides", []):
        used.add(str(slide.get("objectId", "")))
        for element in slide.get("pageElements", []):
            used.add(str(element.get("objectId", "")))
    if object_id in used:
        raise CliError(f"objectId already exists: {object_id}")


def presentations_create(body: dict[str, Any]) -> dict[str, Any]:
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        raise CliError("title is required")
    state = load_state()
    number = int(state["next_presentation_number"])
    presentation_id = f"prs_{number:04d}"
    state["next_presentation_number"] = number + 1
    slide_id = f"slide_{presentation_id}_1"
    presentation = {
        "presentationId": presentation_id,
        "title": title.strip(),
        "createdAt": event_time(state),
        "slides": [
            {
                "objectId": slide_id,
                "layout": "TITLE",
                "pageElements": [
                    {
                        "objectId": f"{slide_id}_title",
                        "placeholderType": "TITLE",
                        "text": "",
                    },
                    {
                        "objectId": f"{slide_id}_subtitle",
                        "placeholderType": "SUBTITLE",
                        "text": "",
                    },
                ],
            }
        ],
    }
    state.setdefault("presentations", []).append(presentation)
    append_event(state, "slides.presentations.create", presentationId=presentation_id)
    save_state(state)
    return copy.deepcopy(presentation)


def presentations_get(params: dict[str, Any]) -> dict[str, Any]:
    presentation_id = params.get("presentationId")
    if not isinstance(presentation_id, str):
        raise CliError("presentationId is required")
    return copy.deepcopy(find_presentation(load_state(), presentation_id))


def make_slide(presentation: dict[str, Any], request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    object_id = request.get("objectId") or f"slide_{presentation['presentationId']}_{len(presentation['slides']) + 1}"
    if not isinstance(object_id, str) or not object_id:
        raise CliError("createSlide.objectId must be a non-empty string")
    ensure_unique_object_id(presentation, object_id)
    layout_ref = request.get("slideLayoutReference", {})
    layout = layout_ref.get("predefinedLayout", "BLANK") if isinstance(layout_ref, dict) else "BLANK"
    mappings = request.get("placeholderIdMappings", [])
    if not isinstance(mappings, list):
        raise CliError("placeholderIdMappings must be a list")
    elements: list[dict[str, Any]] = []
    mapped_ids: dict[str, str] = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise CliError("placeholderIdMappings entries must be objects")
        placeholder = mapping.get("layoutPlaceholder", {})
        placeholder_type = placeholder.get("type") if isinstance(placeholder, dict) else None
        element_id = mapping.get("objectId")
        if not isinstance(placeholder_type, str) or not isinstance(element_id, str):
            raise CliError("each placeholder mapping needs layoutPlaceholder.type and objectId")
        ensure_unique_object_id(presentation, element_id)
        if element_id in mapped_ids.values():
            raise CliError(f"duplicate mapped objectId: {element_id}")
        mapped_ids[placeholder_type] = element_id
        elements.append({"objectId": element_id, "placeholderType": placeholder_type, "text": ""})
    if not elements:
        default_types = {
            "TITLE": ["TITLE", "SUBTITLE"],
            "TITLE_AND_BODY": ["TITLE", "BODY"],
        }.get(str(layout), [])
        for placeholder_type in default_types:
            element_id = f"{object_id}_{placeholder_type.lower()}"
            ensure_unique_object_id(presentation, element_id)
            mapped_ids[placeholder_type] = element_id
            elements.append({"objectId": element_id, "placeholderType": placeholder_type, "text": ""})
    slide = {"objectId": object_id, "layout": layout, "pageElements": elements}
    insertion_index = request.get("insertionIndex")
    if insertion_index is None:
        presentation.setdefault("slides", []).append(slide)
    elif isinstance(insertion_index, int) and 0 <= insertion_index <= len(presentation.get("slides", [])):
        presentation["slides"].insert(insertion_index, slide)
    else:
        raise CliError("createSlide.insertionIndex is outside the valid range")
    return slide, {"objectId": object_id, "placeholderObjectIds": mapped_ids}


def find_text_element(presentation: dict[str, Any], object_id: str) -> dict[str, Any]:
    for slide in presentation.get("slides", []):
        for element in slide.get("pageElements", []):
            if element.get("objectId") == object_id:
                return element
    raise CliError(f"text object not found: {object_id}")


def presentations_batch_update(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    presentation_id = params.get("presentationId")
    requests = body.get("requests")
    if not isinstance(presentation_id, str):
        raise CliError("presentationId is required")
    if not isinstance(requests, list) or not requests:
        raise CliError("requests must be a non-empty list")
    state = load_state()
    presentation = find_presentation(state, presentation_id)
    replies: list[dict[str, Any]] = []
    for request in requests:
        if not isinstance(request, dict) or len(request) != 1:
            raise CliError("each batch request must contain one operation")
        operation, payload = next(iter(request.items()))
        if not isinstance(payload, dict):
            raise CliError(f"{operation} must be an object")
        if operation == "createSlide":
            _, created = make_slide(presentation, payload)
            replies.append({"createSlide": created})
        elif operation == "insertText":
            object_id = payload.get("objectId")
            text = payload.get("text")
            if not isinstance(object_id, str) or not isinstance(text, str):
                raise CliError("insertText needs objectId and string text")
            element = find_text_element(presentation, object_id)
            index = payload.get("insertionIndex", len(element.get("text", "")))
            if not isinstance(index, int) or not 0 <= index <= len(element.get("text", "")):
                raise CliError("insertText.insertionIndex is outside the valid range")
            current = element.get("text", "")
            element["text"] = current[:index] + text + current[index:]
            replies.append({"insertText": {"objectId": object_id}})
        elif operation == "deleteObject":
            object_id = payload.get("objectId")
            slides = presentation.get("slides", [])
            before = len(slides)
            presentation["slides"] = [slide for slide in slides if slide.get("objectId") != object_id]
            if len(presentation["slides"]) == before:
                raise CliError(f"slide object not found: {object_id}")
            replies.append({"deleteObject": {"objectId": object_id}})
        else:
            raise CliError(f"unsupported batch operation: {operation}")
    append_event(
        state,
        "slides.presentations.batchUpdate",
        presentationId=presentation_id,
        requestCount=len(requests),
    )
    save_state(state)
    return {"presentationId": presentation_id, "replies": replies}


def permissions_create(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    file_id = params.get("fileId")
    role = body.get("role")
    permission_type = body.get("type")
    email = body.get("emailAddress")
    if not isinstance(file_id, str):
        raise CliError("fileId is required")
    if role not in {"reader", "commenter", "writer"}:
        raise CliError("role must be reader, commenter, or writer")
    if permission_type not in {"user", "domain", "anyone"}:
        raise CliError("type must be user, domain, or anyone")
    if permission_type == "user" and (not isinstance(email, str) or "@" not in email):
        raise CliError("a user permission requires emailAddress")
    state = load_state()
    find_presentation(state, file_id)
    number = int(state["next_permission_number"])
    state["next_permission_number"] = number + 1
    permission = {
        "permissionId": f"perm_{number:04d}",
        "fileId": file_id,
        "role": role,
        "type": permission_type,
    }
    if isinstance(email, str):
        permission["emailAddress"] = email.strip().lower()
    state.setdefault("permissions", []).append(permission)
    append_event(
        state,
        "drive.permissions.create",
        fileId=file_id,
        permissionId=permission["permissionId"],
    )
    save_state(state)
    return copy.deepcopy(permission)


def permissions_list(params: dict[str, Any]) -> dict[str, Any]:
    file_id = params.get("fileId")
    if not isinstance(file_id, str):
        raise CliError("fileId is required")
    state = load_state()
    find_presentation(state, file_id)
    return {"permissions": [p for p in state.get("permissions", []) if p.get("fileId") == file_id]}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"--help", "-h", "help"}:
        print(HELP)
        return 0
    if len(argv) < 3:
        return fail("expected SERVICE RESOURCE METHOD; run gws --help")
    service, resource, method = argv[:3]
    try:
        options = parse_options(argv[3:])
        params = json_option(options, "params", required=False)
        body = json_option(options, "json", required=False)
        if (service, resource, method) == ("slides", "presentations", "create"):
            result = presentations_create(body)
        elif (service, resource, method) == ("slides", "presentations", "get"):
            result = presentations_get(params)
        elif (service, resource, method) == ("slides", "presentations", "batchUpdate"):
            result = presentations_batch_update(params, body)
        elif (service, resource, method) == ("drive", "permissions", "create"):
            result = permissions_create(params, body)
        elif (service, resource, method) == ("drive", "permissions", "list"):
            result = permissions_list(params)
        else:
            raise CliError(f"unsupported command: {service} {resource} {method}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CliError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
