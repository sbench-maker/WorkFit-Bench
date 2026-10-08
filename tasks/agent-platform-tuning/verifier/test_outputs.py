from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
OUTPUT = Path(os.environ.get("TASK_OUTPUT_DIR", "/root/results/tuning_run"))
PREFIX = "gs://northwind-agent-tuning-eu/tuning_agent_job_20260910T090000Z"
MISSING = object()


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _field(mapping: dict, aliases: tuple[str, ...], default=MISSING):
    wanted = {_token(alias) for alias in aliases}
    for key, value in mapping.items():
        if _token(key) in wanted:
            return value
    if default is MISSING:
        raise KeyError(f"none of {aliases!r} is present")
    return default


def _walk_mappings(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _json_documents() -> list[tuple[Path, object]]:
    documents = []
    if not OUTPUT.is_dir():
        return documents
    for path in OUTPUT.rglob("*.json"):
        try:
            documents.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue
    return documents


def _parse_jsonl(path: Path) -> list[object]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"{path.name} has invalid JSON on line {line_number}: {exc}") from exc
    return rows


def _message_pair(row: object) -> tuple[str, str] | None:
    if not isinstance(row, dict):
        return None
    messages = _field(row, ("messages", "conversation", "turns"), None)
    if isinstance(messages, list):
        users: list[str] = []
        assistants: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                return None
            role = _token(_field(message, ("role", "speaker", "author"), ""))
            content = _field(message, ("content", "text", "message"), None)
            if not isinstance(content, str) or not content.strip():
                return None
            if role in {"user", "human"}:
                users.append(content.strip())
            elif role in {"assistant", "model"}:
                assistants.append(content.strip())
            elif role != "system":
                return None
        if len(users) == 1 and len(assistants) == 1:
            return users[0], assistants[0]
        return None
    prompt = _field(row, ("prompt", "user_message", "input"), None)
    completion = _field(row, ("completion", "assistant_response", "output"), None)
    if isinstance(prompt, str) and prompt.strip() and isinstance(completion, str) and completion.strip():
        return prompt.strip(), completion.strip()
    return None


def _dataset_files() -> tuple[tuple[Path, list[tuple[str, str]]], tuple[Path, list[tuple[str, str]]]]:
    candidates: list[tuple[Path, list[tuple[str, str]]]] = []
    if not OUTPUT.is_dir():
        raise AssertionError(f"requested output directory is missing: {OUTPUT}")
    for path in OUTPUT.rglob("*.jsonl"):
        rows = _parse_jsonl(path)
        if not rows:
            continue
        pairs = [_message_pair(row) for row in rows]
        if all(pair is not None for pair in pairs):
            candidates.append((path, [pair for pair in pairs if pair is not None]))
    assert len(candidates) == 2, (
        "the run bundle must contain two readable chat-dataset JSONL partitions; "
        f"found {len(candidates)}"
    )
    train_named = [item for item in candidates if "train" in _token(item[0].stem) and "validation" not in _token(item[0].stem)]
    validation_named = [item for item in candidates if any(word in _token(item[0].stem) for word in ("validation", "valid", "holdout", "eval"))]
    if len(train_named) == 1 and len(validation_named) == 1 and train_named[0][0] != validation_named[0][0]:
        return train_named[0], validation_named[0]
    ordered = sorted(candidates, key=lambda item: len(item[1]), reverse=True)
    return ordered[0], ordered[1]


