"""Legacy implementation awaiting migration."""

from __future__ import annotations

import json
from pathlib import Path

from .stripe_mock import FakeStripeClient


class PaymentService:
    def __init__(self, orders_path, client, webhook_secret):
        self.orders_path = Path(orders_path)
        self.client = client
        self.webhook_secret = webhook_secret

    def _orders(self):
        return [json.loads(line) for line in self.orders_path.read_text().splitlines() if line]

    def _save(self, rows):
        body = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        self.orders_path.write_text(body)

    def create_checkout(self, order_id):
        order = next(row for row in self._orders() if row["order_id"] == order_id)
        return self.client.charges.create(
            amount=order["total_minor"],
            currency=order["currency"],
            source="legacy-browser-token",
            description=order_id,
        )

    def handle_webhook(self, raw_body, signature_header):
        event = json.loads(raw_body.decode("utf-8"))
        rows = self._orders()
        if event.get("type") == "checkout.session.completed":
            order_id = event["data"]["object"]["metadata"]["order_id"]
            for row in rows:
                if row["order_id"] == order_id:
                    row["status"] = "paid"
                    row["paid_event_id"] = event.get("id")
            self._save(rows)
        return {"status": "processed"}


def build_service(environ, orders_path, stripe_client=None):
    client = stripe_client or FakeStripeClient(
        api_key=environ.get("STRIPE_API_KEY", "replace-at-deploy"),
        api_version="2020-08-27",
    )
    return PaymentService(orders_path, client, environ.get("STRIPE_WEBHOOK_SECRET", ""))
