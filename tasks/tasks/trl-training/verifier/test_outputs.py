from __future__ import annotations

from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
import subprocess


DATA = Path(os.environ.get("DATA_ROOT", "/root/data"))
BUNDLE = Path(os.environ.get("SUBMISSION_ROOT", "/root/results")) / "dpo_run"
FILES = ("train.jsonl", "eval.jsonl", "dpo_config.yaml", "launch.sh", "preflight_report.json")
MAX_LENGTH = 1024


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def normalize_messages(value: object) -> tuple[tuple[str, str], ...]:
    if isinstance(value, str):
        return (("", normalize_space(value)),)
    if not isinstance(value, list):
        return ()
    normalized = []
    for message in value:
        if not isinstance(message, dict):
            return ()
        normalized.append((normalize_space(message.get("role", "")), normalize_space(message.get("content", ""))))
    return tuple(normalized)


def content_only(value: object) -> str:
    return " ".join(content for _role, content in normalize_messages(value)).strip()


def message_problem(record: dict) -> str | None:
    prompt = record.get("prompt")
    chosen = record.get("chosen")
    rejected = record.get("rejected")
    if any(not isinstance(part, list) or not part for part in (prompt, chosen, rejected)):
        return "invalid_message"
    if any(role not in {"system", "user"} for role, _ in normalize_messages(prompt)):
        return "invalid_message"
    if any(role != "assistant" for part in (chosen, rejected) for role, _ in normalize_messages(part)):
        return "invalid_message"
    if not content_only(prompt) or not content_only(chosen) or not content_only(rejected):
        return "blank_response"
    return None


