#!/usr/bin/env python3
"""Small stateful Airtable-compatible REST fixture for an offline evaluation."""

from __future__ import annotations

import argparse
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE_ID = "appDevTriage01"
TABLE_ID = "tblIssues01"
TABLE_NAME = "Issues"
MAX_PAGE = 100
MAX_BATCH = 10
LOCK = threading.Lock()


def write_json(path: Path, payload: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


class Fixture:
    def __init__(self, initial: Path, schema: Path, state: Path, audit: Path):
        self.initial_path = initial
        self.schema = json.loads(schema.read_text(encoding="utf-8"))
        self.state_path = state
        self.audit_path = audit
        state.parent.mkdir(parents=True, exist_ok=True)
        audit.parent.mkdir(parents=True, exist_ok=True)
        if not state.exists():
            state.write_text(initial.read_text(encoding="utf-8"), encoding="utf-8")

    def load(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        write_json(self.state_path, state)

    def audit(self, entry: dict) -> None:
        entry = {"at": datetime.now(timezone.utc).isoformat(), **entry}
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


class Handler(BaseHTTPRequestHandler):
    server_version = "OfflineAirtable/1.0"

    @property
    def fixture(self) -> Fixture:
        return self.server.fixture  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_payload(self, status: int, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def error(self, status: int, error_type: str, message: str, **audit: object) -> None:
        self.fixture.audit({"method": self.command, "path": self.path, "status": status, **audit})
        self.send_payload(status, {"error": {"type": error_type, "message": message}})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == f"/v0/meta/bases/{BASE_ID}/tables":
            self.fixture.audit({"method": "GET", "path": parsed.path, "status": 200, "operation": "schema"})
            self.send_payload(200, self.fixture.schema)
            return

        table_prefixes = (f"/v0/{BASE_ID}/{TABLE_NAME}", f"/v0/{BASE_ID}/{TABLE_ID}")
        prefix = next((value for value in table_prefixes if path == value or path.startswith(value + "/")), None)
        if prefix is None:
            self.error(404, "MODEL_ID_NOT_FOUND", "Unknown base, table, or route")
            return

        with LOCK:
            state = self.fixture.load()
        if path.startswith(prefix + "/"):
            record_id = unquote(path[len(prefix) + 1 :])
            record = next((row for row in state["records"] if row["id"] == record_id), None)
            if record is None:
                self.error(404, "NOT_FOUND", "Record does not exist", operation="get_record")
                return
            self.fixture.audit({"method": "GET", "path": parsed.path, "status": 200, "operation": "get_record", "record_id": record_id})
            self.send_payload(200, record)
            return

        query = parse_qs(parsed.query)
        try:
            requested_size = int(query.get("pageSize", ["100"])[0])
        except ValueError:
            self.error(422, "INVALID_REQUEST", "pageSize must be an integer", operation="list")
            return
        page_size = max(1, min(requested_size, MAX_PAGE))
        raw_offset = query.get("offset", [""])[0]
        if raw_offset:
            match = re.fullmatch(r"itr_(\d+)", raw_offset)
            if not match:
                self.error(422, "INVALID_OFFSET_VALUE", "The offset token is invalid", operation="list")
                return
            start = int(match.group(1))
        else:
            start = 0

        records = list(state["records"])
        formula = query.get("filterByFormula", [None])[0]
        if formula:
            decoded = unquote(formula)
            match = re.fullmatch(r"\{External ID\}\s*=\s*'([^']+)'", decoded)
            if not match:
                self.error(422, "INVALID_FILTER_BY_FORMULA", "Only exact External ID filters are supported", operation="list")
                return
            wanted = match.group(1)
            records = [row for row in records if row["fields"].get("External ID") == wanted]

        page = records[start : start + page_size]
        payload: dict[str, object] = {"records": page}
        if start + page_size < len(records):
            payload["offset"] = f"itr_{start + page_size}"
        self.fixture.audit(
            {
                "method": "GET",
                "path": parsed.path,
                "status": 200,
                "operation": "list",
                "offset": raw_offset or None,
                "page_size": page_size,
                "returned": len(page),
                "filtered": bool(formula),
            }
        )
        self.send_payload(200, payload)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        valid_paths = {f"/v0/{BASE_ID}/{TABLE_NAME}", f"/v0/{BASE_ID}/{TABLE_ID}"}
        if parsed.path.rstrip("/") not in valid_paths:
            self.error(404, "MODEL_ID_NOT_FOUND", "Batch upserts are only supported on the Issues table")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self.error(400, "INVALID_REQUEST", "Request body must be valid JSON", operation="upsert")
            return

        merge_fields = payload.get("performUpsert", {}).get("fieldsToMergeOn") if isinstance(payload, dict) else None
        records = payload.get("records") if isinstance(payload, dict) else None
        if merge_fields != ["External ID"]:
            self.error(422, "INVALID_REQUEST", "performUpsert must merge on External ID", operation="upsert", merge_fields=merge_fields)
            return
        if not isinstance(records, list) or not records:
            self.error(422, "INVALID_REQUEST", "records must be a non-empty list", operation="upsert", merge_fields=merge_fields)
            return
        if len(records) > MAX_BATCH:
            self.error(422, "INVALID_REQUEST", "A batch may contain at most 10 records", operation="upsert", merge_fields=merge_fields, batch_size=len(records))
            return

        schema_fields = {field["name"]: field for field in self.fixture.schema["tables"][0]["fields"]}
        allowed = set(schema_fields)
        seen_ids: set[str] = set()
        normalized: list[dict] = []
        for item in records:
            fields = item.get("fields") if isinstance(item, dict) else None
            if not isinstance(fields, dict) or not isinstance(fields.get("External ID"), str) or not fields["External ID"]:
                self.error(422, "INVALID_REQUEST", "Every upsert record needs fields.External ID", operation="upsert", merge_fields=merge_fields, batch_size=len(records))
                return
            unknown = set(fields) - allowed
            if unknown:
                self.error(422, "UNKNOWN_FIELD_NAME", f"Unknown fields: {sorted(unknown)}", operation="upsert", merge_fields=merge_fields, batch_size=len(records))
                return
            external_id = fields["External ID"]
            if external_id in seen_ids:
                self.error(422, "INVALID_REQUEST", "Duplicate merge values within one request", operation="upsert", merge_fields=merge_fields, batch_size=len(records))
                return
            seen_ids.add(external_id)
            for field_name, field in schema_fields.items():
                if field.get("type") != "singleSelect" or field_name not in fields:
                    continue
                choices = {choice["name"] for choice in field["options"]["choices"]}
                if fields[field_name] not in choices:
                    self.error(422, "INVALID_MULTIPLE_CHOICE_OPTIONS", f"Invalid choice for {field_name}", operation="upsert", merge_fields=merge_fields, batch_size=len(records))
                    return
            normalized.append(fields)

        with LOCK:
            state = self.fixture.load()
            by_external = {row["fields"].get("External ID"): row for row in state["records"]}
            response_records = []
            created_ids = []
            updated_ids = []
            for fields in normalized:
                external_id = fields["External ID"]
                if external_id in by_external:
                    record = by_external[external_id]
                    record["fields"].update(fields)
                    updated_ids.append(record["id"])
                else:
                    number = int(state["next_record_number"])
                    state["next_record_number"] = number + 1
                    record = {
                        "id": f"rec{number:014d}",
                        "createdTime": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                        "fields": dict(fields),
                    }
                    state["records"].append(record)
                    by_external[external_id] = record
                    created_ids.append(record["id"])
                response_records.append(record)
            self.fixture.save(state)

        self.fixture.audit(
            {
                "method": "PATCH",
                "path": parsed.path,
                "status": 200,
                "operation": "upsert",
                "merge_fields": merge_fields,
                "batch_size": len(records),
                "external_ids": [fields["External ID"] for fields in normalized],
                "created": len(created_ids),
                "updated": len(updated_ids),
            }
        )
        self.send_payload(200, {"records": response_records, "createdRecords": created_ids, "updatedRecords": updated_ids})


def main() -> None:
    parser = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    parser.add_argument("--initial", type=Path, default=here / "initial_base.json")
    parser.add_argument("--schema", type=Path, default=here / "schema.json")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.fixture = Fixture(args.initial, args.schema, args.state, args.audit)  # type: ignore[attr-defined]
    server.serve_forever()


if __name__ == "__main__":
    main()
