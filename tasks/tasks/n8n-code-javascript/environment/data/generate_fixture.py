#!/usr/bin/env python3
"""Generate the deterministic fictional webhook fixture next to this script."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parent
SEED = 7049


def decimal_value(cents: int, mode: int):
    text = f"{cents // 100}.{cents % 100:02d}"
    if mode % 3 == 0:
        return text
    if mode % 3 == 1:
        return float(text)
    return f"  {text}  "


def iso_with_offset(moment_utc: datetime, selector: int) -> str:
    offsets = [timezone.utc, timezone(timedelta(hours=8)), timezone(timedelta(hours=-4)), timezone(timedelta(hours=5, minutes=30))]
    rendered = moment_utc.astimezone(offsets[selector % len(offsets)]).isoformat(timespec="seconds")
    return rendered.replace("+00:00", "Z")


def base_item(i: int) -> dict:
    occurred = datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(minutes=i * 37)
    received = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=i * 3)
    subtotal = 1_200 + (i * 137) % 8_800
    tax = (subtotal * (5 + i % 5) + 50) // 100
    shipping = (0, 499, 799)[i % 3]
    discount = (0, 250, 500, 1_000)[i % 4]
    if discount >= subtotal + tax + shipping:
        discount = 0
    event_type = "cancelled" if i % 17 == 0 else ("refunded" if i % 5 == 0 else "paid")
    currencies = ("usd", " EUR ", "gBp")
    return {
        "json": {
            "headers": {"content-type": "application/json", "x-delivery-attempt": "1"},
            "query": {},
            "params": {},
            "received_at": received.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "body": {
                "event_id": f" EVT-{i:04d} " if i % 8 == 0 else f"EVT-{i:04d}",
                "order_id": f" ORD-{10_000 + i} " if i % 9 == 0 else f"ORD-{10_000 + i}",
                "event_type": event_type.upper() if i % 6 == 0 else event_type,
                "occurred_at": iso_with_offset(occurred, i),
                "currency": currencies[i % len(currencies)],
                "amounts": {
                    "subtotal": decimal_value(subtotal, i),
                    "tax": decimal_value(tax, i + 1),
                    "shipping": decimal_value(shipping, i + 2),
                    "discount": decimal_value(discount, i + 3),
                },
                "customer": {"id": f" CUST-{1 + i % 47:03d} " if i % 10 == 0 else f"CUST-{1 + i % 47:03d}"},
            },
        }
    }


def make_fixture() -> list[dict]:
    items = [base_item(i) for i in range(1, 211)]

    invalid_mutations = {
        191: lambda item: item["json"]["body"].pop("order_id"),
        192: lambda item: item["json"]["body"].__setitem__("event_type", "chargeback"),
        193: lambda item: item["json"]["body"].__setitem__("occurred_at", "June 4, 2026"),
        194: lambda item: item["json"]["body"].__setitem__("currency", "JPY"),
        195: lambda item: item["json"]["body"]["amounts"].__setitem__("subtotal", "12.345"),
        196: lambda item: item["json"]["body"]["amounts"].__setitem__("tax", "-1.00"),
        197: lambda item: item["json"]["body"]["amounts"].__setitem__("discount", "9999.99"),
        198: lambda item: item["json"]["body"].__setitem__("customer", {}),
        199: lambda item: item["json"].__setitem__("body", None),
        200: lambda item: item["json"].__setitem__("received_at", "not-a-timestamp"),
        201: lambda item: item["json"]["body"].__setitem__("event_id", "  "),
        202: lambda item: item["json"]["body"]["amounts"].__setitem__("subtotal", "NaN"),
        203: lambda item: item["json"]["body"]["amounts"].__setitem__("subtotal", None),
        204: lambda item: item["json"]["body"]["amounts"].__setitem__("tax", True),
        205: lambda item: item["json"]["body"]["amounts"].pop("shipping"),
        206: lambda item: item["json"]["body"].__setitem__("event_id", 206),
        207: lambda item: item["json"]["body"].__setitem__("customer", {"id": {"raw": "CUST-019"}}),
        208: lambda item: item["json"]["body"].__setitem__("occurred_at", "2026-06-08T12:30:00"),
        209: lambda item: item["json"]["body"].__setitem__("currency", None),
        210: lambda item: item["json"].pop("body"),
    }
    for i, mutate in invalid_mutations.items():
        mutate(items[i - 1])

    retries = []
    for i in range(1, 51):
        retry = copy.deepcopy(items[i - 1])
        received = datetime.fromisoformat(retry["json"]["received_at"].replace("Z", "+00:00")) + timedelta(hours=2)
        retry["json"]["received_at"] = received.isoformat(timespec="seconds").replace("+00:00", "Z")
        retry["json"]["headers"]["x-delivery-attempt"] = "2"
        if i <= 40 and i % 9 == 0:
            retry["json"]["body"]["amounts"]["discount"] = "0.25"
        if 41 <= i <= 45:
            retry["json"]["body"]["amounts"]["subtotal"] = "bad-decimal"
        retries.append(retry)

    items.extend(retries)
    random.Random(SEED).shuffle(items)
    return items


def main() -> None:
    items = make_fixture()
    (ROOT / "webhook_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
