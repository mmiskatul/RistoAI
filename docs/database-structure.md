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

- `restaurant_documents`
  - One document per confirmed uploaded document or invoice.
  - Source of truth for AI/manual document extraction results.
  - Replaces the legacy `restaurant_invoices` collection name.
  - Tenant scoped by `tenant_id`.

- `restaurant_manual_entries`
  - One document per restaurant per business date.
  - Stores raw manual entry payload from Method 1 or Method 2.
  - Tenant scoped by `tenant_id`.

- `restaurant_expenses`
  - Direct manual expense entries plus source-linked display rows from daily data, documents, and inventory purchases.
  - Source-linked rows keep `source_kind` and `source_id`; they must be changed by editing or deleting their source record.

- `restaurant_cash_deposits`
  - Bank deposit and cash-drop records plus source-linked POS, cash-in, bank transfer, withdrawal, cash-out, and cash-expense rows from daily data/documents.
  - Source-linked rows have their own collection `_id` plus `source_kind`, `source_id`, and `source_subtype`; delete or edit them from the source record.

- `restaurant_inventory_items`
  - Current stock state and stock history.
  - Inventory is stored separately from expenses; purchase costs create source-linked expense rows for reporting.

- `restaurant_chat_messages`
  - Restaurant AI chat conversation history.

- `restaurant_ai_insights`
  - Generated restaurant insights.

### Aggregate Collections

- `restaurant_finance_snapshots`
  - One aggregate document per tenant and period key.
  - Stores `period_type` of `day`, `week`, or `month`.
  - Keeps compatibility top-level fields such as `total_revenue`, `total_expenses`, `cash_available`, and `bank_deposits_total`.
  - Also stores normalized nested groups:
    - `revenue_summary`
    - `expense_summary`
    - `deposit_summary`
    - `cash_summary`
    - `operations_summary`
  - Daily, weekly, and monthly repository accessors all read from this same collection.

- `restaurant_finance_transactions`
  - Immutable-like normalized finance movement rows derived from source records.
  - Each row is linked to a `source_kind` and `source_id`.
  - Transaction metadata now classifies whether the row affects revenue, cash, or profit.
  - `metadata.ledger_group` values:
    - `sale`
    - `expense`
    - `cash_movement`
    - `other`

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

## Finance Modeling Notes

- Sales increase revenue once.
- Deposits do not create new revenue; they only move already-earned money.
- Cash withdrawals and cash-out operations reduce available cash but do not count as business expenses.
- Only true expenses, such as `expenses_in_cash` and expense documents, reduce profit.
