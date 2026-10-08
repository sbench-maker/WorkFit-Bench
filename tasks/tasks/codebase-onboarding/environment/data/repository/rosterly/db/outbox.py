from uuid import uuid4
from sqlalchemy.orm import Session

from rosterly.db.models import OutboxEvent


def queue_event(db: Session, *, topic: str, payload: dict) -> None:
    db.add(OutboxEvent(id=str(uuid4()), topic=topic, payload=payload))
