from datetime import UTC, datetime
from fastapi import HTTPException


def approve(entity, *, actor_id: str, reason: str) -> None:
    if entity.status != "pending":
        raise HTTPException(status_code=409, detail="request is not pending")
    entity.status = "approved"
    entity.decided_by = actor_id
    entity.decision_reason = reason
    entity.decided_at = datetime.now(UTC)
