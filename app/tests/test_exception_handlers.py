from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.main import create_app


class MessageResponse(BaseModel):
    message: str



def test_http_exception_returns_standard_error_payload():
    app = create_app(testing=True)

    @app.get('/test/http-exception')
    async def http_exception_route() -> None:
        raise HTTPException(status_code=404, detail='Endpoint not found')

    with TestClient(app) as client:
        response = client.get('/test/http-exception')

    assert response.status_code == 404
    assert response.json() == {
        'success': False,
        'error': {
            'code': 'not_found',
            'message': 'Endpoint not found',
            'details': {},
        },
    }



def test_response_validation_error_returns_standard_error_payload():
    app = create_app(testing=True)

    @app.get('/test/response-validation', response_model=MessageResponse)
    async def response_validation_route() -> dict[str, str]:
        return {'wrong': 'shape'}

    with TestClient(app) as client:
        response = client.get('/test/response-validation')

    assert response.status_code == 500
    payload = response.json()
    assert payload['error']['code'] == 'response_validation_error'
    assert payload['error']['message'] == 'Response validation failed'
    assert payload['error']['details']['errors'][0]['loc'] == ['response', 'message']



def test_request_validation_error_serializes_exception_context():
    app = create_app(testing=True)

    with TestClient(app) as client:
        response = client.post(
            '/api/v1/auth/restaurant/register',
            json={
                'full_name': 'Test User',
                'email': 'test@example.com',
                'password': 'stringst',
                'phone': '+15550001111',
            },
        )

    assert response.status_code == 422
    payload = response.json()
    assert payload['error']['code'] == 'validation_error'
    assert payload['error']['details']['errors'][0]['ctx']['error'] == 'Password must include letters and numbers'
