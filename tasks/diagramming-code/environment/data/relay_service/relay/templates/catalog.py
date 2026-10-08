"""Select fixed templates for validated delivery event kinds."""


APPROVED_TEMPLATES = {
    "invoice.ready": "Invoice {{event_id}} is ready for {{recipient}}.",
    "shipment.delayed": "Shipment update for {{recipient}}.",
    "account.welcome": "Welcome {{recipient}}.",
}


def select_template(kind: str) -> str:
    try:
        return APPROVED_TEMPLATES[kind]
    except KeyError as exc:
        raise ValueError("no approved template for event kind") from exc
