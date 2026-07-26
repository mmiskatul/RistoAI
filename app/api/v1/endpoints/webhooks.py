from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.config.settings import get_settings
from app.core.enums import SubscriptionPlan, SubscriptionStatus
from app.db.mongodb import get_database

router = APIRouter()
logger = logging.getLogger(__name__)


class RevenueCatWebhookPayload(BaseModel):
    event: dict[str, Any]


def _expiration(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC) if value else None
    except (TypeError, ValueError, OSError):
        return None


def _billing_cycle(product_id: str) -> SubscriptionPlan:
    product = product_id.lower()
    return SubscriptionPlan.ONE_YEAR if any(token in product for token in ('annual', 'year', 'yearly', '12_month')) else SubscriptionPlan.ONE_MONTH


@router.post('/revenuecat', include_in_schema=False)
async def handle_revenuecat_webhook(
    payload: RevenueCatWebhookPayload,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    if settings.revenuecat_webhook_secret and authorization != f'Bearer {settings.revenuecat_webhook_secret}':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid webhook authorization header')

    event = payload.event
    event_type = str(event.get('type') or '')
    app_user_id = str(event.get('app_user_id') or '').strip()
    if not app_user_id:
        return {'status': 'ignored', 'reason': 'No app_user_id provided'}

    active_events = {'INITIAL_PURCHASE', 'RENEWAL', 'UNCANCELLATION', 'NON_RENEWING_PURCHASE'}
    inactive_events = {'CANCELLATION', 'EXPIRATION'}
    if event_type not in active_events | inactive_events | {'BILLING_ISSUE'}:
        logger.info('Unhandled RevenueCat event type: %s', event_type)
        return {'status': 'ignored', 'event_type': event_type}

    if ObjectId.is_valid(app_user_id):
        user_filter: dict[str, Any] = {'$or': [{'_id': app_user_id}, {'_id': ObjectId(app_user_id)}]}
    else:
        user_filter = {'_id': app_user_id}

    now = datetime.now(UTC)
    if event_type in active_events:
        product_id = str(event.get('product_id') or '')
        update_data = {
            'is_pro': True,
            'subscription_status': SubscriptionStatus.ACTIVE,
            'subscription_plan': _billing_cycle(product_id),
            'subscription_plan_name': product_id or 'RistoAI Premium',
            'subscription_platform': str(event.get('store') or 'revenuecat'),
            'subscription_started_at': _expiration(event.get('purchased_at_ms')) or now,
            'subscription_expires_at': _expiration(event.get('expiration_at_ms')),
            'updated_at': now,
        }
    elif event_type in inactive_events:
        update_data = {
            'is_pro': False,
            'subscription_status': SubscriptionStatus.EXPIRED if event_type == 'EXPIRATION' else SubscriptionStatus.CANCELED,
            'subscription_expires_at': _expiration(event.get('expiration_at_ms')),
            'updated_at': now,
        }
    else:
        update_data = {'subscription_status': SubscriptionStatus.SUSPENDED, 'updated_at': now}

    db = await get_database()
    result = await db['users'].update_one(user_filter, {'$set': update_data})
    if result.matched_count == 0:
        logger.warning('RevenueCat webhook user not found for ID: %s', app_user_id)
        return {'status': 'user_not_found', 'app_user_id': app_user_id}

    logger.info('Processed RevenueCat %s for user %s', event_type, app_user_id)
    return {'status': 'success', 'event_type': event_type, 'app_user_id': app_user_id}
