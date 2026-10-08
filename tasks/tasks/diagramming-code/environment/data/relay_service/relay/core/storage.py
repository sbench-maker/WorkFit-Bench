"""In-memory fixture records; this module does not use a real database."""

from typing import Any


TABLES: dict[str, dict[str, dict[str, Any]]] = {
    "events": {
        "evt_replay_01": {
            "event_id": "evt_replay_01",
            "kind": "shipment.delayed",
            "recipient": "fictional-recipient",
            "attributes": {"delay_hours": "6"},
        }
    },
    "operators": {
        "operator_fixture": {
            "operator_id": "operator_fixture",
            "role": "delivery-admin",
        }
    },
}


def read_record(table: str, record_id: str) -> dict[str, Any]:
    try:
        return dict(TABLES[table][record_id])
    except KeyError as exc:
        raise LookupError(f"missing {table} record") from exc
