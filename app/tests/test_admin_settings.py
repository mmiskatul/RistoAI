from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.core.enums import UserRole
from app.core.security import token_manager
from app.db.mongodb import get_database
from app.main import create_app


def _build_app_with_mock_db():
    app = create_app(testing=True)
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client['ristoai_test']

    async def override_get_database():
        return mock_db

    app.dependency_overrides[get_database] = override_get_database
    return app, mock_db


def _admin_headers(admin_id: ObjectId) -> dict[str, str]:
    token = token_manager.create_access_token(str(admin_id), UserRole.SUPER_ADMIN)
    return {'Authorization': f'Bearer {token}'}


def _seed_admin(mock_db) -> ObjectId:
    admin_id = ObjectId()
    asyncio.run(
        mock_db['users'].insert_one(
            {
                '_id': admin_id,
                'email': 'admin@example.com',
                'full_name': 'Admin User',
                'avatar_url': 'https://example.com/admin.png',
                'hashed_password': 'x',
                'role': UserRole.SUPER_ADMIN,
                'is_active': True,
                'email_verified': True,
                'created_at': datetime(2026, 3, 12, tzinfo=UTC),
                'updated_at': datetime(2026, 3, 12, tzinfo=UTC),
            }
        )
    )
    return admin_id


def test_admin_settings_overview_and_legal_editor_are_connected():
    app, mock_db = _build_app_with_mock_db()
    admin_id = _seed_admin(mock_db)

    with TestClient(app) as client:
        overview_response = client.get('/api/v1/settings/overview', headers=_admin_headers(admin_id))
        editor_response = client.get('/api/v1/settings/legal-content?tab=terms', headers=_admin_headers(admin_id))

    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview['platform_name'] == 'Risto AI'
    assert overview['support_email'] == 'support@risto-ai.com'
    assert overview['legal_pages'][0]['title'] == 'Terms & Conditions'
    assert overview['legal_pages'][0]['edit_endpoint'] == '/api/v1/settings/legal-content?tab=terms'
    assert overview['legal_pages'][1]['title'] == 'Privacy Policy'
    assert overview['profile_image_url'] == 'https://example.com/admin.png'

    assert editor_response.status_code == 200
    editor = editor_response.json()
    assert editor['active_tab'] == 'terms'
    assert editor['tabs'][0] == {'key': 'terms', 'label': 'Terms of Service', 'active': True}
    assert editor['tabs'][1] == {'key': 'privacy', 'label': 'Privacy Policy', 'active': False}
    assert editor['save_endpoint'] == '/api/v1/settings/legal-content/terms_of_service'
    assert '# Terms of Service' in editor['content']


def test_admin_settings_update_and_legal_content_save_persist():
    app, mock_db = _build_app_with_mock_db()
    admin_id = _seed_admin(mock_db)

    with TestClient(app) as client:
        update_response = client.put(
            '/api/v1/settings/overview',
            headers=_admin_headers(admin_id),
            json={
                'platform_name': 'Horizon SaaS',
                'support_email': 'support@horizon-saas.com',
                'default_language': 'English (United States)',
            },
        )
        legal_update_response = client.put(
            '/api/v1/settings/legal-content/privacy_policy',
            headers=_admin_headers(admin_id),
            json={'content': '# Privacy Policy\n\nUpdated content.'},
        )
        refreshed_overview = client.get('/api/v1/settings/overview', headers=_admin_headers(admin_id))
        refreshed_editor = client.get('/api/v1/settings/legal-content?tab=privacy', headers=_admin_headers(admin_id))

    assert update_response.status_code == 200
    assert update_response.json()['settings']['platform_name'] == 'Horizon SaaS'
    assert update_response.json()['settings']['support_email'] == 'support@horizon-saas.com'

    assert legal_update_response.status_code == 200
    assert legal_update_response.json()['editor']['active_tab'] == 'privacy'
    assert '# Privacy Policy' in legal_update_response.json()['editor']['content']
    assert 'Updated content.' in legal_update_response.json()['editor']['content']

    assert refreshed_overview.status_code == 200
    assert refreshed_overview.json()['platform_name'] == 'Horizon SaaS'
    assert refreshed_editor.status_code == 200
    assert refreshed_editor.json()['active_tab'] == 'privacy'
    assert 'Updated content.' in refreshed_editor.json()['content']
