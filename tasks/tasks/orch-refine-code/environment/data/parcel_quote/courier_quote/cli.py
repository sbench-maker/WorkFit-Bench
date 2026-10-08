"""JSON command line interface with an unfortunately copied quote engine."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SERVICE_RULES = {
    "ground": {"base": 525, "zone": 85, "included": 1000, "weight": 70},
    "priority": {"base": 975, "zone": 120, "included": 500, "weight": 110},
    "same_day": {"base": 1800, "zone": 200, "included": 500, "weight": 160},
}


def _cli_quote(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise TypeError("request must be an object")
    for field in ("request_id", "origin_zone", "destination_zone", "service", "weight_grams", "declared_value_cents", "residential", "fragile", "coupon"):
        if field not in request:
            raise ValueError(f"missing field: {field}")
    if not isinstance(request["request_id"], str) or not request["request_id"].strip():
        raise ValueError("request_id must be a non-empty string")
    for field in ("origin_zone", "destination_zone"):
        value = request[field]
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 8:
            raise ValueError(f"{field} must be an integer from 1 to 8")
    if request["service"] not in SERVICE_RULES:
        raise ValueError(f"unknown service: {request['service']}")
    weight = request["weight_grams"]
    if isinstance(weight, bool) or not isinstance(weight, int) or not 1 <= weight <= 50000:
        raise ValueError("weight_grams must be an integer from 1 to 50000")
    declared = request["declared_value_cents"]
    if isinstance(declared, bool) or not isinstance(declared, int) or not 0 <= declared <= 2000000:
        raise ValueError("declared_value_cents must be an integer from 0 to 2000000")
    if not isinstance(request["residential"], bool):
        raise ValueError("residential must be a boolean")
    if not isinstance(request["fragile"], bool):
        raise ValueError("fragile must be a boolean")
    if request["coupon"] not in (None, "SAVE15", "FLOOR300"):
        raise ValueError(f"unknown coupon: {request['coupon']}")
    distance = abs(request["destination_zone"] - request["origin_zone"])
    if request["service"] == "same_day" and (distance > 1 or weight > 10000):
        raise ValueError("same_day is unavailable for this route or weight")
    rules = SERVICE_RULES[request["service"]]
    base = rules["base"]
    distance_charge = distance * rules["zone"]
    excess = max(0, weight - rules["included"])
    weight_charge = ((excess + 499) // 500) * rules["weight"]
    surcharges = []
    if request["residential"]:
        surcharges.append({"code": "RESIDENTIAL", "amount_cents": 175})
    if request["fragile"]:
        surcharges.append({"code": "FRAGILE", "amount_cents": max(225, (declared * 4 + 999) // 1000)})
    if request["origin_zone"] == 8 or request["destination_zone"] == 8:
        surcharges.append({"code": "REMOTE_AREA", "amount_cents": 350})
    if weight > 20000:
        surcharges.append({"code": "OVERSIZE", "amount_cents": 900})
    chargeable = base + distance_charge + weight_charge
    if request["coupon"] == "SAVE15":
        discount = (chargeable * 15 + 50) // 100
    elif request["coupon"] == "FLOOR300":
        discount = min(300, chargeable)
    else:
        discount = 0
    total = chargeable + sum(row["amount_cents"] for row in surcharges) - discount
    eta_days = max(1, 5 + distance // 2) if request["service"] == "ground" else (2 if request["service"] == "priority" else 0)
    return {"request_id": request["request_id"], "base_cents": base, "distance_cents": distance_charge, "weight_cents": weight_charge, "surcharges": surcharges, "discount_cents": discount, "total_cents": total, "currency": "USD", "eta_days": eta_days}


def _emit(row: dict[str, Any]) -> None:
    print(json.dumps(row, separators=(",", ":"), sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in {"quote", "batch"}:
        print("usage: courier-quote {quote JSON|batch PATH}", file=sys.stderr)
        return 64
    if args[0] == "quote":
        try:
            _emit(_cli_quote(json.loads(args[1])))
            return 0
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    had_error = False
    try:
        lines = Path(args[1]).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            _emit(_cli_quote(json.loads(line)))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            had_error = True
            _emit({"line": number, "error": str(exc)})
    return 2 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
