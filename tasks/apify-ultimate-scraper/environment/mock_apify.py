#!/usr/bin/env python3
"""A deterministic offline subset of the Apify CLI used by this task."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sys
from pathlib import Path


DATA = Path(os.environ.get("APIFY_MOCK_DATA", "/root/data/mock_apify"))
STATE = Path(os.environ.get("APIFY_MOCK_STATE", f"/tmp/apify-mock-{os.getuid()}"))


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def option(args: list[str], flag: str, default=None):
    if flag not in args:
        return default
    idx = args.index(flag)
    if idx + 1 >= len(args):
        fail(f"missing value for {flag}")
    return args[idx + 1]


def emit(value) -> None:
    print(json.dumps(value, separators=(",", ":")))


def fail(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def read_input(args: list[str]) -> dict:
    path = option(args, "--input-file")
    inline = option(args, "--input")
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    elif inline:
        payload = json.loads(inline)
    else:
        fail("Actor input is required")
    if not isinstance(payload, dict):
        fail("Actor input must be one JSON object")
    return payload


def validate(schema: dict, payload: dict) -> None:
    missing = [key for key in schema.get("required", []) if key not in payload]
    if missing:
        fail("missing required input fields: " + ", ".join(missing))


def stable_ids(actor: str, payload: dict) -> tuple[str, str]:
    raw = actor + "\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:12]
    return f"run_{digest}", f"ds_{digest}"


def save_dataset(dataset_id: str, rows: list[dict]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"{dataset_id}.json").write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")


def dataset(dataset_id: str) -> list[dict]:
    path = STATE / f"{dataset_id}.json"
    if not path.is_file():
        fail(f"dataset not found: {dataset_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_places(payload: dict) -> list[dict]:
    terms = {str(item).strip().casefold() for item in payload["searchStringsArray"]}
    if payload.get("language") != "en":
        fail("this offline fixture supports language=en")
    if "portland" not in str(payload.get("locationQuery", "")).casefold():
        return []
    rows = load("places_source.json")
    matched = [row for row in rows if terms.intersection(tag.casefold() for tag in row["searchTags"])]
    return matched[: int(payload["maxCrawledPlaces"])]


def run_enrichment(payload: dict) -> list[dict]:
    source = dataset(str(payload["datasetId"]))
    cap = int(payload["maxRequestsPerCrawl"])
    contacts = {row["placeId"]: row for row in load("contacts_source.json")}
    enriched = []
    for row in source[:cap]:
        merged = dict(row)
        contact = contacts.get(row["placeId"], {})
        for key in ("domain", "emails", "phones", "linkedInUrl", "twitterUrl"):
            merged[key] = contact.get(key, [] if key in {"emails", "phones"} else None)
        enriched.append(merged)
    return enriched


def actors_info(args: list[str]) -> None:
    if not args:
        fail("actor ID required")
    actor = args[0]
    actors = load("actors.json")
    if actor not in actors:
        fail(f"actor not found: {actor}")
    info = dict(actors[actor])
    info["id"] = actor
    emit(info["inputSchema"] if "--input" in args else info)


def actors_search(args: list[str]) -> None:
    query = " ".join(item for item in args if not item.startswith("--") and not item.isdigit()).casefold()
    actors = load("actors.json")
    items = []
    for actor_id, info in actors.items():
        haystack = f"{actor_id} {info['title']}".casefold()
        if all(token in haystack for token in query.split()):
            items.append({"username": actor_id.split("/", 1)[0], "name": actor_id.split("/", 1)[1], **info})
    limit = int(option(args, "--limit", 10))
    emit({"items": items[:limit]})


def actors_call(args: list[str]) -> None:
    if not args:
        fail("actor ID required")
    actor = args[0]
    payload = read_input(args[1:])
    actors = load("actors.json")
    if actor not in actors:
        fail(f"actor not found: {actor}")
    validate(actors[actor]["inputSchema"], payload)
    if actor == "compass/crawler-google-places":
        rows = run_places(payload)
    elif actor == "compass/enrich-google-maps-dataset-with-contacts":
        rows = run_enrichment(payload)
    else:
        fail("this Actor is catalogued but not runnable in the fixture")
    run_id, dataset_id = stable_ids(actor, payload)
    save_dataset(dataset_id, rows)
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"{run_id}.json").write_text(
        json.dumps({"id": run_id, "status": "SUCCEEDED", "defaultDatasetId": dataset_id, "itemCount": len(rows)}),
        encoding="utf-8",
    )
    emit({"id": run_id, "status": "SUCCEEDED", "defaultDatasetId": dataset_id, "stats": {"durationMillis": 125, "itemCount": len(rows)}})


def datasets_get(args: list[str]) -> None:
    if not args:
        fail("dataset ID required")
    rows = dataset(args[0])
    fmt = option(args, "--format", "json")
    if fmt == "json":
        emit(rows)
    elif fmt == "csv":
        keys = sorted({key for row in rows for key in row})
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value) if isinstance(value, (list, dict)) else value for key, value in row.items()})
        print(buf.getvalue(), end="")
    else:
        fail(f"unsupported format: {fmt}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in {"--version", "-V"}:
        print("apify-cli/1.5.0-mock")
        return
    if args[:2] == ["actors", "info"]:
        actors_info(args[2:])
    elif args[:2] == ["actors", "search"]:
        actors_search(args[2:])
    elif args[:2] == ["actors", "call"]:
        actors_call(args[2:])
    elif args[:2] == ["datasets", "get-items"]:
        datasets_get(args[2:])
    else:
        fail("unsupported offline apify command")


if __name__ == "__main__":
    main()