def expected_outcome() -> tuple[dict[str, dict], dict[str, str], dict[str, str]]:
    raw = [
        json.loads(line)
        for line in (DATA / "raw_preference_pairs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    with (DATA / "prompt_group_assignments.csv").open(encoding="utf-8", newline="") as handle:
        assignments = {row["prompt_group_id"]: row["split"] for row in csv.DictReader(handle)}
    included: dict[str, dict] = {}
    exclusions: dict[str, str] = {}
    seen: set[tuple[str, str, str]] = set()
    for record in sorted(raw, key=lambda item: item["pair_id"]):
        if record.get("consent_for_training") is not True:
            reason = "no_consent"
        elif normalize_space(record.get("review_status", "")) != "approved":
            reason = "not_approved"
        elif (problem := message_problem(record)) is not None:
            reason = problem
        elif content_only(record["chosen"]) == content_only(record["rejected"]):
            reason = "ambiguous_preference"
        elif int(record.get("estimated_tokens", MAX_LENGTH + 1)) > MAX_LENGTH:
            reason = "over_length"
        else:
            signature = (
                content_only(record["prompt"]),
                content_only(record["chosen"]),
                content_only(record["rejected"]),
            )
            if signature in seen:
                reason = "duplicate_content"
            else:
                seen.add(signature)
                reason = None
        if reason:
            exclusions[record["pair_id"]] = reason
        else:
            included[record["pair_id"]] = record
    return included, exclusions, assignments


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise AssertionError(f"{path.name} line {line_number} is not a JSON object")
        rows.append(row)
    return rows


def parse_scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    lowered = value.casefold()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"none", "null", "~"}:
        return None
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def read_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {}
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            assert ":" in line, f"dpo_config.yaml line {line_number} is not a simple YAML mapping entry"
            key, value = line.split(":", 1)
            assert key.strip() and not key.strip().startswith("-"), f"invalid YAML key at line {line_number}"
            payload[key.strip()] = parse_scalar(value)
    assert isinstance(payload, dict), "dpo_config.yaml must contain a mapping"
    return payload


def as_number(config: dict, key: str) -> float:
    try:
        return float(config[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise AssertionError(f"configuration needs numeric {key}") from exc


def bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if value.strip().casefold() in {"true", "yes", "on", "1"}:
            return True
        if value.strip().casefold() in {"false", "no", "off", "0", "none"}:
            return False
    return None


def test_artifact_usability():
    """The contracted handoff files exist, are readable, non-empty, and the launcher is executable."""
    problems = []
    for name in FILES:
        path = BUNDLE / name
        if not path.is_file():
            problems.append(f"missing {name}")
        elif not os.access(path, os.R_OK) or path.stat().st_size == 0:
            problems.append(f"{name} is unreadable or empty")
    launch = BUNDLE / "launch.sh"
    if launch.is_file() and not os.access(launch, os.X_OK):
        problems.append("launch.sh is not executable")
    assert not problems, "; ".join(problems) + "; the training handoff is incomplete"


def test_dataset_selection_and_splits():
    """Prepared data contains exactly the eligible source pairs in their authoritative group split."""
    expected, _exclusions, assignments = expected_outcome()
    try:
        submitted = {"train": read_jsonl(BUNDLE / "train.jsonl"), "eval": read_jsonl(BUNDLE / "eval.jsonl")}
    except (OSError, json.JSONDecodeError, AssertionError) as exc:
        raise AssertionError(f"prepared preference data cannot be read: {exc}") from exc
    actual_by_id: dict[str, tuple[str, dict]] = {}
    problems = []
    for split, rows in submitted.items():
        for row in rows:
            pair_id = row.get("pair_id", row.get("id"))
            if not isinstance(pair_id, str):
                problems.append(f"a {split} row lacks a traceable pair_id")
                continue
            if pair_id in actual_by_id:
                problems.append(f"duplicate submitted pair_id {pair_id}")
                continue
            actual_by_id[pair_id] = (split, row)
    expected_ids = set(expected)
    actual_ids = set(actual_by_id)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing:
        problems.append(f"missing eligible IDs {missing[:8]}{'...' if len(missing) > 8 else ''}")
    if extra:
        problems.append(f"included ineligible IDs {extra[:8]}{'...' if len(extra) > 8 else ''}")
    for pair_id in sorted(expected_ids & actual_ids):
        split, row = actual_by_id[pair_id]
        source = expected[pair_id]
        group_id = row.get("prompt_group_id", row.get("group_id"))
        if group_id != source["prompt_group_id"] or split != assignments[source["prompt_group_id"]]:
            problems.append(f"{pair_id} is assigned to the wrong prompt group or split")
            continue
        for field in ("prompt", "chosen", "rejected"):
            if normalize_messages(row.get(field)) != normalize_messages(source[field]):
                problems.append(f"{pair_id} does not preserve source {field}")
                break
    train_groups = {row.get("prompt_group_id", row.get("group_id")) for row in submitted["train"]}
    eval_groups = {row.get("prompt_group_id", row.get("group_id")) for row in submitted["eval"]}
    if train_groups & eval_groups:
        problems.append("one or more prompt groups leak across train and eval")
    assert not problems, "; ".join(problems[:12])


def test_exclusion_traceability():
    """The preflight report accounts for every source row with the correct primary exclusion reason."""
    expected, exclusions, assignments = expected_outcome()
    try:
        report = json.loads((BUNDLE / "preflight_report.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"preflight_report.json is unavailable or invalid: {exc}") from exc
    assert isinstance(report, dict), "preflight report must be a JSON object"
    entries = report.get("excluded_records", report.get("exclusions"))
    assert isinstance(entries, list), "preflight report needs record-level exclusions"
    actual_exclusions = {}
    for entry in entries:
        assert isinstance(entry, dict), "every exclusion must be an object"
        pair_id = entry.get("pair_id", entry.get("id"))
        reason = entry.get("reason", entry.get("reason_code"))
        assert isinstance(pair_id, str) and isinstance(reason, str), "every exclusion needs an ID and reason"
        assert pair_id not in actual_exclusions, f"exclusion {pair_id} is listed more than once"
        actual_exclusions[pair_id] = normalize_space(reason).replace(" ", "_").replace("-", "_")
    assert actual_exclusions == exclusions, "record-level exclusion decisions or precedence are incorrect"

    included = report.get("included", report.get("included_counts", {}))
    excluded = report.get("excluded", report.get("excluded_counts", {}))
    train_count = sum(assignments[row["prompt_group_id"]] == "train" for row in expected.values())
    eval_count = len(expected) - train_count
    expected_reasons = Counter(exclusions.values())
    assert int(report.get("source_records", report.get("source_count", -1))) == len(expected) + len(exclusions)
    assert isinstance(included, dict) and int(included.get("total", -1)) == len(expected)
    assert int(included.get("train", -1)) == train_count and int(included.get("eval", -1)) == eval_count
    assert isinstance(excluded, dict) and int(excluded.get("total", -1)) == len(exclusions)
    by_reason = excluded.get("by_reason", report.get("exclusion_counts", {}))
    assert {normalize_space(k).replace(" ", "_").replace("-", "_"): int(v) for k, v in by_reason.items()} == dict(
        expected_reasons
    ), "exclusion reason totals do not reconcile with source decisions"
    assert normalize_space(report.get("method", "")) in {"dpo", "direct preference optimization"}


def test_training_configuration():
    """The DPO configuration matches the frozen run settings and resource arithmetic without remote dependencies."""
    config = read_config(BUNDLE / "dpo_config.yaml")
    expected_numbers = {
        "learning_rate": 5e-6,
        "num_train_epochs": 2,
        "num_processes": 2,
        "eval_steps": 25,
        "max_length": 1024,
        "max_prompt_length": 384,
        "beta": 0.1,
        "seed": 7319,
        "lora_r": 16,
        "lora_alpha": 32,
    }
    for key, expected in expected_numbers.items():
        actual = as_number(config, key)
        assert abs(actual - expected) <= max(1e-12, abs(expected) * 1e-9), f"{key} is {actual}, expected {expected}"
    per_device = int(as_number(config, "per_device_train_batch_size"))
    accumulation = int(as_number(config, "gradient_accumulation_steps"))
    processes = int(as_number(config, "num_processes"))
    assert 1 <= per_device <= 2, "per-device train batch must fit the 20 GB GPU limit"
    assert accumulation > 0 and per_device * accumulation * processes == 64, "effective global batch must equal 64"
    assert normalize_space(config.get("eval_strategy", "")) in {"steps", "step"}
    for key in ("bf16", "use_peft"):
        assert bool_value(config.get(key)) is True, f"{key} must be enabled"
    assert bool_value(config.get("remove_unused_columns")) is False
    assert bool_value(config.get("push_to_hub")) is False
    assert normalize_space(config.get("report_to", "")) in {"none", "null", "[]", "no"}
    assert Path(str(config.get("model_name_or_path", ""))) == Path("/root/data/model/fictional-tiny-instruct")
    assert Path(str(config.get("train_dataset_path", ""))) == Path("/root/results/dpo_run/train.jsonl")
    assert Path(str(config.get("eval_dataset_path", ""))) == Path("/root/results/dpo_run/eval.jsonl")
    output_dir = Path(str(config.get("output_dir", "")))
    assert output_dir.is_absolute() and output_dir == Path("/root/results/dpo_run/checkpoints")
    remote_text = " ".join(str(value).casefold() for value in config.values())
    assert not any(marker in remote_text for marker in ("wandb", "trackio", "http://", "https://", "huggingface.co"))


def test_launch_smoke_and_offline_safety():
    """The executable launch performs the requested local DPO preflight and contains no runtime fetch or upload step."""
    launch = BUNDLE / "launch.sh"
    text = launch.read_text(encoding="utf-8").casefold()
    compact = re.sub(r"[\s\\\n]+", " ", text)
    assert re.search(r"\btrl\s+dpo\b", compact), "launch.sh does not invoke the DPO command"
    assert "--config" in compact and "dpo_config.yaml" in compact, "launch.sh does not use the bundle configuration"
    forbidden = ("curl ", "wget ", "pip install", "git clone", "hf download", "huggingface-cli upload", "push_to_hub=true")
    assert not any(token in compact for token in forbidden), "launch.sh contains a network fetch, install, or upload action"
    completed = subprocess.run(
        [os.fspath(launch)],
        cwd=BUNDLE,
        capture_output=True,
        text=True,
        timeout=20,
        env=os.environ.copy(),
    )
    assert completed.returncode == 0, f"local DPO preflight failed: {completed.stderr or completed.stdout}"
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise AssertionError("launch did not emit the offline preflight result") from exc
    assert payload.get("status") == "preflight_ok" and payload.get("command") == "dpo"
    assert int(payload.get("effective_global_batch_size", -1)) == 64
