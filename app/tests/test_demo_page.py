from fastapi.testclient import TestClient

from app.main import create_app


def test_landing_preview_returns_html():
    app = create_app(testing=True)

    with TestClient(app) as client:
        response = client.get('/preview/landing')

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert 'ARCH CITY' in response.text
    assert 'Create Account' in response.text
