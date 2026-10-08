from sqlalchemy.orm import Session

from rosterly.db.outbox import queue_event
from rosterly.db.repositories import AccessRequestRepository
from rosterly.domain.access_request import approve


class ApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.requests = AccessRequestRepository(db)

    def approve(self, request_id: str, actor_id: str, reason: str):
        request = self.requests.get_for_update(request_id)
        approve(request, actor_id=actor_id, reason=reason)
        queue_event(
            self.db,
            topic="access_request.approved",
            payload={"request_id": request.id, "system_slug": request.system_slug},
        )
        self.db.commit()
        self.db.refresh(request)
        return request
