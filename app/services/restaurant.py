from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.exceptions import ValidationException
from app.repositories.restaurant_ops import (
    RestaurantCashDepositRepository,
    RestaurantChatRepository,
    RestaurantDailyRecordRepository,
    RestaurantDocumentRepository,
    RestaurantExpenseRepository,
    RestaurantInsightRepository,
    RestaurantInventoryRepository,
    ScopedRepository,
)
from app.repositories.user import UserRepository
from app.schemas.restaurant import (
    ActivityItemResponse,
    AnalyticsOverviewResponse,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashManagementItemResponse,
    CashManagementSummaryResponse,
    ChartPointResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
    ChatMessageResponse,
    DailyDataCreateRequest,
    DailyDataAddButtonResponse,
    DailyDataEntrySourceResponse,
    DailyDataListItemActionResponse,
    DailyDataListItemResponse,
    DailyDataListResponse,
    DailyDataResponse,
    DailyDataSummaryCardResponse,
    DocumentConfirmRequest,
    DocumentDetailResponse,
    DocumentExtractionResponse,
    DocumentLineItemSchema,
    DocumentListItemResponse,
    DocumentListResponse,
    DocumentSaveRequest,
    DocumentUploadExtractRequest,
    ExpenseCreateRequest,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseSummaryResponse,
    InsightActionResponse,
    InsightDetailResponse,
    InsightSummaryResponse,
    InventoryDetailResponse,
    InventoryHistoryItemResponse,
    InventoryItemResponse,
    InventoryListResponse,
    InventoryStockUpdateRequest,
    MetricCardResponse,
    RestaurantHomeResponse,
    RestaurantProfileResponse,
    RestaurantProfileUpdateRequest,
    QuickActionResponse,
    VatOverviewResponse,
)
from app.services.base import BaseService
from app.services.openai_ops import OpenAIOperationsService
from app.utils.pagination import build_pagination_meta


