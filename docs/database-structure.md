# Database Structure

## Core Collections

- `users`: authenticated accounts and current subscription snapshot fields.
- `auth_codes`: verification and password reset codes with TTL expiry.
- `onboarding_profiles`: onboarding answers and restaurant setup data.
- `subscription_plan`: default and visible plan definitions.
- `user_subscriptions`: immutable subscription history records.
- `support_tickets`: support threads and ticket status.
- `coupons`: discount and promotional codes.

## Restaurant Collections

### Raw Source Collections

- `restaurant_invoices`
  - One document per confirmed uploaded invoice.
  - Source of truth for AI/manual invoice extraction results.
  - Tenant scoped by `tenant_id`.

- `restaurant_manual_entries`
  - One document per restaurant per business date.
  - Stores raw manual entry payload from Method 1 or Method 2.
  - Tenant scoped by `tenant_id`.

- `restaurant_expenses`
  - Manual expense entries.
  - Kept separate from invoices so invoice ingestion does not mutate expense rows automatically.

- `restaurant_cash_deposits`
  - Bank deposit and cash-drop records.

- `restaurant_inventory_items`
  - Current stock state and stock history.

- `restaurant_chat_messages`
  - Restaurant AI chat conversation history.

- `restaurant_ai_insights`
  - Generated restaurant insights.

### Aggregate Collections

- `restaurant_daily_records`
  - One aggregate document per `tenant_id + business_date`.
  - Summarizes manual entry revenue, invoice totals, manual expense totals, covers, and profit.

- `restaurant_weekly_records`
  - One aggregate document per `tenant_id + week_start_date`.
  - Summarizes the week for list/detail reporting.

- `restaurant_monthly_records`
  - One aggregate document per `tenant_id + month_key` (`YYYY-MM`).
  - Summarizes the month for reporting.

## Design Rules

- Raw collections store source events and edited source documents.
- Aggregate collections store precomputed reporting summaries only.
- Every restaurant collection is tenant scoped with `tenant_id`.
- Date-granular aggregates are rebuilt when manual entries, invoices, or expenses change.
- Public API routes stay stable even if internal storage changes.

## Recommended Read/Write Flow

1. Write raw data first.
2. Recompute the impacted daily aggregate.
3. Recompute the impacted week aggregate.
4. Recompute the impacted month aggregate.
5. Read reporting screens from aggregate collections where possible.
6. Read detail/edit screens from raw collections.
