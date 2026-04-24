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
    assert 'Restaurant Account Responsibility' in editor['content']


def test_public_legal_document_endpoints_return_admin_managed_content():
    app, mock_db = _build_app_with_mock_db()
    admin_id = _seed_admin(mock_db)

    with TestClient(app) as client:
        update_terms_response = client.put(
            '/api/v1/settings/legal-content/terms_of_service',
            headers=_admin_headers(admin_id),
            json={'content': '# Terms of Service\n\nAdmin managed terms content.'},
        )
        update_privacy_response = client.put(
            '/api/v1/settings/legal-content/privacy_policy',
            headers=_admin_headers(admin_id),
            json={'content': '# Privacy Policy\n\nAdmin managed privacy content.'},
        )
        terms_response = client.get('/api/v1/settings/terms-and-conditions')
        privacy_response = client.get('/api/v1/settings/privacy-policy')

    assert update_terms_response.status_code == 200
    assert update_privacy_response.status_code == 200

    assert terms_response.status_code == 200
    assert terms_response.json()['key'] == 'terms_of_service'
    assert terms_response.json()['title'] == 'Terms of Service'
    assert 'Admin managed terms content.' in terms_response.json()['content']
    assert terms_response.json()['updated_by'] == 'Admin User'

    assert privacy_response.status_code == 200
    assert privacy_response.json()['key'] == 'privacy_policy'
    assert privacy_response.json()['title'] == 'Privacy Policy'
    assert 'Admin managed privacy content.' in privacy_response.json()['content']
    assert privacy_response.json()['updated_by'] == 'Admin User'


def test_admin_settings_update_and_legal_content_save_persist():
    app, mock_db = _build_app_with_mock_db()
    admin_id = _seed_admin(mock_db)

    with TestClient(app) as client:
        update_response = client.put(
            '/api/v1/settings/overview',
            headers=_admin_headers(admin_id),
            data={
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


def test_admin_settings_update_uploads_image_and_stores_url():
    app, mock_db = _build_app_with_mock_db()
    admin_id = _seed_admin(mock_db)

    with TestClient(app) as client:
        response = client.put(
            '/api/v1/settings/overview',
            headers=_admin_headers(admin_id),
            data={
                'platform_name': 'Risto AI',
                'support_email': 'support@risto-ai.com',
                'default_language': 'English (United States)',
            },
            files={
                'profile_image': ('admin.webp', b'fake-image-bytes', 'image/webp'),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    profile_image_url = payload['settings']['profile_image_url']
    assert profile_image_url is not None
    assert profile_image_url.startswith('https://example.com/admin-settings/')
    assert '/profile-image/' in profile_image_url

    stored_admin = asyncio.run(mock_db['users'].find_one({'_id': admin_id}))
    assert stored_admin is not None
    assert stored_admin['avatar_url'] == profile_image_url


def test_legacy_default_legal_content_is_backfilled_with_richer_terms():
    app, mock_db = _build_app_with_mock_db()
    _seed_admin(mock_db)

    asyncio.run(
        mock_db['admin_settings'].insert_one(
            {
                'singleton_key': 'platform_settings',
                'platform_name': 'Risto AI',
                'support_email': 'support@risto-ai.com',
                'default_language': 'English (United States)',
                'legal_documents': {
                    'terms_of_service': {
                        'title': 'Terms of Service',
                        'content': '# Terms of Service\n\n## 1. Acceptance of Terms\nBy accessing and using our platform, you agree to be bound by these Terms of Service and all applicable laws and regulations.',
                    },
                    'privacy_policy': {
                        'title': 'Privacy Policy',
                        'content': '# Privacy Policy\n\n## 1. Information We Collect\nWe collect account, restaurant, and operational data required to provide and improve the platform.',
                    },
                },
            }
        )
    )

    with TestClient(app) as client:
        terms_response = client.get('/api/v1/settings/terms-and-conditions')
        privacy_response = client.get('/api/v1/settings/privacy-policy')

    assert terms_response.status_code == 200
    assert 'Restaurant Account Responsibility' in terms_response.json()['content']
    assert 'Billing and Subscription' in terms_response.json()['content']

    assert privacy_response.status_code == 200
    assert 'How We Use Information' in privacy_response.json()['content']
