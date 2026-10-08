import pytest
from fastapi import HTTPException
from rosterly.domain.access_request import approve


def test_pending_request_can_be_approved(pending_request):
    approve(pending_request, actor_id="mgr-17", reason="Role requires payroll access")
    assert pending_request.status == "approved"


def test_non_pending_request_conflicts(approved_request):
    with pytest.raises(HTTPException, match="not pending"):
        approve(approved_request, actor_id="mgr-17", reason="Role requires payroll access")
