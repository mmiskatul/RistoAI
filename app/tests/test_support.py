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
from app.tests.helpers import register_and_login


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
                'phone': '+10000000000',
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


def test_restaurant_can_list_and_view_only_their_own_tickets():
    app, mock_db = _build_app_with_mock_db()
    _seed_admin(mock_db)

    with TestClient(app) as client:
        owner_headers = register_and_login(
            client,
            {
                'full_name': 'Owner One',
                'email': 'owner-one@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550001111',
            },
        )
        other_headers = register_and_login(
            client,
            {
                'full_name': 'Owner Two',
                'email': 'owner-two@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550002222',
            },
        )

        own_create = client.post(
            '/api/v1/support/tickets',
            headers=owner_headers,
            json={'subject': 'Need help', 'message': 'My issue details here.', 'priority': 'normal'},
        )
        other_create = client.post(
            '/api/v1/support/tickets',
            headers=other_headers,
            json={'subject': 'Other issue', 'message': 'Other issue details here.', 'priority': 'normal'},
        )

        own_ticket_id = own_create.json()['ticket']['id']
        other_ticket_id = other_create.json()['ticket']['id']

        list_response = client.get('/api/v1/support/user/tickets?page=1&page_size=10', headers=owner_headers)
        detail_response = client.get(f'/api/v1/support/user/tickets/{own_ticket_id}', headers=owner_headers)
        forbidden_response = client.get(f'/api/v1/support/user/tickets/{other_ticket_id}', headers=owner_headers)

    assert list_response.status_code == 200
    assert list_response.json()['total'] == 1
    assert list_response.json()['items'][0]['issue_subject'] == 'Need help'
    assert detail_response.status_code == 200
    assert detail_response.json()['subject'] == 'Need help'
    assert forbidden_response.status_code == 404
    assert forbidden_response.json()['error']['message'] == 'Support ticket not found'


def test_restaurant_can_create_support_ticket_and_admin_can_manage_it():
    app, mock_db = _build_app_with_mock_db()
    admin_id = _seed_admin(mock_db)

    with TestClient(app) as client:
        restaurant_headers = register_and_login(
            client,
            {
                'full_name': 'Alex Rivera',
                'email': 'alex@example.com',
                'password': 'OwnerPass123',
                'phone': '+15550009999',
            },
        )

        create_response = client.post(
            '/api/v1/support/tickets',
            headers=restaurant_headers,
            json={
                'subject': 'Order not received',
                'message': 'I placed an order but it never arrived.',
                'priority': 'high',
                'attachment_name': 'screenshot_order_status.png',
                'attachment_url': 'https://example.com/screenshot.png',
            },
        )

        assert create_response.status_code == 200
        created_ticket = create_response.json()['ticket']
        ticket_id = created_ticket['id']

        management_response = client.get('/api/v1/support/management?page=1&page_size=10', headers=_admin_headers(admin_id))
        detail_response = client.get(f'/api/v1/support/tickets/{ticket_id}', headers=_admin_headers(admin_id))
        reply_response = client.post(
            f'/api/v1/support/tickets/{ticket_id}/reply',
            headers=_admin_headers(admin_id),
            json={'message': 'We are checking your order now.', 'is_internal': False},
        )
        resolve_response = client.post(f'/api/v1/support/tickets/{ticket_id}/resolve', headers=_admin_headers(admin_id))

    tickets = asyncio.run(mock_db['support_tickets'].find().to_list(length=None))
    assert len(tickets) == 1
    assert tickets[0]['subject'] == 'Order not received'
    assert tickets[0]['priority'] == 'high'

    assert management_response.status_code == 200
    management_payload = management_response.json()
    assert management_payload['page_title'] == 'Support Management'
    assert management_payload['page_subtitle'] == 'Track and resolve restaurant support requests across the platform.'
    assert management_payload['search_placeholder'] == 'Search tickets, restaurants...'
    assert management_payload['filter_button_label'] == 'Filters'
    assert management_payload['filter_chips'][0] == {'key': 'all', 'label': 'All'}
    assert management_payload['summary']['open_tickets'] == 1
    assert management_payload['summary']['resolved_tickets'] == 0
    assert management_payload['summary_cards'][0] == {
        'key': 'open_tickets',
        'label': 'Open Tickets',
        'value': 1,
        'value_formatted': '1',
    }
    assert management_payload['summary_cards'][1] == {
        'key': 'resolved_tickets',
        'label': 'Resolved Tickets',
        'value': 0,
        'value_formatted': '0',
    }
    assert management_payload['table_columns'][0] == {'key': 'user_restaurant', 'label': 'User & Restaurant'}
    assert management_payload['pagination_label'] == 'Showing 1 to 1 of 1 tickets'
    assert management_payload['items'][0]['user_name'] == 'Alex Rivera'
    assert management_payload['items'][0]['user_restaurant_label'] == 'Alex Rivera'
    assert management_payload['items'][0]['issue_subject'] == 'Order not received'
    assert management_payload['items'][0]['issue_subject_label'] == 'Order not received'
    assert management_payload['items'][0]['status_label'] == 'Open'
    assert management_payload['items'][0]['priority_label'] == 'High'
    assert management_payload['items'][0]['date_formatted'] == 'Mar 26, 2026'
    assert management_payload['items'][0]['view_endpoint'].endswith(ticket_id)
    assert management_payload['items'][0]['actions_menu'][0]['label'] == 'View'
    assert management_payload['items'][0]['actions_menu'][1]['label'] == 'Resolve Ticket'

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload['customer']['user_name'] == 'Alex Rivera'
    assert detail_payload['messages'][0]['attachment_name'] == 'screenshot_order_status.png'

    assert reply_response.status_code == 200
    assert len(reply_response.json()['ticket']['messages']) == 2
    assert reply_response.json()['ticket']['messages'][1]['author_role'] == 'admin'

    assert resolve_response.status_code == 200
    assert resolve_response.json()['ticket']['status'] == 'resolved'
