from typing import Annotated
from fastapi import Header, HTTPException


def require_manager(
    actor_id: Annotated[str, Header(alias="X-Actor-ID")],
    actor_role: Annotated[str, Header(alias="X-Actor-Role")],
) -> str:
    if actor_role != "manager":
        raise HTTPException(status_code=403, detail="manager role required")
    return actor_id
