from __future__ import annotations

import inspect
from typing import Any

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.enums import SubscriptionStatus, UserRole
from app.core.security import token_manager
from app.db.mongodb import get_database
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository

ALLOWED_PATH_PREFIXES = (
    '/health',
    '/docs',
    '/openapi.json',
    '/api/v1/auth',
    '/api/v1/settings',
    '/api/v1/restaurant/help-center',
    '/api/v1/subscriptions',
    '/api/v1/subscriptions/user',
    '/api/v1/dashboard',
    '/api/v1/users',
    '/api/v1/support',
)
ONBOARDING_ALLOWED_PATH_PREFIXES = (
    '/api/v1/onboarding',
    '/api/v1/auth',
    '/api/v1/subscriptions/user',
    '/api/v1/upload',
)
RESTAURANT_ROLES = {UserRole.RESTAURANT_OWNER, UserRole.MANAGER, UserRole.STAFF}
BLOCKED_SUBSCRIPTION_STATUSES = {
    SubscriptionStatus.CANCELED,
    SubscriptionStatus.EXPIRED,
    SubscriptionStatus.SUSPENDED,
    SubscriptionStatus.UNSUBSCRIBED,
}


def _subscription_error_details(user: dict, *, reason: str) -> dict[str, Any]:
    return {
        'selection_required': True,
        'reason': reason,
        'subscription_plan_name': user.get('subscription_plan_name'),
        'subscription_plan': user.get('subscription_plan'),
        'subscription_status': user.get('subscription_status'),
    }


class SubscriptionGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == 'OPTIONS' or self._is_allowed_path(request.url.path):
            return await call_next(request)

        authorization = request.headers.get('Authorization', '')
        if not authorization.startswith('Bearer '):
            return await call_next(request)

        token = authorization.removeprefix('Bearer ').strip()
        if not token:
            return await call_next(request)

        try:
            payload = token_manager.decode_token(token)
        except Exception:
            return await call_next(request)

        if payload.get('type') != 'access':
            return await call_next(request)

        db = await self._resolve_database(request)
        user = await UserRepository(db).get_optional_by_id(payload['sub'])
        if not user:
            return await call_next(request)

        if user.get('role') in RESTAURANT_ROLES and not user.get('subscription_plan_name'):
            return JSONResponse(
                status_code=403,
                content={
                    'success': False,
                    'error': {
                        'code': 'subscription_required',
                        'message': 'Select a subscription plan before accessing this resource',
                        'details': _subscription_error_details(user, reason='missing_plan'),
                    },
                },
            )

        if user.get('role') in RESTAURANT_ROLES and user.get('subscription_status') in BLOCKED_SUBSCRIPTION_STATUSES:
            return JSONResponse(
                status_code=403,
                content={
                    'success': False,
                    'error': {
                        'code': 'subscription_required',
                        'message': 'An active subscription is required to access this resource',
                        'details': _subscription_error_details(user, reason='inactive_subscription'),
                    },
                },
            )

        if (
            user.get('role') in RESTAURANT_ROLES
            and not await self._has_completed_onboarding(db, user)
            and not self._is_onboarding_allowed_path(request.url.path)
        ):
            return JSONResponse(
                status_code=403,
                content={
                    'success': False,
                    'error': {
                        'code': 'onboarding_required',
                        'message': 'Complete onboarding before accessing this resource',
                        'details': {'onboarding_required': True},
                    },
                },
            )

        return await call_next(request)

    @staticmethod
    def _is_allowed_path(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES)

    @staticmethod
    def _is_onboarding_allowed_path(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in ONBOARDING_ALLOWED_PATH_PREFIXES)

    @staticmethod
    async def _has_completed_onboarding(db, user: dict) -> bool:
        if user.get('onboarding_completed') is True:
            return True
        profile = await OnboardingProfileRepository(db).get_by_user_id(str(user['_id']))
        return bool(profile and profile.get('onboarding_completed') is True)

    @staticmethod
    async def _resolve_database(request: Request):
        provider = request.app.dependency_overrides.get(get_database, get_database)
        result = provider()
        if inspect.isawaitable(result):
            return await result
        return result

