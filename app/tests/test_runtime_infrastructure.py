from __future__ import annotations

import pytest

from app.config.settings import Settings


def test_healthcheck_reports_testing_database_state(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert payload["service"] == "RistoAI"


def test_request_context_headers_are_attached(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-MS"]) >= 0


def test_settings_reject_invalid_mongodb_pool_configuration():
    with pytest.raises(ValueError, match="MONGODB_MIN_POOL_SIZE cannot exceed MONGODB_MAX_POOL_SIZE"):
        Settings(
            MONGODB_MIN_POOL_SIZE=5,
            MONGODB_MAX_POOL_SIZE=2,
        )
