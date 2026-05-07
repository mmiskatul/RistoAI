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
    MIGRATIONS = "app_migrations"


class RestaurantCollections:
    DOCUMENTS = "restaurant_documents"
    INVOICES = DOCUMENTS
    MANUAL_ENTRIES = "restaurant_manual_entries"
    FINANCE_SNAPSHOTS = "restaurant_finance_snapshots"
    FINANCE_TRANSACTIONS = "restaurant_finance_transactions"
    DAILY_RECORDS = FINANCE_SNAPSHOTS
    WEEKLY_RECORDS = FINANCE_SNAPSHOTS
    MONTHLY_RECORDS = FINANCE_SNAPSHOTS
    EXPENSES = "restaurant_expenses"
    CASH_DEPOSITS = "restaurant_cash_deposits"
    BANK_ACCOUNTS = "restaurant_bank_accounts"
    INVENTORY_ITEMS = "restaurant_inventory_items"
    INVENTORY_CATEGORIES = "restaurant_inventory_categories"
    INVENTORY_SUPPLIERS = "restaurant_inventory_suppliers"
    CHAT_MESSAGES = "restaurant_chat_messages"
    CHAT_MEMORIES = "restaurant_chat_memories"
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
    CoreCollections.MIGRATIONS,
    RestaurantCollections.INVOICES,
    RestaurantCollections.MANUAL_ENTRIES,
    RestaurantCollections.DAILY_RECORDS,
    RestaurantCollections.WEEKLY_RECORDS,
    RestaurantCollections.MONTHLY_RECORDS,
    RestaurantCollections.FINANCE_TRANSACTIONS,
    RestaurantCollections.EXPENSES,
    RestaurantCollections.CASH_DEPOSITS,
    RestaurantCollections.BANK_ACCOUNTS,
    RestaurantCollections.INVENTORY_ITEMS,
    RestaurantCollections.INVENTORY_CATEGORIES,
    RestaurantCollections.INVENTORY_SUPPLIERS,
    RestaurantCollections.CHAT_MESSAGES,
    RestaurantCollections.CHAT_MEMORIES,
    RestaurantCollections.AI_INSIGHTS,
}
