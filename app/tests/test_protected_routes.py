from __future__ import annotations


def test_protected_route_requires_token(client):
    response = client.get("/api/v1/restaurants")
    assert response.status_code == 401
