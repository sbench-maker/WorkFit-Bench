#!/usr/bin/env python3
"""Deterministic offline HTTP mock for the bundled A-share paper-trading window."""

from __future__ import annotations

import argparse
import json
import threading
from copy import deepcopy
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


DATA_DIR = Path(__file__).resolve().parent


def money(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def is_shanghai(symbol: str) -> bool:
    return str(symbol).lower().startswith(("6", "sh"))


def transfer_fee(amount: float, symbol: str) -> float:
    return money(amount * 0.00001) if is_shanghai(symbol) else 0.0


def commission(amount: float, symbol: str) -> float:
    return money(max(5.0, money(amount * 0.0003)) + transfer_fee(amount, symbol))


def tax(side: str, amount: float) -> float:
    return 0.0 if side != "sell" else money(amount * 0.001)


def load_seed() -> dict:
    names = ("accounts", "quotes", "position_lots", "orders", "trades")
    state = {name: json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8")) for name in names}
    state["meta"] = {
        "clock": "2026-09-10 10:05:00",
        "default_account_id": "long_term",
        "next_order_seq": 1,
        "next_trade_seq": 1,
        "next_lot_seq": 1,
    }
    return state


class Store:
    def __init__(self, state_path: Path) -> None:
        self.path = state_path
        self.lock = threading.RLock()
        if state_path.exists():
            self.state = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            self.state = load_seed()
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @property
    def today(self) -> str:
        return self.state["meta"]["clock"].split(" ", 1)[0]

    def account_row(self, account_id: str) -> dict:
        for account in self.state["accounts"]:
            if account["account_id"] == account_id:
                return account
        raise ValueError(f"account {account_id} not found")

    def quote(self, symbol: str) -> dict:
        symbol = str(symbol).replace("sh", "").replace("sz", "")
        for quote in self.state["quotes"]:
            if quote["symbol"] == symbol:
                return quote
        raise ValueError(f"quote for {symbol} not found")

    def get_order(self, order_id: str) -> dict:
        for order in self.state["orders"]:
            if order["order_id"] == order_id:
                return deepcopy(order)
        raise ValueError(f"order {order_id} not found")

    def positions(self, account_id: str) -> list[dict]:
        self.account_row(account_id)
        grouped: dict[str, dict] = {}
        for lot in self.state["position_lots"]:
            if lot["account_id"] != account_id or int(lot["remaining_qty"]) <= 0:
                continue
            item = grouped.setdefault(lot["symbol"], {"qty": 0, "cost": 0.0, "sellable_qty": 0})
            remaining = int(lot["remaining_qty"])
            item["qty"] += remaining
            item["cost"] += remaining * float(lot["cost_price"])
            if lot["acquired_date"] < self.today:
                item["sellable_qty"] += remaining
        output = []
        for symbol, item in sorted(grouped.items()):
            quote = self.quote(symbol)
            qty = item["qty"]
            market_value = float(quote["price"]) * qty
            output.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "sellable_qty": item["sellable_qty"],
                    "avg_cost": round(item["cost"] / qty, 4),
                    "last_price": float(quote["price"]),
                    "market_value": money(market_value),
                    "unrealized_pnl": money(market_value - item["cost"]),
                }
            )
        return output

    def account(self, account_id: str) -> dict:
        account = self.account_row(account_id)
        positions = self.positions(account_id)
        market_value = money(sum(row["market_value"] for row in positions))
        account_orders = [o for o in self.state["orders"] if o["account_id"] == account_id]
        account_trades = [t for t in self.state["trades"] if t["account_id"] == account_id]
        return {
            "account_id": account_id,
            "initial_cash": money(account["initial_cash"]),
            "cash": money(account["cash"]),
            "frozen_cash": money(account["frozen_cash"]),
            "available_cash": money(float(account["cash"]) - float(account["frozen_cash"])),
            "market_value": market_value,
            "net_asset": money(float(account["cash"]) + market_value),
            "positions": positions,
            "order_count": len(account_orders),
            "trade_count": len(account_trades),
            "updated_at": account["updated_at"],
        }

    def list_accounts(self) -> list[dict]:
        default = self.state["meta"]["default_account_id"]
        rows = []
        for account in sorted(self.state["accounts"], key=lambda row: row["account_id"]):
            item = self.account(account["account_id"])
            item["is_default"] = item["account_id"] == default
            rows.append(item)
        return rows

    def list_orders(self, account_id: str, status: str | None = None) -> list[dict]:
        self.account_row(account_id)
        rows = [deepcopy(o) for o in self.state["orders"] if o["account_id"] == account_id and (status is None or o["status"] == status)]
        return sorted(rows, key=lambda row: (row["created_at"], row["order_id"]), reverse=True)

    def list_trades(self, account_id: str) -> list[dict]:
        self.account_row(account_id)
        rows = [deepcopy(t) for t in self.state["trades"] if t["account_id"] == account_id]
        return sorted(rows, key=lambda row: (row["created_at"], row["trade_id"]), reverse=True)

    def cancel(self, order_id: str) -> dict:
        with self.lock:
            for order in self.state["orders"]:
                if order["order_id"] != order_id:
                    continue
                if order["status"] != "open":
                    raise ValueError(f"order {order_id} is not open")
                account = self.account_row(order["account_id"])
                account["frozen_cash"] = money(max(0.0, float(account["frozen_cash"]) - float(order["reserved_cash"])))
                account["updated_at"] = self.state["meta"]["clock"]
                order["status"] = "cancelled"
                order["updated_at"] = self.state["meta"]["clock"]
                self.save()
                return deepcopy(order)
        raise ValueError(f"order {order_id} not found")

    def _next_id(self, kind: str) -> str:
        key = f"next_{kind}_seq"
        value = int(self.state["meta"][key])
        self.state["meta"][key] = value + 1
        prefix = {"order": "ORD", "trade": "TRD", "lot": "LOT"}[kind]
        return f"{prefix}-20260910-{value:04d}"

    def _validate_tick(self, raw: object) -> float:
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"invalid price {raw}") from exc
        if value <= 0 or value != value.quantize(Decimal("0.01")):
            raise ValueError(f"order price must align with 0.01 tick size, got {raw}")
        return float(value)

    def _sellable_qty(self, account_id: str, symbol: str) -> int:
        return sum(int(lot["remaining_qty"]) for lot in self.state["position_lots"] if lot["account_id"] == account_id and lot["symbol"] == symbol and lot["acquired_date"] < self.today and int(lot["remaining_qty"]) > 0)

    def _total_qty(self, account_id: str, symbol: str) -> int:
        return sum(int(lot["remaining_qty"]) for lot in self.state["position_lots"] if lot["account_id"] == account_id and lot["symbol"] == symbol and int(lot["remaining_qty"]) > 0)

    def _pending_sell_qty(self, account_id: str, symbol: str) -> int:
        return sum(int(order["qty"]) - int(order["filled_qty"]) for order in self.state["orders"] if order["account_id"] == account_id and order["symbol"] == symbol and order["side"] == "sell" and order["status"] == "open")

    def place_order(self, payload: dict) -> dict:
        with self.lock:
            account_id = str(payload["account_id"])
            symbol = str(payload["symbol"]).replace("sh", "").replace("sz", "")
            side = str(payload["side"]).lower()
            order_type = str(payload.get("order_type", "limit")).lower()
            qty = int(payload["qty"])
            if side not in {"buy", "sell"}:
                raise ValueError("side must be buy or sell")
            if order_type not in {"limit", "market"}:
                raise ValueError("order_type must be limit or market")
            if qty <= 0:
                raise ValueError("qty must be positive")
            if side == "buy" and qty % 100:
                raise ValueError("A-share buy order qty must be multiple of 100")
            account = self.account_row(account_id)
            quote = self.quote(symbol)
            limit_price = None
            if order_type == "limit":
                if payload.get("limit_price") is None:
                    raise ValueError("limit_price required for limit orders")
                limit_price = self._validate_tick(payload["limit_price"])
                if limit_price > money(quote["limit_up"]):
                    raise ValueError(f"order price {limit_price} above daily limit up {money(quote['limit_up'])}")
                if limit_price < money(quote["limit_down"]):
                    raise ValueError(f"order price {limit_price} below daily limit down {money(quote['limit_down'])}")
            else:
                clock = datetime.fromisoformat(self.state["meta"]["clock"])
                in_session = time(9, 30) <= clock.time() <= time(11, 30) or time(13, 0) <= clock.time() < time(14, 57)
                if not in_session:
                    raise ValueError("market orders are only accepted during trading hours")
                if str(quote["timestamp"]).split(" ", 1)[0] != self.today:
                    raise ValueError(f"symbol {symbol} quote is stale or unavailable for market order")

            reserved_cash = 0.0
            if side == "buy":
                estimate_price = limit_price if order_type == "limit" else float(quote["price"])
                estimate_amount = money(qty * estimate_price)
                reserved_cash = money(estimate_amount + commission(estimate_amount, symbol)) if order_type == "limit" else 0.0
                need = reserved_cash if order_type == "limit" else money(estimate_amount + commission(estimate_amount, symbol))
                available = money(float(account["cash"]) - float(account["frozen_cash"]))
                if available + 1e-6 < need:
                    raise ValueError(f"insufficient available cash, available={available}")
            else:
                available = self._sellable_qty(account_id, symbol) - self._pending_sell_qty(account_id, symbol)
                if available < qty:
                    raise ValueError(f"insufficient sellable qty, available={available}")
                total = self._total_qty(account_id, symbol)
                if qty % 100 and qty != total:
                    raise ValueError("A-share sell qty must be multiple of 100 unless selling all remaining shares")

            order = {
                "order_id": self._next_id("order"),
                "account_id": account_id,
                "symbol": symbol,
                "side": side,
                "order_type": order_type,
                "limit_price": limit_price,
                "qty": qty,
                "reserved_cash": reserved_cash,
                "filled_qty": 0,
                "avg_fill_price": None,
                "status": "open",
                "note": str(payload.get("note", "")),
                "created_at": self.state["meta"]["clock"],
                "updated_at": self.state["meta"]["clock"],
            }
            self.state["orders"].append(order)
            if reserved_cash:
                account["frozen_cash"] = money(float(account["frozen_cash"]) + reserved_cash)
            account["updated_at"] = self.state["meta"]["clock"]
            self.save()
            if order_type == "market":
                self.process_orders()
            return self.get_order(order["order_id"])

    @staticmethod
    def _locked_limit(side: str, quote: dict) -> bool:
        if side == "buy":
            return all(money(quote[key]) >= money(quote["limit_up"]) for key in ("price", "open", "low"))
        return all(money(quote[key]) <= money(quote["limit_down"]) for key in ("price", "open", "high"))

    def _fill_price(self, order: dict, quote: dict) -> float | None:
        if str(quote["timestamp"]).split(" ", 1)[0] != self.today:
            return None
        if order["order_type"] == "market":
            return None if self._locked_limit(order["side"], quote) else float(quote["price"])
        if self._locked_limit(order["side"], quote):
            return None
        limit_price = float(order["limit_price"])
        market_price = float(quote["price"])
        if order["side"] == "buy" and market_price <= limit_price:
            return min(limit_price, market_price)
        if order["side"] == "sell" and market_price >= limit_price:
            return max(limit_price, market_price)
        return None

    def _fill(self, order: dict, fill_price: float) -> None:
        account = self.account_row(order["account_id"])
        qty = int(order["qty"])
        amount = money(qty * fill_price)
        fee = commission(amount, order["symbol"])
        stamp = tax(order["side"], amount)
        if order["side"] == "buy":
            total = money(amount + fee)
            if float(account["cash"]) + 1e-6 < total:
                order["status"] = "rejected"
                order["note"] = "insufficient cash at fill time"
                account["frozen_cash"] = money(max(0.0, float(account["frozen_cash"]) - float(order["reserved_cash"])))
                return
            account["cash"] = money(float(account["cash"]) - total)
            account["frozen_cash"] = money(max(0.0, float(account["frozen_cash"]) - float(order["reserved_cash"])))
            self.state["position_lots"].append(
                {"lot_id": self._next_id("lot"), "account_id": order["account_id"], "symbol": order["symbol"], "acquired_date": self.today, "qty": qty, "remaining_qty": qty, "cost_price": fill_price}
            )
        else:
            remaining = qty
            eligible = sorted(
                (lot for lot in self.state["position_lots"] if lot["account_id"] == order["account_id"] and lot["symbol"] == order["symbol"] and lot["acquired_date"] < self.today and int(lot["remaining_qty"]) > 0),
                key=lambda lot: (lot["acquired_date"], lot["lot_id"]),
            )
            for lot in eligible:
                take = min(remaining, int(lot["remaining_qty"]))
                lot["remaining_qty"] = int(lot["remaining_qty"]) - take
                remaining -= take
                if remaining == 0:
                    break
            if remaining:
                order["status"] = "rejected"
                order["note"] = "insufficient sellable qty at fill time"
                return
            account["cash"] = money(float(account["cash"]) + amount - fee - stamp)

        trade = {
            "trade_id": self._next_id("trade"),
            "order_id": order["order_id"],
            "account_id": order["account_id"],
            "symbol": order["symbol"],
            "side": order["side"],
            "price": fill_price,
            "qty": qty,
            "amount": amount,
            "commission": fee,
            "tax": stamp,
            "created_at": self.state["meta"]["clock"],
        }
        self.state["trades"].append(trade)
        order["filled_qty"] = qty
        order["avg_fill_price"] = fill_price
        order["status"] = "filled"
        order["updated_at"] = self.state["meta"]["clock"]
        account["updated_at"] = self.state["meta"]["clock"]

    def process_orders(self) -> dict:
        with self.lock:
            processed = 0
            filled = 0
            for order in self.state["orders"]:
                if order["status"] != "open":
                    continue
                processed += 1
                quote = self.quote(order["symbol"])
                fill_price = self._fill_price(order, quote)
                if fill_price is not None:
                    self._fill(order, fill_price)
                    if order["status"] == "filled":
                        filled += 1
            self.save()
            return {"processed": processed, "filled": filled, "expired": 0}


