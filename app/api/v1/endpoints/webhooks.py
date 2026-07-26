from datetime import datetime, timezone
import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.config.settings import get_settings
from app.db.mongodb import get_database

router = APIRouter()
logger = logging.getLogger(__name__)


class RevenueCatWebhookPayload(BaseModel):
    event: Dict[str, Any]


@router.post("/revenuecat")
async def handle_revenuecat_webhook(
    payload: RevenueCatWebhookPayload,
    authorization: str | None = Header(None),
):
    settings = get_settings()
    expected_secret = getattr(settings, "REVENUECAT_WEBHOOK_SECRET", None)

    if expected_secret and authorization != f"Bearer {expected_secret}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook authorization header",
        )

    event = payload.event
    event_type = event.get("type")
    app_user_id = event.get("app_user_id")

    if not app_user_id:
        return {"status": "ignored", "reason": "No app_user_id provided"}

    db = get_database()
    users_collection = db["users"]

    expiration_at_ms = event.get("expiration_at_ms")
    expires_at = (
        datetime.fromtimestamp(expiration_at_ms / 1000.0, tz=timezone.utc)
        if expiration_at_ms
        else None
    )

    product_id = event.get("product_id", "")
    store = event.get("store", "")

    if event_type in ["INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "NON_RENEWING_PURCHASE"]:
        update_data = {
            "is_pro": True,
            "subscription_status": "active",
            "subscription_plan_name": product_id or "RistoAI Premium",
            "subscription_platform": store or "revenuecat",
            "subscription_expires_at": expires_at,
            "updated_at": datetime.now(timezone.utc),
        }
    elif event_type in ["CANCELLATION", "EXPIRATION"]:
        update_data = {
            "is_pro": False,
            "subscription_status": "expired",
            "updated_at": datetime.now(timezone.utc),
        }
    elif event_type == "BILLING_ISSUE":
        update_data = {
            "subscription_status": "grace_period",
            "updated_at": datetime.now(timezone.utc),
        }
    else:
        logger.info(f"Unhandled RevenueCat event type: {event_type}")
        return {"status": "ignored", "event_type": event_type}

    from bson import ObjectId
    user_filter = {"_id": app_user_id}
    if ObjectId.is_valid(app_user_id):
        user_filter = {"$or": [{"_id": app_user_id}, {"_id": ObjectId(app_user_id)}]}

    result = await users_collection.update_one(
        user_filter,
        {"$set": update_data},
    )

    if result.matched_count == 0:
        logger.warning(f"RevenueCat webhook user not found for ID: {app_user_id}")
        return {"status": "user_not_found", "app_user_id": app_user_id}

    logger.info(f"Successfully processed RevenueCat {event_type} for user {app_user_id}")
    return {"status": "success", "event_type": event_type, "app_user_id": app_user_id}
