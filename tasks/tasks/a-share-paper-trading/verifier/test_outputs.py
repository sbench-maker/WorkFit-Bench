from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest


DATA = Path(os.environ.get("TASK_DATA_DIR", "/root/data"))
RESULTS = Path(os.environ.get("TASK_RESULTS_DIR", "/root/results"))
OUTPUT_PATH = RESULTS / "output.json"
STATE_PATH = RESULTS / "broker_state.json"


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        pytest.fail(f"缺少要求的文件：{path}", pytrace=False)
    except (OSError, json.JSONDecodeError) as exc:
        pytest.fail(f"文件不可读或不是有效 JSON：{path}: {exc}", pytrace=False)


def _key(value: object) -> str:
    return re.sub(r"[\s_\-]+", "", str(value).strip().lower())


def _value(row: dict, *aliases: str, default=None):
    wanted = {_key(alias) for alias in aliases}
    for key, value in row.items():
        if _key(key) in wanted:
            return value
    return default


def _walk_dicts(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _walk_lists(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, list):
                yield _key(key), child
            yield from _walk_lists(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_lists(child)


def _named_list(root: object, aliases: set[str], row_signal) -> list[dict]:
    normalized_aliases = {_key(name) for name in aliases}
    candidates: list[tuple[int, list[dict]]] = []
    for parent_key, values in _walk_lists(root):
        rows = [row for row in values if isinstance(row, dict)]
        signal = sum(bool(row_signal(row)) for row in rows)
        if signal:
            bonus = 1000 if parent_key in normalized_aliases else 0
            candidates.append((bonus + signal, rows))
    return max(candidates, key=lambda item: item[0])[1] if candidates else []


def _items(root: object) -> dict[str, dict]:
    rows = _named_list(
        root,
        {"items", "results", "instruction_results", "execution_results", "逐项结果", "执行结果"},
        lambda row: _value(row, "request_id", "requestid", "instruction_id", "请求编号", "指令编号") is not None,
    )
    result = {}
    for row in rows:
        request_id = _value(row, "request_id", "requestid", "instruction_id", "请求编号", "指令编号")
        if request_id is not None:
            result[str(request_id).upper()] = row
    return result


def _positions(root: object) -> list[dict]:
    return _named_list(
        root,
        {"positions", "holdings", "final_positions", "持仓", "最终持仓"},
        lambda row: _value(row, "symbol", "code", "证券代码", "股票代码") is not None
        and _value(row, "qty", "quantity", "持仓数量", "数量") is not None
        and _value(row, "sellable_qty", "available_qty", "可卖数量", "avg_cost", "平均成本") is not None,
    )


def _orders(root: object) -> list[dict]:
    return _named_list(
        root,
        {"orders", "order_receipts", "orderreceipts", "订单", "委托回执", "订单回执"},
        lambda row: _value(row, "order_id", "orderid", "委托编号", "订单编号") is not None
        and _value(row, "symbol", "code", "证券代码", "股票代码") is not None,
    )


def _trades(root: object) -> list[dict]:
    return _named_list(
        root,
        {"trades", "fills", "trade_receipts", "成交", "成交回执"},
        lambda row: _value(row, "trade_id", "tradeid", "成交编号") is not None
        and _value(row, "order_id", "orderid", "委托编号", "订单编号") is not None,
    )


def _account(root: object) -> dict:
    candidates = []
    for row in _walk_dicts(root):
        account_id = _value(row, "account_id", "accountid", "账户", "账户编号")
        cash = _value(row, "cash", "现金", "资金余额")
        if str(account_id) == "swing_alpha" and cash is not None:
            candidates.append(row)
    if not candidates:
        return {}
    return max(candidates, key=lambda row: len(row))


def _status(value: object, action: object = None) -> str:
    if isinstance(value, dict):
        value = _value(value, "order_status", "orderStatus", "status", "state", "结果", "状态")
    raw = _key(value)
    action_key = _key(action)
    if action_key in {_key(item) for item in ("cancel", "cancel_order", "撤单", "撤销")} and raw in {
        _key(item) for item in ("executed", "success", "successful", "done", "completed", "执行成功")
    }:
        return "cancelled"
    aliases = {
        "cancelled": {"cancelled", "canceled", "已撤", "撤单成功", "撤销", "已取消"},
        "filled": {"filled", "成交", "已成交", "全部成交", "executed", "success"},
        "open": {"open", "pending", "working", "已报", "未成交", "挂单", "排队中", "待成交"},
        "rejected": {"rejected", "reject", "failed", "error", "拒绝", "已拒绝", "失败", "不可执行"},
    }
    for normalized, values in aliases.items():
        if raw in {_key(item) for item in values}:
            return normalized
    return raw


def _num(row: dict, *aliases: str) -> float:
    value = _value(row, *aliases)
    try:
        return float(value)
    except (TypeError, ValueError):
        pytest.fail(f"记录缺少可解析数值 {aliases}: {row}", pytrace=False)


def _symbol(row: dict) -> str:
    value = _value(row, "symbol", "code", "证券代码", "股票代码", default="")
    return str(value).lower().removeprefix("sh").removeprefix("sz")


def _side(row: dict) -> str:
    raw = _key(_value(row, "side", "action", "方向", "操作", default=""))
    if raw in {"buy", "买", "买入"}:
        return "buy"
    if raw in {"sell", "卖", "卖出"}:
        return "sell"
    return raw


def _order_signature(row: dict) -> tuple[str, str, int]:
    return (_side(row), _symbol(row), int(_num(row, "qty", "quantity", "数量", "委托数量")))


def _position_map(root: object) -> dict[str, dict]:
    return {_symbol(row): row for row in _positions(root)}


@pytest.fixture(scope="session")
def output() -> object:
    return _load(OUTPUT_PATH)


@pytest.fixture(scope="session")
def state() -> dict:
    loaded = _load(STATE_PATH)
    assert isinstance(loaded, dict), "broker_state.json 顶层必须是对象"
    return loaded


def test_cancel_decision(output):
    row = _items(output).get("REQ-001")
    assert row is not None, "REQ-001 撤单结果缺失"
    assert _status(
        _value(row, "status", "result", "状态", "结果"),
        _value(row, "action", "operation", "动作", "操作"),
    ) == "cancelled", "REQ-001 应撤销原盘前委托"
    order_id = _value(row, "order_id", "orderid", "委托编号", "订单编号")
    assert str(order_id) == "OPEN-SA-CANCEL", "REQ-001 回执应指向被撤销的原委托"


def test_filled_order_decisions(output):
    rows = _items(output)
    for request_id in ("REQ-002", "REQ-004", "REQ-007", "REQ-009"):
        assert request_id in rows, f"{request_id} 结果缺失"
        assert _status(_value(rows[request_id], "status", "result", "状态", "结果")) == "filled", f"{request_id} 应完成成交"


def test_locked_limit_order_decision(output):
    row = _items(output).get("REQ-005")
    assert row is not None, "REQ-005 结果缺失"
    assert _status(_value(row, "status", "result", "状态", "结果")) == "open", "REQ-005 为一字涨停买单，应保留为未成交排队单"


@pytest.mark.parametrize(
    ("request_id", "reason_terms"),
    [
        ("REQ-003", ("t+1", "可卖", "sellable", "available=100", "可用100")),
        ("REQ-006", ("涨停", "limitup", "dailylimit", "5.25", "价格上限")),
        ("REQ-008", ("陈旧", "stale", "过期", "行情日期", "2026-09-09")),
        ("REQ-010", ("100", "整手", "手数", "multipleof100", "一手")),
    ],
)
def test_rejected_safeguards(output, request_id, reason_terms):
    row = _items(output).get(request_id)
    assert row is not None, f"{request_id} 结果缺失"
    assert _status(_value(row, "status", "result", "状态", "结果")) == "rejected", f"{request_id} 必须拒绝，不能自动改量或改价"
    reason = str(_value(row, "reason", "message", "error", "rejection_reason", "原因", "说明", default=""))
    normalized = _key(reason)
    assert any(_key(term) in normalized for term in reason_terms), f"{request_id} 的拒绝原因没有指出对应业务约束：{reason!r}"


def test_state_cash_and_account_isolation(state):
    accounts = {row["account_id"]: row for row in state["accounts"]}
    assert state["meta"]["default_account_id"] == "long_term", "执行不得切换默认账户"
    target = accounts["swing_alpha"]
    assert float(target["cash"]) == pytest.approx(238940.73, abs=0.02), "成交金额与佣金、印花税、沪市过户费后的现金不正确"
    assert float(target["frozen_cash"]) == pytest.approx(2205.02, abs=0.02), "撤单应释放旧冻结资金，仅保留涨停排队单冻结额"
    initial_accounts = {row["account_id"]: row for row in _load(DATA / "accounts.json")}
    for account_id in ("long_term", "quant_beta"):
        assert float(accounts[account_id]["cash"]) == pytest.approx(float(initial_accounts[account_id]["cash"]), abs=0.001), f"误改了其他账户 {account_id} 的现金"
        assert float(accounts[account_id]["frozen_cash"]) == pytest.approx(float(initial_accounts[account_id]["frozen_cash"]), abs=0.001), f"误改了其他账户 {account_id} 的冻结资金"


def test_state_orders_and_trades(state):
    initial_orders = _load(DATA / "orders.json")
    orders = state["orders"]
    assert len(orders) == len(initial_orders) + 5, "只有五条下单指令应被接受并生成委托"
    by_id = {row["order_id"]: row for row in orders}
    assert by_id["OPEN-SA-CANCEL"]["status"] == "cancelled", "原盘前委托没有在状态中撤销"
    assert by_id["OPEN-QB-KEEP"]["status"] == "open", "误处理了 quant_beta 的未完成单"
    current = [row for row in orders if row.get("created_at") == "2026-09-10 10:05:00" and row.get("account_id") == "swing_alpha"]
    expected = {
        ("sell", "600111", 200): ("filled", 21.10),
        ("buy", "300222", 300): ("filled", 50.40),
        ("buy", "600444", 200): ("open", None),
        ("buy", "000666", 100): ("filled", 8.88),
        ("sell", "600333", 75): ("filled", 10.05),
    }
    actual = {_order_signature(row): row for row in current}
    assert set(actual) == set(expected), "实际创建的本工单委托集合不正确，可能执行了应拒绝的指令或遗漏了可执行指令"
    for signature, (status, fill_price) in expected.items():
        row = actual[signature]
        assert row["status"] == status, f"委托 {signature} 状态错误"
        if fill_price is not None:
            assert float(row["avg_fill_price"]) == pytest.approx(fill_price, abs=0.001), f"委托 {signature} 成交价错误"
    locked = actual[("buy", "600444", 200)]
    assert float(locked["reserved_cash"]) == pytest.approx(2205.02, abs=0.02), "涨停排队单冻结金额错误"

    initial_trades = _load(DATA / "trades.json")
    new_order_ids = {row["order_id"] for row in current}
    new_trades = [row for row in state["trades"] if row["order_id"] in new_order_ids]
    assert len(state["trades"]) == len(initial_trades) + 4 and len(new_trades) == 4, "本工单应新增四笔成交且不能为排队或拒绝项生成成交"
    trade_map = {(_side(row), _symbol(row), int(row["qty"])): row for row in new_trades}
    assert set(trade_map) == {key for key, value in expected.items() if value[0] == "filled"}, "成交方向、证券或数量集合错误"
    expected_fees = {
        ("sell", "600111", 200): (5.04, 4.22),
        ("buy", "300222", 300): (5.00, 0.00),
        ("buy", "000666", 100): (5.00, 0.00),
        ("sell", "600333", 75): (5.01, 0.75),
    }
    for signature, (fee, stamp) in expected_fees.items():
        row = trade_map[signature]
        assert float(row["commission"]) == pytest.approx(fee, abs=0.02), f"成交 {signature} 佣金或过户费错误"
        assert float(row["tax"]) == pytest.approx(stamp, abs=0.02), f"成交 {signature} 印花税错误"


def test_state_positions(state):
    lots = state["position_lots"]
    grouped = {}
    for lot in lots:
        if lot["account_id"] != "swing_alpha" or int(lot["remaining_qty"]) <= 0:
            continue
        item = grouped.setdefault(lot["symbol"], {"qty": 0, "sellable": 0, "cost": 0.0})
        qty = int(lot["remaining_qty"])
        item["qty"] += qty
        item["cost"] += qty * float(lot["cost_price"])
        if lot["acquired_date"] < "2026-09-10":
            item["sellable"] += qty
    expected = {
        "000666": (100, 0, 8.88),
        "300222": (500, 200, 50.24),
        "600111": (300, 100, 20.6667),
    }
    assert set(grouped) == set(expected), "最终证券持仓集合错误；清仓零股应消失，新买入应形成当日不可卖批次"
    for symbol, (qty, sellable, avg_cost) in expected.items():
        actual = grouped[symbol]
        assert actual["qty"] == qty and actual["sellable"] == sellable, f"{symbol} 的总持仓或 T+1 可卖数量错误"
        assert actual["cost"] / actual["qty"] == pytest.approx(avg_cost, abs=0.0002), f"{symbol} 平均成本错误"


def test_report_account_and_positions_match_state(output, state):
    report_account = _account(output)
    state_account = next(row for row in state["accounts"] if row["account_id"] == "swing_alpha")
    for aliases, expected in (
        (("cash", "现金", "资金余额"), state_account["cash"]),
        (("frozen_cash", "frozencash", "冻结资金"), state_account["frozen_cash"]),
    ):
        assert _num(report_account, *aliases) == pytest.approx(float(expected), abs=0.02), f"回执账户字段 {aliases[0]} 与实际状态不一致"
    available = _value(report_account, "available_cash", "availablecash", "可用资金")
    if available is not None:
        assert float(available) == pytest.approx(float(state_account["cash"]) - float(state_account["frozen_cash"]), abs=0.02), "回执可用资金与现金减冻结资金不一致"

    report_positions = _position_map(output)
    expected = {"000666": (100, 0), "300222": (500, 200), "600111": (300, 100)}
    assert set(report_positions) == set(expected), "回执最终持仓证券集合与执行状态不一致"
    for symbol, (qty, sellable) in expected.items():
        row = report_positions[symbol]
        assert int(_num(row, "qty", "quantity", "持仓数量", "数量")) == qty, f"回执 {symbol} 持仓数量错误"
        assert int(_num(row, "sellable_qty", "available_qty", "可卖数量")) == sellable, f"回执 {symbol} 可卖数量错误"


def test_report_receipts_match_state(output, state):
    report_orders = _orders(output)
    state_orders = state["orders"]
    state_by_id = {row["order_id"]: row for row in state_orders}
    report_order_ids = {str(_value(row, "order_id", "orderid", "委托编号", "订单编号")) for row in report_orders}
    assert "OPEN-SA-CANCEL" in report_order_ids, "订单回执遗漏本工单撤销的原委托"
    current_state_orders = [row for row in state_orders if row.get("created_at") == "2026-09-10 10:05:00" and row.get("account_id") == "swing_alpha"]
    expected_new_ids = {row["order_id"] for row in current_state_orders}
    assert expected_new_ids <= report_order_ids, "订单回执遗漏本工单新建委托"
    for row in report_orders:
        order_id = str(_value(row, "order_id", "orderid", "委托编号", "订单编号"))
        if order_id in expected_new_ids | {"OPEN-SA-CANCEL"}:
            assert _status(_value(row, "status", "状态", "结果")) == _status(state_by_id[order_id]["status"]), f"订单回执 {order_id} 状态与模拟盘不一致"

    report_trades = _trades(output)
    current_order_ids = expected_new_ids
    state_trade_ids = {row["trade_id"] for row in state["trades"] if row["order_id"] in current_order_ids}
    report_trade_ids = {str(_value(row, "trade_id", "tradeid", "成交编号")) for row in report_trades}
    assert state_trade_ids <= report_trade_ids, "成交回执遗漏本工单成交"
    assert len(state_trade_ids) == 4, "执行状态中的本工单成交基数异常"
