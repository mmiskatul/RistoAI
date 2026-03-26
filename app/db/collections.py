from __future__ import annotations


class CoreCollections:
    USERS = "users"
    AUTH_CODES = "auth_codes"
    ONBOARDING_PROFILES = "onboarding_profiles"
    SUBSCRIPTION_PLANS = "subscription_plan"
    USER_SUBSCRIPTIONS = "user_subscriptions"
    SUPPORT_TICKETS = "support_tickets"
    COUPONS = "coupons"
    ADMIN_SETTINGS = "admin_settings"


class RestaurantCollections:
    INVOICES = "restaurant_invoices"
    MANUAL_ENTRIES = "restaurant_manual_entries"
    DAILY_RECORDS = "restaurant_daily_records"
    WEEKLY_RECORDS = "restaurant_weekly_records"
    MONTHLY_RECORDS = "restaurant_monthly_records"
    EXPENSES = "restaurant_expenses"
    CASH_DEPOSITS = "restaurant_cash_deposits"
    INVENTORY_ITEMS = "restaurant_inventory_items"
    CHAT_MESSAGES = "restaurant_chat_messages"
    AI_INSIGHTS = "restaurant_ai_insights"


ALL_COLLECTIONS = {
    CoreCollections.USERS,
    CoreCollections.AUTH_CODES,
    CoreCollections.ONBOARDING_PROFILES,
    CoreCollections.SUBSCRIPTION_PLANS,
    CoreCollections.USER_SUBSCRIPTIONS,
    CoreCollections.SUPPORT_TICKETS,
    CoreCollections.COUPONS,
    CoreCollections.ADMIN_SETTINGS,
    RestaurantCollections.INVOICES,
    RestaurantCollections.MANUAL_ENTRIES,
    RestaurantCollections.DAILY_RECORDS,
    RestaurantCollections.WEEKLY_RECORDS,
    RestaurantCollections.MONTHLY_RECORDS,
    RestaurantCollections.EXPENSES,
    RestaurantCollections.CASH_DEPOSITS,
    RestaurantCollections.INVENTORY_ITEMS,
    RestaurantCollections.CHAT_MESSAGES,
    RestaurantCollections.AI_INSIGHTS,
}