def _expected() -> dict:
    with (DATA / "support_tuning_candidates.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected: dict[str, dict[str, str]] = {}
    for row in rows:
        prompt = row["customer_message"].strip()
        reply = row["approved_reply"].strip()
        if row["review_status"].strip().casefold() != "approved":
            continue
        if not prompt or not reply or prompt.casefold() in {"nan", "none"} or reply.casefold() in {"nan", "none"}:
            continue
        row = {**row, "customer_message": prompt, "approved_reply": reply}
        current = selected.get(prompt)
        candidate_key = (-int(row["review_revision"]), row["example_id"])
        current_key = (-int(current["review_revision"]), current["example_id"]) if current else None
        if current is None or candidate_key < current_key:
            selected[prompt] = row
    curated = sorted(selected.values(), key=lambda row: row["example_id"])
    validation_count = math.floor(len(curated) * 0.20 + 0.5)
    ranked = sorted(
        curated,
        key=lambda row: hashlib.sha256(("nw-support-v1:" + row["example_id"]).encode()).hexdigest(),
    )
    validation_ids = {row["example_id"] for row in ranked[:validation_count]}
    train_pairs = {
        (row["customer_message"], row["approved_reply"])
        for row in curated
        if row["example_id"] not in validation_ids
    }
    validation_pairs = {
        (row["customer_message"], row["approved_reply"])
        for row in curated
        if row["example_id"] in validation_ids
    }
    return {
        "all": train_pairs | validation_pairs,
        "train": train_pairs,
        "validation": validation_pairs,
    }


def _contract() -> dict:
    return json.loads((DATA / "mock_cloud_snapshot.json").read_text(encoding="utf-8"))["model_contract"]


def _find_request() -> tuple[Path, dict]:
    aliases = {
        "base_model": ("base_model", "base_model_id", "model_id"),
        "train_dataset": ("train_dataset", "training_dataset", "train_uri"),
        "output_uri": ("output_uri", "output", "artifact_uri"),
    }
    candidates = []
    for path, document in _json_documents():
        for mapping in _walk_mappings(document):
            score = sum(_field(mapping, names, None) is not None for names in aliases.values())
            if score >= 2:
                candidates.append((score, path, mapping))
    assert candidates, "no usable tuning request object was found in the run bundle"
    _, path, mapping = max(candidates, key=lambda item: item[0])
    return path, mapping


def _request_value(request: dict, name: str):
    aliases = {
        "project": ("project", "project_id"),
        "location": ("location", "region"),
        "base_model": ("base_model", "base_model_id", "model_id"),
        "train_dataset": ("train_dataset", "training_dataset", "train_uri"),
        "validation_dataset": ("validation_dataset", "validation_uri", "eval_dataset"),
        "output_uri": ("output_uri", "artifact_uri", "output"),
        "epochs": ("epochs", "epoch_count", "num_epochs"),
        "learning_rate": ("learning_rate", "lr"),
        "tuning_mode": ("tuning_mode", "mode"),
        "adapter_size": ("adapter_size", "adapter_rank", "rank"),
    }
    return _field(request, aliases[name], None)


def _find_cost() -> float:
    aliases = ("estimated_cost_usd", "estimated_training_cost_usd", "cost_estimate_usd", "estimated_cost", "cost_usd")
    for _, document in _json_documents():
        for mapping in _walk_mappings(document):
            value = _field(mapping, aliases, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            if isinstance(value, str):
                match = re.fullmatch(r"\s*\$?\s*([0-9]+(?:\.[0-9]+)?)\s*", value)
                if match:
                    return float(match.group(1))
    for path in OUTPUT.rglob("*") if OUTPUT.is_dir() else []:
        if path.is_file() and path.suffix.casefold() in {".md", ".txt"}:
            match = re.search(r"estimated[^\n$]{0,80}\$\s*([0-9]+(?:\.[0-9]+)?)", path.read_text(encoding="utf-8"), re.I)
            if match:
                return float(match.group(1))
    raise AssertionError("no machine-readable or clearly labeled estimated USD cost was found")


def _find_state() -> dict:
    for _, document in _json_documents():
        for mapping in _walk_mappings(document):
            if isinstance(_field(mapping, ("objects", "uploaded_objects", "storage_objects"), None), dict) and isinstance(
                _field(mapping, ("jobs", "tuning_jobs"), None), dict
            ):
                return mapping
    raise AssertionError("no mock control-plane state with uploaded objects and jobs was found")


def _find_receipt() -> dict:
    candidates = []
    for _, document in _json_documents():
        for mapping in _walk_mappings(document):
            job_id = _field(mapping, ("job_id", "tuning_job_id"), None)
            request_hash = _field(mapping, ("request_sha256", "request_hash"), None)
            if job_id is not None and request_hash is not None:
                candidates.append(mapping)
    assert candidates, "no tuning job receipt was found"
    queued = [row for row in candidates if "queued" in _token(_field(row, ("state", "status"), ""))]
    return queued[0] if queued else candidates[0]


def _monitoring_rows() -> list[dict]:
    candidates = []
    if not OUTPUT.is_dir():
        return []
    for path in OUTPUT.rglob("*.jsonl"):
        rows = _parse_jsonl(path)
        if rows and all(isinstance(row, dict) and _field(row, ("state", "status", "job_state"), None) is not None for row in rows):
            candidates.append(rows)
    assert len(candidates) == 1, f"expected one monitoring event stream, found {len(candidates)}"
    return candidates[0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_curated_chat_records():
    (train_path, train), (validation_path, validation) = _dataset_files()
    expected = _expected()
    observed = train + validation
    assert all(pair[0].casefold() not in {"nan", "none"} and pair[1].casefold() not in {"nan", "none"} for pair in observed), (
        "placeholder content would make the tuning dataset invalid"
    )
    assert Counter(observed) == Counter(expected["all"]), (
        "the prepared partitions must contain every and only the approved, valid, conflict-resolved examples exactly once"
    )
    assert train_path != validation_path


def test_holdout_partition():
    (_, train), (_, validation) = _dataset_files()
    expected = _expected()
    assert set(train).isdisjoint(validation), "training and validation examples overlap, causing holdout leakage"
    assert set(train) == expected["train"], "training membership does not follow the confirmed stable holdout rule"
    assert set(validation) == expected["validation"], "validation membership does not follow the confirmed stable holdout rule"


def test_tuning_configuration():
    _, request = _find_request()
    contract = _contract()
    assert _request_value(request, "project") == "northwind-agent-lab"
    assert _request_value(request, "location") == "europe-west4"
    assert _token(_request_value(request, "base_model")) in {
        _token(contract["base_model"]),
        _token(contract["display_name"]),
    }, "the request does not use the confirmed supported open model"
    assert _token(_request_value(request, "tuning_mode")) in {"peft", "peftadapter", "adapter"}
    assert int(_request_value(request, "epochs")) == contract["epochs"]
    assert math.isclose(float(_request_value(request, "learning_rate")), contract["learning_rate"], rel_tol=0, abs_tol=1e-12)
    assert int(_request_value(request, "adapter_size")) == contract["adapter_size"]
    train_uri = str(_request_value(request, "train_dataset"))
    validation_uri = str(_request_value(request, "validation_dataset"))
    assert train_uri.startswith(PREFIX + "/") and validation_uri.startswith(PREFIX + "/") and train_uri != validation_uri
    assert str(_request_value(request, "output_uri")).rstrip("/") == PREFIX + "/output"


def test_cost_estimate():
    (_, train), _ = _dataset_files()
    _, request = _find_request()
    characters = sum(len(prompt) + len(reply) for prompt, reply in train)
    contract = _contract()
    expected_cost = characters * contract["tokens_per_character"] * int(_request_value(request, "epochs")) / 1_000_000 * contract["cost_per_million_tokens_usd"]
    reported_cost = _find_cost()
    assert math.isclose(reported_cost, expected_cost, rel_tol=0.02, abs_tol=0.005), (
        f"reported cost ${reported_cost:.6f} does not reconcile to the submitted training content (${expected_cost:.6f})"
    )
    assert reported_cost <= 0.05 + 1e-9, "the chosen run exceeds the confirmed $0.05 budget"


def test_mock_submission_and_monitoring():
    (train_path, _), (validation_path, _) = _dataset_files()
    request_path, request = _find_request()
    state = _find_state()
    receipt = _find_receipt()
    objects = _field(state, ("objects", "uploaded_objects", "storage_objects"))
    train_uri = str(_request_value(request, "train_dataset"))
    validation_uri = str(_request_value(request, "validation_dataset"))
    assert train_uri in objects and validation_uri in objects, "both dataset partitions must be uploaded before submission"
    local_by_count = {"train": train_path, "validation": validation_path}
    for label, uri in (("train", train_uri), ("validation", validation_uri)):
        metadata = objects[uri]
        recorded = _field(metadata, ("sha256", "checksum", "digest"), None) if isinstance(metadata, dict) else None
        assert recorded == _sha256(local_by_count[label]), f"uploaded {label} checksum does not match the bundled partition"

    canonical_request = {
        "project": _request_value(request, "project"),
        "location": _request_value(request, "location"),
        "base_model": _request_value(request, "base_model"),
        "train_dataset": train_uri,
        "validation_dataset": validation_uri,
        "output_uri": _request_value(request, "output_uri"),
        "epochs": _request_value(request, "epochs"),
        "learning_rate": _request_value(request, "learning_rate"),
        "tuning_mode": _request_value(request, "tuning_mode"),
        "adapter_size": _request_value(request, "adapter_size"),
    }
    request_hash = hashlib.sha256(json.dumps(canonical_request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt_hash = str(_field(receipt, ("request_sha256", "request_hash"), ""))
    assert receipt_hash == request_hash, "job receipt is not tied to the submitted request"
    job_id = str(_field(receipt, ("job_id", "tuning_job_id")))
    assert job_id == "tune-" + request_hash[:12], "receipt does not identify the deterministic mock job"

    rows = _monitoring_rows()
    states = [_token(_field(row, ("state", "status", "job_state"))) for row in rows]
    assert states == ["jobstatequeued", "jobstaterunning", "jobstatesucceeded"], (
        "monitoring must show the mock job progressing from queued through running to succeeded"
    )
    assert all(str(_field(row, ("job_id", "tuning_job_id"))) == job_id for row in rows)
    times = [datetime.fromisoformat(str(_field(row, ("observed_at", "timestamp", "time"))).replace("Z", "+00:00")) for row in rows]
    assert times == sorted(times) and len(set(times)) == len(times), "monitoring timestamps are not chronological"
    jobs = _field(state, ("jobs", "tuning_jobs"))
    assert job_id in jobs and _token(_field(jobs[job_id], ("state", "status"))) == "jobstatesucceeded"
