from datetime import datetime
from pydantic import BaseModel, Field


class ApprovalCommand(BaseModel):
    reason: str = Field(min_length=8, max_length=240)


class AccessRequestRead(BaseModel):
    id: str
    employee_id: str
    system_slug: str
    status: str
    decided_at: datetime | None
