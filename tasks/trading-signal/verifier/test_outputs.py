from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

import pytest


DATA_DIR = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS_DIR = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS_DIR / "output.json"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _lookup(node: object, aliases: set[str]):
    wanted = {_key(item) for item in aliases}
    if isinstance(node, dict):
        for raw_key, value in node.items():
            if _key(raw_key) in wanted:
                return raw_key, value
        for value in node.values():
            if isinstance(value, dict):
                found = _lookup(value, aliases)
                if found is not None:
                    return found
    return None


def _as_rows(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            if isinstance(item, dict):
                row = dict(item)
                row.setdefault("signal_id", key)
                rows.append(row)
            elif isinstance(item, list):
                rows.extend(item)
        return rows
    return []


def _find_collection(node: object, aliases: set[str]) -> list | None:
    wanted = {_key(item) for item in aliases}
    if isinstance(node, dict):
        for raw_key, value in node.items():
            if _key(raw_key) in wanted and isinstance(value, (list, dict)):
                return _as_rows(value)
        for value in node.values():
            found = _find_collection(value, aliases)
            if found is not None:
                return found
    return None


def _find_collections(node: object, aliases: set[str]) -> list:
    wanted = {_key(item) for item in aliases}
    rows: list = []
    if isinstance(node, dict):
        for raw_key, value in node.items():
            if _key(raw_key) in wanted and isinstance(value, (list, dict)):
                rows.extend(_as_rows(value))
            else:
                rows.extend(_find_collections(value, aliases))
    elif isinstance(node, list):
        for value in node:
            rows.extend(_find_collections(value, aliases))
    return rows


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("$", "").replace("%", "")
        try:
            parsed = float(text)
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def _value(row: object, aliases: set[str]):
    found = _lookup(row, aliases)
    return None if found is None else found[1]


def _signal_id(row: object) -> int | None:
    value = _number(_value(row, {"signal_id", "signalId", "id"}))
    return None if value is None else int(value)


def _resolved_signal_id(row: object, by_id: dict[int, dict]) -> int | None:
    explicit = _signal_id(row)
    if explicit in by_id:
        return explicit
    ticker = str(_value(row, {"ticker", "symbol", "token"}) or "").upper()
    chain = str(_value(row, {"chain_id", "chainId", "chain"}) or "")
    address = str(_value(row, {"contract_address", "contractAddress", "address"}) or "").lower()
    candidates = list(by_id.items())
    if address:
        candidates = [(sid, source) for sid, source in candidates if source.get("contractAddress", "").lower() == address]
    if chain:
        candidates = [(sid, source) for sid, source in candidates if str(source.get("chainId", "")) == chain]
    if ticker:
        candidates = [(sid, source) for sid, source in candidates if str(source.get("ticker", "")).upper() == ticker]
    return candidates[0][0] if len(candidates) == 1 else None


def _ranked(rows: list) -> list:
    ranks = [_number(_value(row, {"rank", "priority_rank", "order"})) for row in rows]
    if rows and all(value is not None for value in ranks):
        return [row for _, row in sorted(zip(ranks, rows), key=lambda pair: pair[0])]
    return rows


def _load_submission() -> dict:
    if not OUTPUT_PATH.is_file():
        return {"error": f"missing {OUTPUT_PATH}", "document": None, "buys": None, "sells": None, "issues": None}
    try:
        document = _json(OUTPUT_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"unreadable JSON: {exc}", "document": None, "buys": None, "sells": None, "issues": None}
    if not isinstance(document, dict):
        return {"error": "output JSON must be an object", "document": document, "buys": None, "sells": None, "issues": None}
    buys = _find_collection(document, {"ranked_buys", "buy_opportunities", "buy_watchlist", "watchlist", "buys", "opportunities"})
    sells = _find_collection(document, {"ranked_sells", "sell_watchlist", "exit_alerts", "sell_alerts", "sells"})
    issues = _find_collections(document, {
        "data_quality_alerts", "quality_alerts", "data_issues", "incomplete_signals",
        "buy_incomplete", "sell_incomplete", "exceptions",
    })
    deduplicated_issues = []
    seen_issue_ids = set()
    for row in issues:
        marker = _signal_id(row) if isinstance(row, dict) else None
        if marker is None or marker not in seen_issue_ids:
            deduplicated_issues.append(row)
            seen_issue_ids.add(marker)
    return {"error": None, "document": document, "buys": buys, "sells": sells, "issues": deduplicated_issues}


def _source() -> tuple[list[dict], dict, set[tuple[str, str]], int]:
    signals_doc = _json(DATA_DIR / "smart_money_signals.json")
    policy = _json(DATA_DIR / "desk_policy.json")
    positions = _json(DATA_DIR / "open_positions.json")["positions"]
    held = {
        (str(row["chainId"]), str(row["contractAddress"]))
        for row in positions
        if row.get("status") == "open"
    }
    snapshot_ms = int(datetime.fromisoformat(policy["snapshotTime"].replace("Z", "+00:00")).timestamp() * 1000)
    return signals_doc["data"], policy, held, snapshot_ms


def _present(row: dict, field: str) -> bool:
    value = row.get(field)
    if value is None or value == "":
        return False
    if field in {"alertPrice", "currentPrice", "maxGain", "exitRate", "smartMoneyCount", "signalTriggerTime"}:
        return _number(value) is not None
    return True


def _buy_gate(row: dict, policy: dict, snapshot_ms: int) -> bool:
    cfg = policy["buyQueue"]
    try:
        age = (snapshot_ms - int(row["signalTriggerTime"])) / 60_000
        return (
            row.get("chainId") in policy["supportedChainIds"]
            and row.get("direction") in cfg["directions"]
            and row.get("status") in cfg["statuses"]
            and 0 <= age <= cfg["maxAgeMinutes"]
            and float(row.get("smartMoneyCount", -1)) >= cfg["minSmartMoneyCount"]
            and float(row.get("exitRate", 101)) < cfg["maxExitRateExclusive"]
            and float(row.get("totalTokenValue", -1)) >= cfg["minTotalTokenValueUsd"]
        )
    except (TypeError, ValueError):
        return False


def _sell_gate(row: dict, policy: dict, held: set[tuple[str, str]], snapshot_ms: int) -> bool:
    cfg = policy["sellAlerts"]
    try:
        age = (snapshot_ms - int(row["signalTriggerTime"])) / 60_000
        return (
            row.get("chainId") in policy["supportedChainIds"]
            and row.get("direction") in cfg["directions"]
            and row.get("status") in cfg["statuses"]
            and 0 <= age <= cfg["maxAgeMinutes"]
            and float(row.get("smartMoneyCount", -1)) >= cfg["minSmartMoneyCount"]
            and (str(row.get("chainId", "")), str(row.get("contractAddress", ""))) in held
        )
    except (TypeError, ValueError):
        return False


def _expected() -> dict:
    signals, policy, held, snapshot_ms = _source()
    buys = []
    sells = []
    issues: dict[int, set[str]] = {}
    for row in signals:
        if _buy_gate(row, policy, snapshot_ms):
            missing = {field for field in policy["buyQueue"]["requiredFields"] if not _present(row, field)}
            if missing:
                issues[int(row["signalId"])] = missing
            else:
                alert = float(row["alertPrice"])
                ret = (float(row["currentPrice"]) / alert - 1) * 100
                gain = float(row["maxGain"]) * 100
                age = (snapshot_ms - int(row["signalTriggerTime"])) / 60_000
                score = float(row["smartMoneyCount"]) * 12 + ret * .30 + gain * .20 - float(row["exitRate"]) * .40 - age / 60 * 2
                buys.append((score, int(row["signalId"])))
        if _sell_gate(row, policy, held, snapshot_ms):
            missing = {field for field in policy["sellAlerts"]["requiredFields"] if not _present(row, field)}
            if missing:
                issues[int(row["signalId"])] = missing
            else:
                sells.append(row)
    buys.sort(key=lambda item: (-item[0], item[1]))
    buy_ids = [signal_id for _, signal_id in buys[: policy["buyQueue"]["ranking"]["topN"]]]
    sells.sort(key=lambda row: (-float(row["smartMoneyCount"]), -float(row["exitRate"]), -int(row["signalTriggerTime"]), int(row["signalId"])))
    return {
        "buy_ids": buy_ids,
        "sell_ids": [int(row["signalId"]) for row in sells],
        "issues": issues,
        "by_id": {int(row["signalId"]): row for row in signals},
    }


def _usable(state: dict) -> bool:
    return state["error"] is None and all(isinstance(state[name], list) for name in ("buys", "sells", "issues"))


def _pct_matches(actual: object, expected_pct: float, tolerance: float = 0.08) -> bool:
    value = _number(actual)
    if value is None:
        return False
    candidates = [value]
    if abs(value) <= 2:
        candidates.append(value * 100)
    return min(abs(candidate - expected_pct) for candidate in candidates) <= tolerance


def _close(actual: object, expected: float) -> bool:
    value = _number(actual)
    if value is None:
        return False
    return math.isclose(value, expected, rel_tol=2e-5, abs_tol=1e-10)


def test_artifact_usability():
    state = _load_submission()
    assert state["error"] is None, state["error"]
    missing = [name for name in ("buys", "sells", "issues") if not isinstance(state[name], list)]
    assert not missing, f"output does not expose identifiable collections for: {', '.join(missing)}"


def test_buy_selection_and_ranking():
    state = _load_submission()
    if not _usable(state):
        pytest.skip("artifact usability failure already reports the root representation problem")
    expected_data = _expected()
    expected = expected_data["buy_ids"]
    actual = [_resolved_signal_id(row, expected_data["by_id"]) for row in _ranked(state["buys"])]
    assert None not in actual, "every buy opportunity needs a unique source identity so it can be acted on"
    assert len(actual) == len(set(actual)), "a repeated buy signal would overstate conviction and consume queue capacity"
    assert actual == expected, f"ranked buy signal IDs are {actual}, expected {expected} under desk policy"


def test_held_position_sell_alerts():
    state = _load_submission()
    if not _usable(state):
        pytest.skip("artifact usability failure already reports the root representation problem")
    expected_data = _expected()
    expected = expected_data["sell_ids"]
    actual = [_resolved_signal_id(row, expected_data["by_id"]) for row in _ranked(state["sells"])]
    assert None not in actual, "every sell alert needs a unique source identity so the held token can be verified"
    assert len(actual) == len(set(actual)), "duplicate sell alerts would exaggerate the exit signal"
    assert actual == expected, f"ranked held-position sell signal IDs are {actual}, expected {expected}"


def test_signal_metrics_and_units():
    state = _load_submission()
    if not _usable(state):
        pytest.skip("artifact usability failure already reports the root representation problem")
    expected = _expected()
    expected_ids = set(expected["buy_ids"] + expected["sell_ids"])
    actual_rows = {}
    for row in state["buys"] + state["sells"]:
        signal_id = _resolved_signal_id(row, expected["by_id"])
        if signal_id in expected_ids:
            actual_rows[signal_id] = row
    assert actual_rows, "no actionable rows could be matched to source signals for metric validation"
    problems = []
    for signal_id, row in actual_rows.items():
        source = expected["by_id"][signal_id]
        alert = float(source["alertPrice"])
        current = float(source["currentPrice"])
        current_return = (current / alert - 1) * 100
        checks = {
            "trigger price": _close(_value(row, {"trigger_price_usd", "triggerPrice", "alertPrice", "entry_price"}), alert),
            "current price": _close(_value(row, {"current_price_usd", "currentPrice", "price_now"}), current),
            "current return": _pct_matches(_value(row, {"current_return_pct", "currentReturnPct", "current_return", "return_pct", "gain_since_trigger"}), current_return),
            "max gain": _pct_matches(_value(row, {"max_gain_pct", "maxGainPct", "maxGain", "max_gain"}), float(source["maxGain"]) * 100),
            "exit rate": _pct_matches(_value(row, {"exit_rate_pct", "exitRatePct", "exitRate", "exit_rate"}), float(source["exitRate"])),
            "wallet conviction": _number(_value(row, {"smart_money_count", "smartMoneyCount", "wallet_count", "wallets", "conviction"})) == float(source["smartMoneyCount"]),
        }
        optional_identity = {
            "ticker": ({"ticker", "symbol", "token"}, source["ticker"], False),
            "chain": ({"chain_id", "chainId", "chain"}, source["chainId"], False),
            "contract": ({"contract_address", "contractAddress", "address"}, source["contractAddress"], True),
            "direction": ({"direction", "side", "signal_direction"}, source["direction"], False),
        }
        for label, (aliases, source_value, lower) in optional_identity.items():
            actual_value = _value(row, aliases)
            if actual_value is not None:
                left = str(actual_value).lower() if lower else str(actual_value).upper()
                right = str(source_value).lower() if lower else str(source_value).upper()
                checks[label] = left == right
        failures = [name for name, passed in checks.items() if not passed]
        if failures:
            problems.append(f"{signal_id}: {', '.join(failures)}")
    assert not problems, "source metric mismatches (including percent conversion): " + "; ".join(problems)


def test_incomplete_qualifying_signals():
    state = _load_submission()
    if not _usable(state):
        pytest.skip("artifact usability failure already reports the root representation problem")
    expected = _expected()
    actionable_ids = {_resolved_signal_id(row, expected["by_id"]) for row in state["buys"] + state["sells"]}
    promoted = sorted(set(expected["issues"]) & actionable_ids)
    assert not promoted, f"incomplete signals were promoted with values that would have to be guessed: {promoted}"
    rendered_issues = [json.dumps(row, ensure_ascii=False, sort_keys=True).lower() for row in state["issues"]]
    missing_evidence = []
    for signal_id, fields in expected["issues"].items():
        source = expected["by_id"][signal_id]
        matching = [
            text for text in rendered_issues
            if str(signal_id) in text or str(source["ticker"]).lower() in text
        ]
        if not matching or any(not any(_key(field) in _key(text) for text in matching) for field in fields):
            missing_evidence.append(f"{signal_id}:{sorted(fields)}")
    assert not missing_evidence, "missing or inaccurate data-quality alerts for " + ", ".join(missing_evidence)
