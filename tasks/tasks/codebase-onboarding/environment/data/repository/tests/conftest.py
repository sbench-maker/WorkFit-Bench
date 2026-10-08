import pytest


@pytest.fixture
def manager_headers():
    return {"X-Actor-ID": "mgr-17", "X-Actor-Role": "manager"}
