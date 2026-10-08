from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from rosterly.db.models import AccessRequest


class AccessRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_update(self, request_id: str) -> AccessRequest:
        statement = (
            select(AccessRequest)
            .where(AccessRequest.id == request_id)
            .with_for_update()
        )
        entity = self.db.scalar(statement)
        if entity is None:
            raise HTTPException(status_code=404, detail="request not found")
        return entity
