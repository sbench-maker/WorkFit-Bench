from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from rosterly.api.dependencies import require_manager
from rosterly.api.schemas import AccessRequestRead, ApprovalCommand
from rosterly.db.session import get_db
from rosterly.services.approvals import ApprovalService

router = APIRouter(tags=["access-requests"])


@router.post(
    "/access-requests/{request_id}/approve",
    response_model=AccessRequestRead,
)
def approve_request(
    request_id: str,
    command: ApprovalCommand,
    actor_id: Annotated[str, Depends(require_manager)],
    db: Annotated[Session, Depends(get_db)],
) -> AccessRequestRead:
    return ApprovalService(db).approve(request_id, actor_id, command.reason)