class RestaurantOperationsService(BaseService):
    VAT_RATE = 0.1

    def __init__(
        self,
        user_repository: UserRepository,
        document_repository: RestaurantDocumentRepository,
        expense_repository: RestaurantExpenseRepository,
        cash_repository: RestaurantCashDepositRepository,
        daily_record_repository: RestaurantDailyRecordRepository,
        inventory_repository: RestaurantInventoryRepository,
        chat_repository: RestaurantChatRepository,
        insight_repository: RestaurantInsightRepository,
        openai_service: OpenAIOperationsService,
    ) -> None:
        self.user_repository = user_repository
        self.document_repository = document_repository
        self.expense_repository = expense_repository
        self.cash_repository = cash_repository
        self.daily_record_repository = daily_record_repository
        self.inventory_repository = inventory_repository
        self.chat_repository = chat_repository
        self.insight_repository = insight_repository
        self.openai_service = openai_service

    async def get_home(self, current_user: dict) -> RestaurantHomeResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=90)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=90)
        cash_deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=20)
        insights = await self._get_or_generate_insights(scope_id=scope_id, daily_records=daily_records, expenses=expenses)
        metrics_context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
        recent_activity = self._build_recent_activity(daily_records=daily_records, expenses=expenses, cash_deposits=cash_deposits)
        return RestaurantHomeResponse(
            greeting_name=current_user["full_name"].split()[0],
            restaurant_name=current_user.get("restaurant_name"),
            preferred_language=str(current_user.get("preferred_language", "en")),
            metrics=[
                MetricCardResponse(label="Revenue", value=metrics_context["revenue_total"], change_percent=metrics_context["revenue_change_percent"]),
                MetricCardResponse(label="Expenses", value=metrics_context["expenses_total"], change_percent=metrics_context["expense_change_percent"]),
                MetricCardResponse(label="Food Cost", value=metrics_context["food_cost_total"], change_percent=metrics_context["food_cost_change_percent"]),
                MetricCardResponse(label="Profit", value=metrics_context["profit_total"], change_percent=metrics_context["profit_change_percent"]),
            ],
            cash_management=[
                CashManagementItemResponse(label="Total Cash Collected", amount=metrics_context["cash_collected_total"], subtitle="From recorded daily entries"),
                CashManagementItemResponse(label="Cash Available", amount=metrics_context["cash_available"], subtitle="Estimated from register movements"),
                CashManagementItemResponse(label="Cash Deposited", amount=sum(float(item.get("amount", 0)) for item in cash_deposits), subtitle="Bank deposits logged"),
            ],
            quick_actions=[
                QuickActionResponse(key="upload_invoice", label="Upload Invoice"),
                QuickActionResponse(key="daily_data", label="Add Daily Data"),
                QuickActionResponse(key="expenses", label="Expenses"),
                QuickActionResponse(key="cash", label="Cash"),
            ],
            vat_balance=self._calculate_vat_balance(metrics_context["revenue_total"], metrics_context["expenses_total"]),
            weekly_revenue=self._build_weekly_revenue_chart(daily_records),
            featured_insight=insights[0] if insights else None,
            recent_activity=recent_activity,
        )

    async def get_vat_overview(self, current_user: dict) -> VatOverviewResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=120)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=120)
        revenue_total = sum(float(item.get("total_revenue", 0)) for item in daily_records)
        expenses_total = sum(float(item.get("amount", 0)) for item in expenses)
        vat_payable = round(revenue_total * self.VAT_RATE, 2)
        vat_receivable = round(expenses_total * self.VAT_RATE, 2)
        today = datetime.now(UTC).date()
        filing_deadline = today.replace(day=min(20, max(today.day, 1)))
        return VatOverviewResponse(
            estimated_vat_balance=round(vat_payable - vat_receivable, 2),
            vat_payable=vat_payable,
            vat_receivable=vat_receivable,
            filing_deadline=filing_deadline.isoformat(),
            report_ready=bool(daily_records or expenses),
        )

    async def list_insights(self, current_user: dict) -> InsightDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        insights = await self._get_or_generate_insights(scope_id=scope_id, daily_records=daily_records, expenses=expenses)
        return await self.get_insight_detail(current_user, insights[0].id)

    async def get_insight_detail(self, current_user: dict, insight_id: str) -> InsightDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        insight = self.serialize(await self.insight_repository.get_by_scope_and_id(scope_id=scope_id, insight_id=insight_id))
        related_items = self._build_other_related_insights(insight)
        return InsightDetailResponse(
            id=insight["id"],
            subtitle="Smart recommendations based on your restaurant data.",
            badge_label=insight["priority"].replace("_", " ").upper() + " PRIORITY",
            title=insight["title"],
            priority=insight["priority"],
            metric_value=insight["metric_value"],
            metric_caption=insight["metric_caption"],
            trend=[ChartPointResponse(**item) for item in insight.get("trend", [])],
            root_causes=insight.get("root_causes", []),
            recommended_actions=[InsightActionResponse(**item) for item in insight.get("recommended_actions", [])],
            other_related_insights=related_items,
        )

    async def upload_and_extract_document(
        self,
        current_user: dict,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
    ) -> DocumentExtractionResponse:
        if not file_bytes:
            raise ValidationException("Uploaded file is empty")
        extraction = await self.openai_service.extract_invoice(file_name=file_name, content_type=content_type, file_bytes=file_bytes)
        line_items = extraction.get("line_items") or []
        total_amount = extraction.get("total_amount")
        if total_amount is None:
            total_amount = round(sum(float(item.get("total_price", 0)) for item in line_items), 2)
        return DocumentExtractionResponse(
            supplier_name=extraction.get("supplier_name") or "Unknown Supplier",
            invoice_number=extraction.get("invoice_number"),
            invoice_date=None,
            total_amount=float(total_amount),
            ai_provider="openai" if self.openai_service.enabled else "fallback",
            ai_summary=extraction.get("ai_summary") or "AI extraction completed.",
            source_file_name=file_name,
            line_items=[DocumentLineItemSchema(**item) for item in line_items],
        )

    async def create_document_from_confirmation(self, current_user: dict, payload: DocumentSaveRequest) -> DocumentDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        now = datetime.now(UTC)
        resolved_invoice_date = payload.invoice_date or now.date()
        document = await self.document_repository.create(
            {
                "tenant_id": scope_id,
                "supplier_name": payload.supplier_name,
                "invoice_number": payload.invoice_number,
                "invoice_date": resolved_invoice_date.isoformat(),
                "upload_date": now,
                "total_amount": payload.total_amount,
                "currency": "EUR",
                "status": "processed",
                "ai_provider": payload.ai_provider,
                "ai_summary": payload.ai_summary,
                "source_file_name": payload.source_file_name,
                "line_items": [item.model_dump(mode="json") for item in payload.line_items],
                "created_by_user_id": str(current_user["_id"]),
                "last_edited_by_user_id": str(current_user["_id"]),
                "last_edited_at": now,
                "confirmed_by_user_id": str(current_user["_id"]),
                "confirmed_at": now,
            }
        )
        expense = await self._sync_document_expense(
            current_user=current_user,
            scope_id=scope_id,
            document_id=str(document["_id"]),
            supplier_name=payload.supplier_name,
            invoice_number=payload.invoice_number,
            invoice_date=resolved_invoice_date,
            total_amount=payload.total_amount,
            source_file_name=payload.source_file_name,
        )
        document = await self.document_repository.update(document["_id"], {"expense_entry_id": str(expense["_id"])})
        return self._to_document_detail(document)

    async def confirm_document(self, current_user: dict, document_id: str, payload: DocumentConfirmRequest) -> DocumentDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        updates = self._build_document_updates(current_user=current_user, payload=payload, mark_processed=True)
        updated = await self.document_repository.update(document["_id"], updates)
        effective_invoice_date = payload.invoice_date
        if effective_invoice_date is None and updated.get("invoice_date"):
            effective_invoice_date = datetime.fromisoformat(str(updated["invoice_date"])).date()
        if effective_invoice_date is None:
            effective_invoice_date = datetime.now(UTC).date()
            updated = await self.document_repository.update(updated["_id"], {"invoice_date": effective_invoice_date.isoformat()})
        expense = await self._sync_document_expense(
            current_user=current_user,
            scope_id=scope_id,
            document_id=str(updated["_id"]),
            supplier_name=str(updated.get("supplier_name") or document.get("supplier_name") or "Uploaded Invoice"),
            invoice_number=updated.get("invoice_number"),
            invoice_date=effective_invoice_date,
            total_amount=float(updated.get("total_amount", 0)),
            source_file_name=str(updated.get("source_file_name") or document.get("source_file_name") or "invoice"),
            existing_expense_id=updated.get("expense_entry_id"),
        )
        updated = await self.document_repository.update(updated["_id"], {"expense_entry_id": str(expense["_id"])})
        return self._to_document_detail(updated)

    async def list_documents(self, current_user: dict, *, page: int, page_size: int, status: str | None, search: str | None) -> DocumentListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.document_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size, status=status, search=search)
        return DocumentListResponse(items=[self._to_document_list_item(item) for item in items], **build_pagination_meta(total=total, page=page, page_size=page_size))

    async def get_document_detail(self, current_user: dict, document_id: str) -> DocumentDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        return self._to_document_detail(document)

    async def update_document(self, current_user: dict, document_id: str, payload: DocumentConfirmRequest) -> DocumentDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        updates = self._build_document_updates(current_user=current_user, payload=payload, mark_processed=False)
        updated = await self.document_repository.update(document["_id"], updates)
        if updated.get("status") == "processed" or updated.get("expense_entry_id"):
            effective_invoice_date = payload.invoice_date
            if effective_invoice_date is None and updated.get("invoice_date"):
                effective_invoice_date = datetime.fromisoformat(str(updated["invoice_date"])).date()
            if effective_invoice_date is None:
                effective_invoice_date = datetime.now(UTC).date()
                updated = await self.document_repository.update(updated["_id"], {"invoice_date": effective_invoice_date.isoformat()})
            expense = await self._sync_document_expense(
                current_user=current_user,
                scope_id=scope_id,
                document_id=str(updated["_id"]),
                supplier_name=str(updated.get("supplier_name") or document.get("supplier_name") or "Uploaded Invoice"),
                invoice_number=updated.get("invoice_number"),
                invoice_date=effective_invoice_date,
                total_amount=float(updated.get("total_amount", 0)),
                source_file_name=str(updated.get("source_file_name") or document.get("source_file_name") or "invoice"),
                existing_expense_id=updated.get("expense_entry_id"),
            )
            updated = await self.document_repository.update(updated["_id"], {"expense_entry_id": str(expense["_id"])})
        return self._to_document_detail(updated)

    async def delete_document(self, current_user: dict, document_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        await self.document_repository.delete(document["_id"])

    async def create_expense(self, current_user: dict, payload: ExpenseCreateRequest) -> ExpenseResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.expense_repository.create(
            {
                "tenant_id": scope_id,
                "category": payload.category,
                "amount": payload.amount,
                "expense_date": datetime.combine(payload.expense_date, datetime.min.time(), tzinfo=UTC),
                "notes": payload.notes,
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        return self._to_expense_response(document)

    async def list_expenses(self, current_user: dict, *, page: int, page_size: int) -> ExpenseListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.expense_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size)
        today = datetime.now(UTC).date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        serialized_items = self.serialize_list(items)
        summary = ExpenseSummaryResponse(
            today_total=round(sum(item["amount"] for item in serialized_items if item["expense_date"][:10] == today.isoformat()), 2),
            week_total=round(sum(item["amount"] for item in serialized_items if item["expense_date"][:10] >= week_start.isoformat()), 2),
            month_total=round(sum(item["amount"] for item in serialized_items if item["expense_date"][:10] >= month_start.isoformat()), 2),
            top_category=self._top_category(serialized_items),
        )
        return ExpenseListResponse(summary=summary, items=[self._to_expense_response(item) for item in items], **build_pagination_meta(total=total, page=page, page_size=page_size))

    async def create_cash_deposit(self, current_user: dict, payload: CashDepositCreateRequest) -> CashDepositResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.cash_repository.create(
            {
                "tenant_id": scope_id,
                "deposit_date": datetime.combine(payload.deposit_date, datetime.min.time(), tzinfo=UTC),
                "amount": payload.amount,
                "deposit_type": payload.deposit_type,
                "notes": payload.notes,
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        return self._to_cash_deposit_response(document)

    async def get_cash_management(self, current_user: dict) -> CashManagementSummaryResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=30)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=90)
        total_collected = round(sum(float(item.get("cash_collected_total", item.get("cash_payments", 0) + item.get("cash_in", 0))) for item in daily_records), 2)
        cash_available = round(sum(float(item.get("cash_available", item.get("closing_cash", 0) + item.get("cash_in", 0) - item.get("cash_out", 0))) for item in daily_records), 2)
        withdrawals_total = round(sum(float(item.get("cash_withdrawals", 0) + item.get("cash_out", 0)) for item in daily_records), 2)
        bank_deposits_total = round(sum(float(item.get("amount", 0)) for item in deposits), 2)
        return CashManagementSummaryResponse(
            total_collected=total_collected,
            cash_available=cash_available,
            withdrawals_total=withdrawals_total,
            bank_deposits_total=bank_deposits_total,
            recent_deposits=[self._to_cash_deposit_response(item) for item in deposits[:10]],
        )

    async def create_daily_data(self, current_user: dict, payload: DailyDataCreateRequest) -> DailyDataResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        if payload.method == "method_1":
            if payload.method_one is None:
                raise ValidationException("method_one is required when method is method_1")
            data = payload.method_one.model_dump(mode="json")
            business_date = payload.method_one.business_date
            total_revenue = round(data["pos_payments"] + data["cash_in"], 2)
            total_expenses = round(data["expenses_in_cash"] + data["cash_withdrawals"] + data["cash_out"], 2)
            lunch_covers = 0
            dinner_covers = 0
            record_payload = {
                **data,
                "cash_collected_total": data["cash_in"],
                "cash_available": max(data["cash_in"] - data["cash_out"] - data["cash_withdrawals"] - data["expenses_in_cash"], 0),
                "closing_cash": max(data["cash_in"] - data["cash_out"], 0),
                "opening_cash": 0,
            }
        else:
            if payload.method_two is None:
                raise ValidationException("method_two is required when method is method_2")
            data = payload.method_two.model_dump(mode="json")
            business_date = payload.method_two.business_date
            total_revenue = round(data["pos_payments"] + data["cash_payments"] + data["bank_transfer_payments"], 2)
            total_expenses = 0.0
            lunch_covers = data["lunch_covers"]
            dinner_covers = data["dinner_covers"]
            record_payload = {
                **data,
                "cash_collected_total": data["cash_payments"],
                "cash_available": data["closing_cash"],
                "cash_withdrawals": 0.0,
                "cash_in": data["cash_payments"],
                "cash_out": max(data["opening_cash"] - data["closing_cash"], 0),
                "expenses_in_cash": 0.0,
            }
        existing = await self.daily_record_repository.find_by_business_date(scope_id=scope_id, business_date=business_date)
        final_payload = {
            "tenant_id": scope_id,
            "business_date": business_date,
            "method": payload.method,
            **record_payload,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "profit": round(total_revenue - total_expenses, 2),
            "lunch_covers": lunch_covers,
            "dinner_covers": dinner_covers,
            "avg_revenue_per_cover": round(total_revenue / max(lunch_covers + dinner_covers, 1), 2),
            "created_by_user_id": str(current_user["_id"]),
        }
        if existing:
            document = await self.daily_record_repository.update(existing["_id"], final_payload)
        else:
            document = await self.daily_record_repository.create(final_payload)
        return self._to_daily_data_response(document)

    async def list_daily_data(self, current_user: dict, *, page: int, page_size: int, view: str, reference_date: date | None) -> DailyDataListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        anchor_date = reference_date or datetime.now(UTC).date()
        start_date: date | None = None
        end_date: date | None = None
        if view == "week":
            start_date = anchor_date - timedelta(days=anchor_date.weekday())
            end_date = start_date + timedelta(days=6)
        elif view == "month":
            start_date = anchor_date.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_date = next_month - timedelta(days=1)

        all_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_records = self.serialize_list(all_records)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_expenses = self.serialize_list(all_expenses)

        filtered_records = self._filter_daily_records_by_date_range(serialized_records, start_date=start_date, end_date=end_date)
        filtered_expenses = self._filter_expenses_by_date_range(serialized_expenses, start_date=start_date, end_date=end_date) if (start_date or end_date) else serialized_expenses

        buckets = self._build_daily_data_buckets(filtered_records, filtered_expenses, anchor_date=anchor_date)
        total = len(buckets)
        page_start = (page - 1) * page_size
        page_end = page_start + page_size
        page_items = buckets[page_start:page_end]

        if view == "date":
            latest_bucket = page_items[0] if page_items else None
            latest_revenue = float(latest_bucket.get("total_revenue", 0)) if latest_bucket else 0.0
            latest_expenses = float(latest_bucket.get("total_expenses", 0)) if latest_bucket else 0.0
            latest_covers = float(latest_bucket.get("total_covers", 0)) if latest_bucket else 0.0
        else:
            latest_bucket = None
            latest_revenue = round(sum(float(item.get("total_revenue", 0)) for item in buckets), 2)
            latest_expenses = round(sum(float(item.get("total_expenses", 0)) for item in buckets), 2)
            latest_covers = float(sum(int(item.get("total_covers", 0)) for item in buckets))
        latest_profit = round(latest_revenue - latest_expenses, 2)
        latest_avg = round(latest_revenue / max(latest_covers, 1), 2) if latest_revenue else 0.0

        revenue_label = "Today's Revenue" if view == "date" else ("This Week Revenue" if view == "week" else "This Month Revenue")
        expense_label = "Total Expenses" if view == "date" else ("This Week Expenses" if view == "week" else "This Month Expenses")
        profit_label = "Profit" if view == "date" else ("This Week Profit" if view == "week" else "This Month Profit")
        summary_cards = [
            DailyDataSummaryCardResponse(label=revenue_label, value=latest_revenue, value_prefix="EUR", value_formatted=self._format_currency(latest_revenue), icon_key="revenue"),
            DailyDataSummaryCardResponse(label=expense_label, value=latest_expenses, value_prefix="EUR", value_formatted=self._format_currency(latest_expenses), icon_key="expenses"),
            DailyDataSummaryCardResponse(label=profit_label, value=latest_profit, value_prefix="EUR", value_formatted=self._format_currency(latest_profit), icon_key="profit"),
            DailyDataSummaryCardResponse(label="Total Covers", value=latest_covers, value_formatted=str(int(latest_covers)), icon_key=None),
            DailyDataSummaryCardResponse(label="Avg. Rev/Cover", value=latest_avg, value_prefix="USD", value_formatted=self._format_currency(latest_avg), icon_key=None),
        ]
        return DailyDataListResponse(
            active_view=view,
            summary_cards=summary_cards,
            add_button=DailyDataAddButtonResponse(endpoint="/api/v1/restaurant/daily-data"),
            items=[self._to_daily_data_bucket_item(item, anchor_date=anchor_date) for item in page_items],
            **build_pagination_meta(total=total, page=page, page_size=page_size),
        )

    async def get_daily_data_detail(self, current_user: dict, record_id: str) -> DailyDataResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        record = await self.daily_record_repository.get_scoped_by_id(record_id, scope_id)
        return self._to_daily_data_response(record)

    async def delete_daily_data(self, current_user: dict, record_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        record = await self.daily_record_repository.get_scoped_by_id(record_id, scope_id)
        await self.daily_record_repository.delete(record["_id"])

    async def create_inventory_item(self, current_user: dict, payload: Any) -> InventoryItemResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.inventory_repository.create(
            {
                "tenant_id": scope_id,
                "product_name": payload.product_name,
                "category": payload.category,
                "stock_quantity": payload.stock_quantity,
                "unit_type": payload.unit_type,
                "supplier_name": payload.supplier_name,
                "unit_price": payload.unit_price,
                "alert_threshold": payload.alert_threshold,
                "purchase_date": payload.purchase_date.isoformat() if payload.purchase_date else None,
                "stock_status": self._resolve_stock_status(payload.stock_quantity, payload.alert_threshold),
                "history": [{"kind": "stock_added", "quantity_delta": payload.stock_quantity, "occurred_at": datetime.now(UTC)}],
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        return self._to_inventory_item_response(document)

    async def list_inventory(self, current_user: dict, *, page: int, page_size: int, search: str | None, status: str | None, category: str | None) -> InventoryListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.inventory_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size, search=search, status=status, category=category)
        serialized_items = self.serialize_list(items)
        total_inventory_value = round(sum(item["stock_quantity"] * item["unit_price"] for item in serialized_items), 2)
        return InventoryListResponse(total_inventory_value=total_inventory_value, items=[self._to_inventory_item_response(item) for item in items], **build_pagination_meta(total=total, page=page, page_size=page_size))

    async def get_inventory_item(self, current_user: dict, item_id: str) -> InventoryDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        return self._to_inventory_detail_response(item)

    async def update_inventory_stock(self, current_user: dict, item_id: str, payload: InventoryStockUpdateRequest) -> InventoryDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        if payload.remove_stock > item.get("stock_quantity", 0):
            raise ValidationException("Cannot remove more stock than available")
        new_quantity = round(item.get("stock_quantity", 0) + payload.add_stock - payload.remove_stock, 2)
        history = list(item.get("history", []))
        now = datetime.now(UTC)
        if payload.add_stock:
            history.append({"kind": "stock_added", "quantity_delta": payload.add_stock, "occurred_at": now})
        if payload.remove_stock:
            history.append({"kind": "stock_removed", "quantity_delta": -payload.remove_stock, "occurred_at": now})
        updated = await self.inventory_repository.update(
            item["_id"],
            {
                "stock_quantity": new_quantity,
                "stock_status": self._resolve_stock_status(new_quantity, float(item.get("alert_threshold", 0))),
                "history": history,
            },
        )
        return self._to_inventory_detail_response(updated)

    async def get_analytics(self, current_user: dict) -> AnalyticsOverviewResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
        return AnalyticsOverviewResponse(
            estimated_profit=context["profit_total"],
            peak_hour_label="7:00 PM",
            revenue_total=context["revenue_total"],
            revenue_change_percent=context["revenue_change_percent"],
            covers_total=context["covers_total"],
            avg_revenue_per_cover=context["avg_revenue_per_cover"],
            weekly_revenue=self._build_weekly_revenue_chart(daily_records),
        )

    async def list_chat_messages(self, current_user: dict) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=40)
        return ChatConversationResponse(messages=[self._to_chat_message_response(item) for item in items])

    async def create_chat_message(self, current_user: dict, payload: ChatMessageCreateRequest) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        await self.chat_repository.create({"tenant_id": scope_id, "role": "user", "message": payload.message, "created_by_user_id": str(current_user["_id"])})
        recent = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=12)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=30)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=30)
        metrics_context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
        assistant_text = await self.openai_service.generate_chat_reply(prompt=payload.message, metrics_context=metrics_context, recent_messages=[self.serialize(item) for item in recent])
        await self.chat_repository.create({"tenant_id": scope_id, "role": "assistant", "message": assistant_text, "created_by_user_id": str(current_user["_id"])})
        items = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=40)
        return ChatConversationResponse(messages=[self._to_chat_message_response(item) for item in items])

    async def get_profile(self, current_user: dict) -> RestaurantProfileResponse:
        serialized = self.serialize(current_user)
        return RestaurantProfileResponse(
            full_name=serialized["full_name"],
            email=serialized["email"],
            phone=serialized.get("phone"),
            restaurant_name=serialized.get("restaurant_name"),
            location=serialized.get("location"),
            preferred_language=serialized.get("preferred_language", "en"),
        )

    async def update_profile(self, current_user: dict, payload: RestaurantProfileUpdateRequest) -> RestaurantProfileResponse:
        updates = payload.model_dump(exclude_none=True)
        user = current_user if not updates else await self.user_repository.update(current_user["_id"], updates)
        return await self.get_profile(user)

    async def _get_or_generate_insights(self, *, scope_id: str, daily_records: list[dict], expenses: list[dict]) -> list[InsightSummaryResponse]:
        insights = await self.insight_repository.list_by_scope(scope_id=scope_id, limit=10)
        if not insights:
            context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
            percent = abs(context["food_cost_change_percent"])
            trend = self._build_weekly_revenue_chart(daily_records)
            created = await self.insight_repository.create(
                {
                    "tenant_id": scope_id,
                    "title": "Food Cost Increased" if context["food_cost_change_percent"] >= 0 else "Food Cost Improved",
                    "summary": f"Food cost changed by {percent:.1f}% compared with the previous week. Review supplier pricing and prep waste.",
                    "priority": "high" if percent >= 10 else "medium",
                    "metric_value": f"{percent:.0f}%",
                    "metric_caption": "change this week",
                    "trend": [item.model_dump(mode="json") for item in trend],
                    "root_causes": [
                        "Supplier price increase on core items",
                        "Higher ingredient usage in main courses",
                        "Prep station waste increased",
                    ],
                    "recommended_actions": [
                        {"title": "Review supplier prices", "description": "Compare top suppliers and renegotiate this week."},
                        {"title": "Optimize portion sizes", "description": "Audit garnish and prep weights on the slowest dishes."},
                        {"title": "Monitor ingredient waste", "description": "Run a daily waste checklist for the next 7 days."},
                    ],
                    "related_metrics": [
                        {"label": "Profit", "value": context["profit_total"], "change_percent": context["profit_change_percent"], "currency": "EUR"},
                        {"label": "Expenses", "value": context["expenses_total"], "change_percent": context["expense_change_percent"], "currency": "EUR"},
                    ],
                }
            )
            insights = [created]
        serialized = self.serialize_list(insights)
        return [InsightSummaryResponse(id=item["id"], title=item["title"], summary=item["summary"], priority=item["priority"], metric_value=item["metric_value"], metric_caption=item["metric_caption"]) for item in serialized]

    def _build_metrics_context(self, *, daily_records: list[dict], expenses: list[dict]) -> dict[str, float | int]:
        today = datetime.now(UTC).date()
        last_7_start = today - timedelta(days=6)
        prev_7_start = today - timedelta(days=13)
        prev_7_end = today - timedelta(days=7)
        serialized_records = self.serialize_list(daily_records)
        serialized_expenses = self.serialize_list(expenses)
        revenue_total = round(sum(item["total_revenue"] for item in serialized_records), 2)
        expenses_total = round(sum(item["amount"] for item in serialized_expenses), 2)
        food_cost_total = round(sum(item["amount"] for item in serialized_expenses if "food" in item["category"].lower() or "inventory" in item["category"].lower()), 2)
        profit_total = round(revenue_total - expenses_total, 2)
        covers_total = sum(int(item.get("lunch_covers", 0) + item.get("dinner_covers", 0)) for item in serialized_records)
        recent_revenue = sum(item["total_revenue"] for item in serialized_records if item["business_date"] >= last_7_start.isoformat())
        previous_revenue = sum(item["total_revenue"] for item in serialized_records if prev_7_start.isoformat() <= item["business_date"] <= prev_7_end.isoformat())
        recent_food_cost = sum(item["amount"] for item in serialized_expenses if item["expense_date"][:10] >= last_7_start.isoformat() and ("food" in item["category"].lower() or "inventory" in item["category"].lower()))
        previous_food_cost = sum(item["amount"] for item in serialized_expenses if prev_7_start.isoformat() <= item["expense_date"][:10] <= prev_7_end.isoformat() and ("food" in item["category"].lower() or "inventory" in item["category"].lower()))
        recent_expenses = sum(item["amount"] for item in serialized_expenses if item["expense_date"][:10] >= last_7_start.isoformat())
        previous_expenses = sum(item["amount"] for item in serialized_expenses if prev_7_start.isoformat() <= item["expense_date"][:10] <= prev_7_end.isoformat())
        recent_profit = recent_revenue - recent_expenses
        previous_profit = previous_revenue - previous_expenses
        cash_collected_total = round(sum(float(item.get("cash_collected_total", 0)) for item in daily_records), 2)
        cash_available = round(sum(float(item.get("cash_available", 0)) for item in daily_records), 2)
        return {
            "revenue_total": revenue_total,
            "expenses_total": expenses_total,
            "food_cost_total": food_cost_total,
            "profit_total": profit_total,
            "revenue_change_percent": self._percent_change(previous_revenue, recent_revenue),
            "expense_change_percent": self._percent_change(previous_expenses, recent_expenses),
            "food_cost_change_percent": self._percent_change(previous_food_cost, recent_food_cost),
            "profit_change_percent": self._percent_change(previous_profit, recent_profit),
            "covers_total": covers_total,
            "avg_revenue_per_cover": round(revenue_total / max(covers_total, 1), 2),
            "cash_collected_total": cash_collected_total,
            "cash_available": cash_available,
        }

    @staticmethod
    def _format_currency(value: float) -> str:
        return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"

    @staticmethod
    def _percent_change(previous: float, current: float) -> float:
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round(((current - previous) / abs(previous)) * 100, 1)

    def _calculate_vat_balance(self, revenue_total: float, expenses_total: float) -> float:
        return round((revenue_total - expenses_total) * self.VAT_RATE, 2)

    def _build_weekly_revenue_chart(self, daily_records: list[dict]) -> list[ChartPointResponse]:
        today = datetime.now(UTC).date()
        by_day: dict[str, float] = {}
        for item in self.serialize_list(daily_records):
            by_day[item["business_date"]] = by_day.get(item["business_date"], 0.0) + float(item["total_revenue"])
        points: list[ChartPointResponse] = []
        for offset in range(6, -1, -1):
            target = today - timedelta(days=offset)
            points.append(ChartPointResponse(label=target.strftime("%a").upper(), value=round(by_day.get(target.isoformat(), 0.0), 2)))
        return points

    def _build_recent_activity(self, *, daily_records: list[dict], expenses: list[dict], cash_deposits: list[dict]) -> list[ActivityItemResponse]:
        items: list[ActivityItemResponse] = []
        for item in self.serialize_list(daily_records[:3]):
            items.append(ActivityItemResponse(kind="daily_record", title="Daily data saved", subtitle=item["business_date"], timestamp=item["created_at"]))
        for item in self.serialize_list(expenses[:3]):
            items.append(ActivityItemResponse(kind="expense", title="Expense added", subtitle=item["category"], timestamp=item["created_at"]))
        for item in self.serialize_list(cash_deposits[:3]):
            items.append(ActivityItemResponse(kind="cash", title="Bank deposit logged", subtitle=item["deposit_type"], timestamp=item["created_at"]))
        return sorted(items, key=lambda value: value.timestamp, reverse=True)[:6]

    @staticmethod
    def _top_category(items: list[dict[str, Any]]) -> str | None:
        totals: dict[str, float] = {}
        for item in items:
            totals[item["category"]] = totals.get(item["category"], 0.0) + float(item["amount"])
        if not totals:
            return None
        return max(totals.items(), key=lambda pair: pair[1])[0]

    @staticmethod
    def _resolve_stock_status(stock_quantity: float, alert_threshold: float) -> str:
        if stock_quantity <= 0:
            return "out_of_stock"
        if stock_quantity <= alert_threshold:
            return "low_stock"
        return "in_stock"

    def _build_document_updates(self, *, current_user: dict, payload: DocumentConfirmRequest, mark_processed: bool) -> dict[str, Any]:
        updates = payload.model_dump(exclude_none=True)
        if "invoice_date" in updates and updates["invoice_date"] is not None:
            updates["invoice_date"] = updates["invoice_date"].isoformat()
        if "line_items" in updates and updates["line_items"] is not None:
            updates["line_items"] = [item.model_dump(mode="json") for item in payload.line_items or []]
        now = datetime.now(UTC)
        updates["last_edited_by_user_id"] = str(current_user["_id"])
        updates["last_edited_at"] = now
        if mark_processed:
            updates["status"] = "processed"
            updates["confirmed_by_user_id"] = str(current_user["_id"])
            updates["confirmed_at"] = now
        return updates

    @staticmethod
    def _filter_daily_records_by_date_range(records: list[dict[str, Any]], *, start_date: date | None, end_date: date | None) -> list[dict[str, Any]]:
        if not start_date and not end_date:
            return records
        filtered: list[dict[str, Any]] = []
        for item in records:
            item_date = datetime.fromisoformat(item["business_date"]).date()
            if start_date and item_date < start_date:
                continue
            if end_date and item_date > end_date:
                continue
            filtered.append(item)
        return filtered

    def _build_daily_data_buckets(self, records: list[dict[str, Any]], expenses: list[dict[str, Any]], *, anchor_date: date) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for record in records:
            bucket = buckets.setdefault(
                record["business_date"],
                {
                    "id": f"date:{record['business_date']}",
                    "business_date": record["business_date"],
                    "total_revenue": 0.0,
                    "total_expenses": 0.0,
                    "total_covers": 0,
                    "avg_revenue_per_cover": 0.0,
                    "record_id": None,
                    "created_at": record["created_at"],
                    "data_sources": [],
                },
            )
            covers = int(record.get("lunch_covers", 0) + record.get("dinner_covers", 0))
            bucket["id"] = record["id"]
            bucket["record_id"] = record["id"]
            bucket["total_revenue"] = float(record.get("total_revenue", 0))
            bucket["total_covers"] = covers
            bucket["avg_revenue_per_cover"] = float(record.get("avg_revenue_per_cover", 0))
            bucket["created_at"] = record["created_at"]
            bucket["data_sources"].append(
                DailyDataEntrySourceResponse(kind="daily_record", label="Daily data", count=1, endpoint=f"/api/v1/restaurant/daily-data/{record['id']}")
            )

        expense_groups: dict[str, dict[str, Any]] = {}
        for expense in expenses:
            expense_date = datetime.fromisoformat(expense["expense_date"].replace("Z", "+00:00")).date().isoformat()
            group = expense_groups.setdefault(expense_date, {"uploaded_invoice": {"count": 0, "total": 0.0, "endpoint": None}, "manual_expense": {"count": 0, "total": 0.0, "endpoint": "/api/v1/restaurant/expenses"}})
            if expense.get("source_document_id"):
                group["uploaded_invoice"]["count"] += 1
                group["uploaded_invoice"]["total"] += float(expense.get("amount", 0))
                group["uploaded_invoice"]["endpoint"] = f"/api/v1/restaurant/documents/{expense['source_document_id']}"
            else:
                group["manual_expense"]["count"] += 1
                group["manual_expense"]["total"] += float(expense.get("amount", 0))

            bucket = buckets.setdefault(
                expense_date,
                {
                    "id": f"date:{expense_date}",
                    "business_date": expense_date,
                    "total_revenue": 0.0,
                    "total_expenses": 0.0,
                    "total_covers": 0,
                    "avg_revenue_per_cover": 0.0,
                    "record_id": None,
                    "created_at": expense.get("created_at", datetime.now(UTC).isoformat()),
                    "data_sources": [],
                },
            )
            bucket["total_expenses"] = round(bucket.get("total_expenses", 0.0) + float(expense.get("amount", 0)), 2)

        for expense_date, grouped in expense_groups.items():
            bucket = buckets[expense_date]
            if grouped["uploaded_invoice"]["count"]:
                bucket["data_sources"].append(
                    DailyDataEntrySourceResponse(
                        kind="uploaded_invoice",
                        label="Uploaded invoices",
                        count=grouped["uploaded_invoice"]["count"],
                        total_amount=round(grouped["uploaded_invoice"]["total"], 2),
                        endpoint=grouped["uploaded_invoice"]["endpoint"],
                    )
                )
            if grouped["manual_expense"]["count"]:
                bucket["data_sources"].append(
                    DailyDataEntrySourceResponse(
                        kind="manual_expense",
                        label="Manual expenses",
                        count=grouped["manual_expense"]["count"],
                        total_amount=round(grouped["manual_expense"]["total"], 2),
                        endpoint=grouped["manual_expense"]["endpoint"],
                    )
                )
            if bucket["total_revenue"]:
                bucket["avg_revenue_per_cover"] = round(bucket["total_revenue"] / max(bucket["total_covers"], 1), 2)

        return sorted(buckets.values(), key=lambda item: item["business_date"], reverse=True)

    async def _sync_document_expense(
        self,
        *,
        current_user: dict,
        scope_id: str,
        document_id: str,
        supplier_name: str,
        invoice_number: str | None,
        invoice_date: date | None,
        total_amount: float,
        source_file_name: str,
        existing_expense_id: str | None = None,
    ) -> dict:
        expense_payload = {
            "tenant_id": scope_id,
            "category": "Uploaded Invoice",
            "amount": float(total_amount),
            "expense_date": datetime.combine(invoice_date or datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC),
            "notes": f"Invoice {invoice_number or source_file_name} from {supplier_name}",
            "created_by_user_id": str(current_user["_id"]),
            "source_document_id": document_id,
        }
        if existing_expense_id:
            return await self.expense_repository.update(existing_expense_id, expense_payload)
        return await self.expense_repository.create(expense_payload)

    @staticmethod
    def _filter_expenses_by_date_range(expenses: list[dict[str, Any]], *, start_date: date, end_date: date) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for item in expenses:
            expense_date = datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date()
            if start_date <= expense_date <= end_date:
                filtered.append(item)
        return filtered

    def _build_other_related_insights(self, insight: dict) -> list[dict[str, str | None]]:
        related_items: list[dict[str, str | None]] = []
        for metric in insight.get("related_metrics", []):
            label = str(metric.get("label", "Metric"))
            value = float(metric.get("value", 0))
            change_percent = float(metric.get("change_percent", 0))
            currency = str(metric.get("currency", "EUR"))
            currency_symbol = "EUR " if currency == "EUR" else f"{currency} "
            if label.lower() == "expenses":
                related_items.append({"label": f"{label} increase", "value": f"+{currency_symbol}{value:,.0f}", "subtitle": None})
            else:
                direction = "increase" if change_percent >= 0 else "decrease"
                related_items.append({"label": f"{label} {direction}", "value": f"{change_percent:+.1f}%", "subtitle": None})
        return related_items[:2]

    def _to_document_list_item(self, document: dict) -> DocumentListItemResponse:
        serialized = self.serialize(document)
        return DocumentListItemResponse(
            id=serialized["id"],
            supplier_name=serialized["supplier_name"],
            invoice_number=serialized.get("invoice_number"),
            invoice_date=serialized.get("invoice_date"),
            upload_date=serialized["upload_date"],
            total_amount=serialized["total_amount"],
            status=serialized["status"],
            line_item_count=len(serialized.get("line_items", [])),
            source_file_name=serialized["source_file_name"],
            created_by_user_id=serialized.get("created_by_user_id"),
            last_edited_by_user_id=serialized.get("last_edited_by_user_id"),
            confirmed_at=serialized.get("confirmed_at"),
        )

    def _to_document_detail(self, document: dict) -> DocumentDetailResponse:
        serialized = self.serialize(document)
        return DocumentDetailResponse(
            id=serialized["id"],
            supplier_name=serialized["supplier_name"],
            invoice_number=serialized.get("invoice_number"),
            invoice_date=serialized.get("invoice_date"),
            upload_date=serialized["upload_date"],
            total_amount=serialized["total_amount"],
            status=serialized["status"],
            ai_provider=serialized["ai_provider"],
            ai_summary=serialized.get("ai_summary", ""),
            source_file_name=serialized["source_file_name"],
            line_items=[DocumentLineItemSchema(**item) for item in serialized.get("line_items", [])],
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
            created_by_user_id=serialized.get("created_by_user_id"),
            last_edited_by_user_id=serialized.get("last_edited_by_user_id"),
            last_edited_at=serialized.get("last_edited_at"),
            confirmed_by_user_id=serialized.get("confirmed_by_user_id"),
            confirmed_at=serialized.get("confirmed_at"),
        )

    def _to_expense_response(self, expense: dict) -> ExpenseResponse:
        serialized = self.serialize(expense)
        return ExpenseResponse(id=serialized["id"], category=serialized["category"], amount=serialized["amount"], expense_date=serialized["expense_date"], notes=serialized.get("notes"), created_at=serialized["created_at"])

    def _to_cash_deposit_response(self, deposit: dict) -> CashDepositResponse:
        serialized = self.serialize(deposit)
        return CashDepositResponse(id=serialized["id"], deposit_date=serialized["deposit_date"], amount=serialized["amount"], deposit_type=serialized["deposit_type"], notes=serialized.get("notes"), created_at=serialized["created_at"])

    def _to_daily_data_response(self, record: dict) -> DailyDataResponse:
        serialized = self.serialize(record)
        total_covers = int(serialized.get("lunch_covers", 0) + serialized.get("dinner_covers", 0))
        return DailyDataResponse(
            id=serialized["id"],
            business_date=serialized["business_date"],
            method=serialized["method"],
            total_revenue=serialized["total_revenue"],
            total_expenses=serialized["total_expenses"],
            profit=serialized["profit"],
            lunch_covers=serialized.get("lunch_covers", 0),
            dinner_covers=serialized.get("dinner_covers", 0),
            total_covers=total_covers,
            avg_revenue_per_cover=serialized.get("avg_revenue_per_cover", 0.0),
            created_at=serialized["created_at"],
        )

    def _to_daily_data_bucket_item(self, bucket: dict[str, Any], *, anchor_date: date | None = None) -> DailyDataListItemResponse:
        business_date = datetime.fromisoformat(bucket["business_date"]).date()
        anchor = anchor_date or datetime.now(UTC).date()
        if business_date == anchor:
            day_label = "TODAY"
        elif business_date == anchor - timedelta(days=1):
            day_label = "YESTERDAY"
        else:
            day_label = business_date.strftime("%A").upper()
        revenue = float(bucket.get("total_revenue", 0.0))
        expenses = float(bucket.get("total_expenses", 0.0))
        avg_value = float(bucket.get("avg_revenue_per_cover", 0.0))
        record_id = bucket.get("record_id")
        return DailyDataListItemResponse(
            id=str(bucket["id"]),
            business_date=bucket["business_date"],
            business_date_formatted=business_date.strftime("%b %d, %Y"),
            day_label=day_label,
            total_revenue=revenue,
            total_revenue_formatted=self._format_currency(revenue),
            total_expenses=expenses,
            total_expenses_formatted=self._format_currency(expenses),
            total_covers=int(bucket.get("total_covers", 0)),
            avg_revenue_per_cover=avg_value,
            avg_revenue_per_cover_formatted=self._format_currency(avg_value),
            data_sources=bucket.get("data_sources", []),
            actions=DailyDataListItemActionResponse(
                view_endpoint=f"/api/v1/restaurant/daily-data/{record_id}" if record_id else None,
                delete_endpoint=f"/api/v1/restaurant/daily-data/{record_id}" if record_id else None,
            ),
            created_at=str(bucket.get("created_at")),
        )

    def _to_inventory_item_response(self, item: dict) -> InventoryItemResponse:
        serialized = self.serialize(item)
        return InventoryItemResponse(
            id=serialized["id"],
            product_name=serialized["product_name"],
            category=serialized["category"],
            stock_quantity=serialized["stock_quantity"],
            unit_type=serialized["unit_type"],
            supplier_name=serialized.get("supplier_name"),
            unit_price=serialized["unit_price"],
            alert_threshold=serialized["alert_threshold"],
            stock_status=serialized["stock_status"],
            purchase_date=serialized.get("purchase_date"),
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    def _to_inventory_detail_response(self, item: dict) -> InventoryDetailResponse:
        base_item = self._to_inventory_item_response(item)
        serialized = self.serialize(item)
        return InventoryDetailResponse(**base_item.model_dump(), history=[InventoryHistoryItemResponse(**entry) for entry in serialized.get("history", [])])

    def _to_chat_message_response(self, item: dict) -> ChatMessageResponse:
        serialized = self.serialize(item)
        return ChatMessageResponse(id=serialized["id"], role=serialized["role"], message=serialized["message"], created_at=serialized["created_at"])