class Handler(BaseHTTPRequestHandler):
    store: Store

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8")) if raw else {}

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/health":
                return self.send_json({"status": "ok", "clock": self.store.state["meta"]["clock"]})
            if path == "/accounts":
                return self.send_json({"status": "success", "data": self.store.list_accounts()})
            if path == "/accounts/default":
                return self.send_json({"status": "success", "data": {"account_id": self.store.state["meta"]["default_account_id"]}})
            parts = path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "accounts":
                account_id = parts[1]
                if len(parts) == 2:
                    return self.send_json({"status": "success", "data": self.store.account(account_id)})
                if len(parts) == 3 and parts[2] == "positions":
                    return self.send_json({"status": "success", "data": self.store.positions(account_id)})
                if len(parts) == 3 and parts[2] == "orders":
                    status = query.get("status", [None])[0]
                    return self.send_json({"status": "success", "data": self.store.list_orders(account_id, status)})
                if len(parts) == 3 and parts[2] == "trades":
                    return self.send_json({"status": "success", "data": self.store.list_trades(account_id)})
            return self.send_json({"status": "error", "message": f"unknown route {path}"}, 404)
        except Exception as exc:
            return self.send_json({"status": "error", "message": str(exc)}, 400)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            payload = self.body()
            if path == "/orders":
                return self.send_json({"status": "success", "data": self.store.place_order(payload)}, 201)
            if path == "/orders/process":
                return self.send_json({"status": "success", "data": self.store.process_orders()})
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "orders" and parts[2] == "cancel":
                return self.send_json({"status": "success", "data": self.store.cancel(parts[1])})
            return self.send_json({"status": "error", "message": f"unknown route {path}"}, 404)
        except Exception as exc:
            return self.send_json({"status": "error", "message": str(exc)}, 400)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--state", type=Path, default=Path("/root/results/broker_state.json"))
    args = parser.parse_args()
    Handler.store = Store(args.state)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"offline paper-trading service listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
