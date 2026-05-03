from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import Settings
from app.core.enums import SubscriptionPlan
from app.core.exceptions import ValidationException

try:
    import stripe
except Exception:  # pragma: no cover - optional dependency fallback
    stripe = None


class StripeBillingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if stripe is not None:
            stripe.api_key = settings.stripe_secret_key

    def _require_client(self):
        if stripe is None:
            raise ValidationException('Stripe SDK is not installed')
        if not self.settings.stripe_secret_key:
            raise ValidationException('Stripe is not configured')
        return stripe

    def _price_id_for_cycle(self, billing_cycle: SubscriptionPlan) -> str:
        if billing_cycle == SubscriptionPlan.ONE_YEAR and self.settings.stripe_price_id_yearly:
            return self.settings.stripe_price_id_yearly
        if billing_cycle == SubscriptionPlan.ONE_MONTH and self.settings.stripe_price_id_monthly:
            return self.settings.stripe_price_id_monthly
        raise ValidationException('Stripe price id is not configured for the selected billing cycle')

    async def create_customer(self, *, email: str, name: str, metadata: dict[str, str]) -> dict[str, Any]:
        client = self._require_client()
        return await asyncio.to_thread(client.Customer.create, email=email, name=name, metadata=metadata)

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        billing_cycle: SubscriptionPlan,
        metadata: dict[str, str],
        trial_days: int = 0,
    ) -> dict[str, Any]:
        client = self._require_client()
        subscription_data: dict[str, Any] = {'metadata': metadata}
        if trial_days > 0:
            subscription_data['trial_period_days'] = trial_days
        return await asyncio.to_thread(
            client.checkout.Session.create,
            customer=customer_id,
            mode='subscription',
            success_url=self.settings.stripe_checkout_success_url,
            cancel_url=self.settings.stripe_checkout_cancel_url,
            line_items=[{'price': self._price_id_for_cycle(billing_cycle), 'quantity': 1}],
            metadata=metadata,
            subscription_data=subscription_data,
        )

    async def create_customer_portal_session(self, *, customer_id: str) -> dict[str, Any]:
        client = self._require_client()
        return await asyncio.to_thread(
            client.billing_portal.Session.create,
            customer=customer_id,
            return_url=self.settings.stripe_customer_portal_return_url,
        )

    async def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        client = self._require_client()
        return await asyncio.to_thread(client.Subscription.retrieve, subscription_id, expand=['items.data.price'])

    async def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        client = self._require_client()
        return await asyncio.to_thread(client.Subscription.cancel, subscription_id)

    def construct_event(self, payload: bytes, sig_header: str | None) -> dict[str, Any]:
        client = self._require_client()
        if not sig_header or not self.settings.stripe_webhook_secret:
            raise ValidationException('Stripe webhook secret is not configured')
        return client.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=self.settings.stripe_webhook_secret)
