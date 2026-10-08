def test_manager_can_approve(client, manager_headers):
    response = client.post(
        "/api/v1/access-requests/ar-12/approve",
        headers=manager_headers,
        json={"reason": "Role requires payroll access"},
    )
    assert response.status_code == 200


def test_non_manager_is_forbidden(client):
    response = client.post(
        "/api/v1/access-requests/ar-12/approve",
        headers={"X-Actor-ID": "emp-22", "X-Actor-Role": "employee"},
        json={"reason": "I would like payroll access"},
    )
    assert response.status_code == 403
