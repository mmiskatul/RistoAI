from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from html import escape
from typing import Any

from app.core.exceptions import ValidationException
from app.repositories.restaurant_ops import (
    RestaurantCashDepositRepository,
    RestaurantChatRepository,
    RestaurantDailyRecordRepository,
    RestaurantRecordRepository,
    RestaurantWeeklyRecordRepository,
    RestaurantMonthlyRecordRepository,
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
    AnalyticsInsightBannerResponse,
    AnalyticsMetricTileResponse,
    AnalyticsSummaryStatResponse,
    AnalyticsComparisonRowResponse,
    AnalyticsSupplierAlertResponse,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashManagementItemResponse,
    CashManagementSummaryResponse,
    ChartPointResponse,
    ChatAttachmentOptionResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatQuickPromptResponse,
    ChatRealtimeConfigResponse,
    DailyDataCollectionResponse,
    DailyDataCreateRequest,
    DailyDataAddButtonResponse,
    DailyDataDetailResponse,
    DailyDataDocumentItemResponse,
    DailyDataFormFieldResponse,
    DailyDataManualEntryResponse,
    DailyDataManualMethodResponse,
    DailyDataEntrySourceResponse,
    DailyDataListItemActionResponse,
    DailyDataListItemResponse,
    DailyDataListResponse,
    DailyDataResponse,
    DailyDataSummaryCardResponse,
    DocumentConfirmRequest,
    DocumentConfirmSaveResponse,
    DocumentDetailResponse,
    DocumentExtractionResponse,
    DocumentLineItemSchema,
    DocumentListItemResponse,
    DocumentListResponse,
    DocumentSaveRequest,
    DocumentUploadExtractRequest,
    ExpenseCreateRequest,
    ExpenseDistributionItemResponse,
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
    InventoryUpdateRequest,
    InventoryListItemActionResponse,
    InventorySupplierCardResponse,
    DailyDataRevenueBreakdownItemResponse,
    DailyDataCoversSummaryResponse,
    DailyDataRegisterSummaryResponse,
    MetricCardResponse,
    RestaurantHomePeriodResponse,
    RestaurantHomeResponse,
    RestaurantProfileResponse,
    RestaurantProfileUpdateRequest,
    SettingsActionItemResponse,
    SettingsLanguageOptionResponse,
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
        record_repository: RestaurantRecordRepository,
        weekly_record_repository: RestaurantWeeklyRecordRepository,
        monthly_record_repository: RestaurantMonthlyRecordRepository,
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
        self.record_repository = record_repository
        self.weekly_record_repository = weekly_record_repository
        self.monthly_record_repository = monthly_record_repository
        self.inventory_repository = inventory_repository
        self.chat_repository = chat_repository
        self.insight_repository = insight_repository
        self.openai_service = openai_service

    async def get_home(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> RestaurantHomeResponse:
        del period
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        cash_deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=120)

        weekly_snapshot = await self._build_home_period_snapshot(
            scope_id=scope_id,
            daily_records=daily_records,
            expenses=expenses,
            cash_deposits=cash_deposits,
            period='weekly',
            from_date=from_date,
            to_date=to_date,
        )
        monthly_snapshot = await self._build_home_period_snapshot(
            scope_id=scope_id,
            daily_records=daily_records,
            expenses=expenses,
            cash_deposits=cash_deposits,
            period='monthly',
            from_date=from_date,
            to_date=to_date,
        )

        recent_activity = self._build_recent_activity(
            daily_records=self.serialize_list(daily_records),
            expenses=self.serialize_list(expenses),
            cash_deposits=self.serialize_list(cash_deposits),
        )

        return RestaurantHomeResponse(
            greeting_name=current_user["full_name"].split()[0],
            restaurant_name=current_user.get("restaurant_name"),
            preferred_language=str(current_user.get("preferred_language", "en")),
            weekly=weekly_snapshot,
            monthly=monthly_snapshot,
            quick_actions=[
                QuickActionResponse(key="upload_invoice", label="Upload Invoice"),
                QuickActionResponse(key="daily_data", label="Add Daily Data"),
                QuickActionResponse(key="expenses", label="Expenses"),
                QuickActionResponse(key="cash", label="Cash"),
            ],
            recent_activity=recent_activity,
        )

    async def export_home_report(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        export_format: str = "pdf",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[str, str, bytes]:
        home = await self.get_home(current_user, period=period, from_date=from_date, to_date=to_date)
        section = home.monthly if period == 'monthly' else home.weekly
        period_label = period.capitalize()
        if export_format == 'excel':
            lines = [
                'Section,Label,Value,ChangePercent,Currency',
            ]
            for metric in section.metrics:
                lines.append(f'Metric,{metric.label},{metric.value},{metric.change_percent},{metric.currency}')
            for item in section.cash_management:
                lines.append(f'CashManagement,{item.label},{item.amount},,EUR')
            for point in section.revenue:
                lines.append(f'Trend,{point.label},{point.value},,EUR')
            content = ('\n'.join(lines) + '\n').encode('utf-8')
            return (f'home_{period}_report.csv', 'text/csv; charset=utf-8', content)

        pdf_text = [
            f'Risto AI - Home Report ({period_label})',
            f'Greeting: {home.greeting_name}',
            f'Restaurant: {home.restaurant_name or "-"}',
            f'VAT Balance: {section.vat_balance:.2f}',
            'Metrics:',
        ]
        for metric in section.metrics:
            pdf_text.append(f'- {metric.label}: {metric.value:.2f} ({metric.change_percent:+.1f}%)')
        pdf_text.append('Cash Management:')
        for item in section.cash_management:
            pdf_text.append(f'- {item.label}: {item.amount:.2f}')
        pdf_text.append('Trend:')
        for point in section.revenue:
            pdf_text.append(f'- {point.label}: {point.value:.2f}')

        content = self._build_simple_pdf('\n'.join(pdf_text))
        return (f'home_{period}_report.pdf', 'application/pdf', content)

    async def _build_home_period_snapshot(
        self,
        *,
        scope_id: str,
        daily_records: list[dict],
        expenses: list[dict],
        cash_deposits: list[dict],
        period: str,
        from_date: date | None,
        to_date: date | None,
    ) -> RestaurantHomePeriodResponse:
        filtered_daily_records = self._filter_home_daily_records(daily_records, period=period, from_date=from_date, to_date=to_date)
        filtered_expenses = self._filter_home_expenses(expenses, period=period, from_date=from_date, to_date=to_date)
        filtered_cash_deposits = self._filter_home_cash_deposits(cash_deposits, period=period, from_date=from_date, to_date=to_date)

        insights = await self._get_or_generate_insights(scope_id=scope_id, daily_records=filtered_daily_records, expenses=filtered_expenses)
        metrics_context = self._build_metrics_context(daily_records=filtered_daily_records, expenses=filtered_expenses)

        revenue_points = self._build_home_revenue_chart(filtered_daily_records, period=period)
        if period == 'monthly':
            revenue_points = [ChartPointResponse(label=point.label.replace('W', 'Week '), value=point.value) for point in revenue_points]

        return RestaurantHomePeriodResponse(
            metrics=[
                MetricCardResponse(label="Revenue", value=metrics_context["revenue_total"], change_percent=metrics_context["revenue_change_percent"]),
                MetricCardResponse(label="Expenses", value=metrics_context["expenses_total"], change_percent=metrics_context["expense_change_percent"]),
                MetricCardResponse(label="Food Cost", value=metrics_context["food_cost_total"], change_percent=metrics_context["food_cost_change_percent"]),
                MetricCardResponse(label="Profit", value=metrics_context["profit_total"], change_percent=metrics_context["profit_change_percent"]),
            ],
            cash_management=[
                CashManagementItemResponse(label="Total Cash Collected", amount=metrics_context["cash_collected_total"], subtitle="From recorded daily entries"),
                CashManagementItemResponse(label="Cash Available", amount=metrics_context["cash_available"], subtitle="Estimated from register movements"),
                CashManagementItemResponse(label="Cash Deposited", amount=sum(float(item.get("amount", 0)) for item in filtered_cash_deposits), subtitle="Bank deposits logged"),
            ],
            vat_balance=self._calculate_vat_balance(metrics_context["revenue_total"], metrics_context["expenses_total"]),
            revenue=revenue_points,
            featured_insight=insights[0] if insights else None,
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

    async def create_document_from_confirmation(self, current_user: dict, payload: DocumentSaveRequest) -> DocumentConfirmSaveResponse:
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
        await self._sync_restaurant_record(scope_id=scope_id, business_date=resolved_invoice_date, current_user=current_user)
        return self._to_document_confirm_save(document)

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
        await self._sync_restaurant_record(scope_id=scope_id, business_date=effective_invoice_date, current_user=current_user)
        return self._to_document_detail(updated)

    async def list_documents(self, current_user: dict, *, page: int, page_size: int, status: str | None, search: str | None) -> DocumentListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.document_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size, status=status, search=search)
        return DocumentListResponse(items=[self._to_document_list_item(item) for item in items], **build_pagination_meta(total=total, page=page, page_size=page_size))

    async def get_document_detail(self, current_user: dict, document_id: str) -> DocumentDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        return self._to_document_detail(document)

    async def download_document_file(self, current_user: dict, document_id: str) -> tuple[str, bytes]:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        serialized = self.serialize(document)
        supplier = str(serialized.get("supplier_name") or "document").strip().lower().replace(" ", "-")
        safe_supplier = "".join(ch for ch in supplier if ch.isalnum() or ch in {"-", "_"}) or "document"
        return f"{safe_supplier}-{serialized['id']}.pdf", self._build_invoice_pdf(serialized)

    async def download_document_image(self, current_user: dict, document_id: str, *, image_format: str = 'svg') -> tuple[str, str, bytes]:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        serialized = self.serialize(document)
        supplier = str(serialized.get("supplier_name") or "document").strip().lower().replace(" ", "-")
        safe_supplier = "".join(ch for ch in supplier if ch.isalnum() or ch in {"-", "_"}) or "document"

        svg_text = self._build_document_svg(serialized)
        if image_format == 'svg':
            return f"{safe_supplier}-{serialized['id']}.svg", 'image/svg+xml', svg_text.encode('utf-8')

        if image_format == 'png':
            try:
                import cairosvg
            except ImportError as exc:
                raise ValidationException('PNG export requires cairosvg to be installed on the server') from exc
            try:
                png_bytes = cairosvg.svg2png(bytestring=svg_text.encode('utf-8'))
            except Exception as exc:
                raise ValidationException('Unable to generate PNG export for this invoice') from exc
            return f"{safe_supplier}-{serialized['id']}.png", 'image/png', png_bytes

        raise ValidationException('Unsupported image format')

    async def update_document(self, current_user: dict, document_id: str, payload: DocumentConfirmRequest) -> DocumentDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        updates = self._build_document_updates(current_user=current_user, payload=payload, mark_processed=False)
        updated = await self.document_repository.update(document["_id"], updates)
        if updated.get("status") == "processed":
            effective_invoice_date = payload.invoice_date
            if effective_invoice_date is None and updated.get("invoice_date"):
                effective_invoice_date = datetime.fromisoformat(str(updated["invoice_date"])).date()
            if effective_invoice_date is None:
                effective_invoice_date = datetime.now(UTC).date()
                updated = await self.document_repository.update(updated["_id"], {"invoice_date": effective_invoice_date.isoformat()})
            old_invoice_date_value = document.get("invoice_date")
            if old_invoice_date_value:
                await self._sync_restaurant_record(scope_id=scope_id, business_date=datetime.fromisoformat(str(old_invoice_date_value)).date(), current_user=current_user)
            await self._sync_restaurant_record(scope_id=scope_id, business_date=effective_invoice_date, current_user=current_user)
        return self._to_document_detail(updated)

    async def delete_document(self, current_user: dict, document_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        invoice_date = datetime.fromisoformat(str(document["invoice_date"])).date() if document.get("invoice_date") else None
        await self.document_repository.delete(document["_id"])
        if invoice_date:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=invoice_date, current_user=current_user)

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
        await self._sync_restaurant_record(scope_id=scope_id, business_date=payload.expense_date, current_user=current_user)
        return self._to_expense_response(document)

    async def list_expenses(self, current_user: dict, *, page: int, page_size: int) -> ExpenseListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.expense_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size)
        today = datetime.now(UTC).date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        serialized_items = self.serialize_list(items)
        today_total = round(sum(item["amount"] for item in serialized_items if item["expense_date"][:10] == today.isoformat()), 2)
        week_total = round(sum(item["amount"] for item in serialized_items if week_start.isoformat() <= item["expense_date"][:10] <= today.isoformat()), 2)
        month_total = round(sum(item["amount"] for item in serialized_items if month_start.isoformat() <= item["expense_date"][:10] <= today.isoformat()), 2)
        year_total = round(sum(item["amount"] for item in serialized_items if year_start.isoformat() <= item["expense_date"][:10] <= today.isoformat()), 2)
        category_totals: dict[str, float] = {}
        for item in serialized_items:
            category = str(item.get("category") or "Other")
            category_totals[category] = round(category_totals.get(category, 0.0) + float(item.get("amount", 0)), 2)
        total_spend = round(sum(category_totals.values()), 2)
        distribution = [
            ExpenseDistributionItemResponse(
                label=category,
                percentage=round((amount / max(total_spend, 1)) * 100, 1),
                percentage_label=f"{round((amount / max(total_spend, 1)) * 100):.0f}%",
            )
            for category, amount in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)[:3]
        ]
        summary = ExpenseSummaryResponse(
            today_total=today_total,
            today_total_formatted=self._format_currency(today_total),
            week_total=week_total,
            week_total_formatted=self._format_currency(week_total),
            month_total=month_total,
            month_total_formatted=self._format_currency(month_total),
            top_category=self._top_category(serialized_items),
        )
        return ExpenseListResponse(
            active_period="Today",
            summary=summary,
            distribution_total_label=distribution[0].percentage_label if distribution else None,
            expense_distribution=distribution,
            items=[self._to_expense_response(item) for item in items],
            **build_pagination_meta(total=total, page=page, page_size=page_size),
        )

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
            total_collected_formatted=self._format_currency(total_collected),
            cash_available=cash_available,
            cash_available_formatted=self._format_currency(cash_available),
            withdrawals_total=withdrawals_total,
            withdrawals_total_formatted=self._format_currency(withdrawals_total),
            bank_deposits_total=bank_deposits_total,
            bank_deposits_total_formatted=self._format_currency(bank_deposits_total),
            recent_deposits=[self._to_cash_deposit_response(item) for item in deposits[:10]],
        )

    async def get_daily_data_manual_entry(self, current_user: dict) -> DailyDataManualEntryResponse:
        return DailyDataManualEntryResponse(
            methods=[
                DailyDataManualMethodResponse(
                    key="method_1",
                    label="Method 1",
                    description="Cash tracking with POS, withdrawals, cash in/out, and cash expenses.",
                    fields=[
                        DailyDataFormFieldResponse(key="business_date", label="Business Date", value_type="date", required=True, section="cash_tracking"),
                        DailyDataFormFieldResponse(key="pos_payments", label="POS Payments (+)", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="cash_withdrawals", label="Cash Withdrawals (+)", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="cash_in", label="Cash In (-)", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="cash_out", label="Cash Out (+)", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="expenses_in_cash", label="Expenses in Cash (+)", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="notes", label="Add Note", value_type="string", placeholder="Optional note", section="cash_tracking"),
                    ],
                ),
                DailyDataManualMethodResponse(
                    key="method_2",
                    label="Method 2",
                    description="Payment inputs with customer covers and register opening/closing cash.",
                    fields=[
                        DailyDataFormFieldResponse(key="business_date", label="Business Date", value_type="date", required=True, section="payment_inputs"),
                        DailyDataFormFieldResponse(key="pos_payments", label="POS Payments (+)", value_type="number", placeholder="0.00", section="payment_inputs"),
                        DailyDataFormFieldResponse(key="cash_payments", label="Cash Payments (+)", value_type="number", placeholder="0.00", section="payment_inputs"),
                        DailyDataFormFieldResponse(key="bank_transfer_payments", label="Invoices Paid by Bank Transfer (+)", value_type="number", placeholder="0.00", section="payment_inputs"),
                        DailyDataFormFieldResponse(key="lunch_covers", label="Lunch Covers", value_type="integer", placeholder="0", section="customer_covers"),
                        DailyDataFormFieldResponse(key="dinner_covers", label="Dinner Covers", value_type="integer", placeholder="0", section="customer_covers"),
                        DailyDataFormFieldResponse(key="opening_cash", label="Opening Cash", value_type="number", placeholder="0.00", section="cash_register_balance"),
                        DailyDataFormFieldResponse(key="closing_cash", label="Closing Cash", value_type="number", placeholder="0.00", section="cash_register_balance"),
                    ],
                ),
            ]
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
            "business_date": business_date.isoformat(),
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
        await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)
        return self._to_daily_data_response(document)

    async def update_daily_data(self, current_user: dict, record_id: str, payload: DailyDataCreateRequest) -> DailyDataResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        existing_record = await self.daily_record_repository.get_scoped_by_id(record_id, scope_id)
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
        final_payload = {
            "tenant_id": scope_id,
            "business_date": business_date.isoformat(),
            "method": payload.method,
            **record_payload,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "profit": round(total_revenue - total_expenses, 2),
            "lunch_covers": lunch_covers,
            "dinner_covers": dinner_covers,
            "avg_revenue_per_cover": round(total_revenue / max(lunch_covers + dinner_covers, 1), 2),
            "created_by_user_id": existing_record.get("created_by_user_id", str(current_user["_id"])),
        }
        updated = await self.daily_record_repository.update(existing_record["_id"], final_payload)
        old_business_date = existing_record.get("business_date")
        if old_business_date and str(old_business_date) != business_date.isoformat():
            await self._sync_restaurant_record(scope_id=scope_id, business_date=datetime.fromisoformat(str(old_business_date)).date(), current_user=current_user)
        await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)
        return self._to_daily_data_response(updated)

    async def list_daily_data(self, current_user: dict, *, page: int, page_size: int, view: str, reference_date: date | None) -> DailyDataListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        anchor_date = reference_date or datetime.now(UTC).date()
        start_date, end_date = self._resolve_date_range(view=view, anchor_date=anchor_date)

        all_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_records = self.serialize_list(all_records)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_expenses = self.serialize_list(all_expenses)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)

        filtered_records = self._filter_daily_records_by_date_range(serialized_records, start_date=start_date, end_date=end_date)
        filtered_expenses = self._filter_expenses_by_date_range(serialized_expenses, start_date=start_date, end_date=end_date) if (start_date or end_date) else serialized_expenses

        filtered_documents = [item for item in self.serialize_list(all_documents) if item.get("status") == "processed"]
        buckets = self._build_daily_data_buckets(filtered_records, filtered_expenses, filtered_documents, anchor_date=anchor_date)
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
            add_button=DailyDataAddButtonResponse(endpoint="/api/v1/restaurant/manual-entry"),
            items=[self._to_daily_data_bucket_item(item, anchor_date=anchor_date, active_view=view) for item in page_items],
            **build_pagination_meta(total=total, page=page, page_size=page_size),
        )

    async def get_daily_data_detail(self, current_user: dict, record_id: str) -> DailyDataResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        record = await self.daily_record_repository.get_scoped_by_id(record_id, scope_id)
        return self._to_daily_data_response(record)

    async def get_daily_data_by_date_detail(self, current_user: dict, *, business_date: date | None = None) -> DailyDataDetailResponse | DailyDataCollectionResponse:
        if business_date is None:
            return await self.get_all_daily_data_by_date(current_user)
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        all_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)

        serialized_records = self.serialize_list(all_records)
        serialized_expenses = self.serialize_list(all_expenses)
        serialized_documents = self.serialize_list(all_documents)

        target_iso = business_date.isoformat()
        filtered_records = [item for item in serialized_records if item["business_date"] == target_iso]
        filtered_expenses = [
            item
            for item in serialized_expenses
            if datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date() == business_date
        ]
        filtered_documents = [
            item
            for item in serialized_documents
            if item.get("invoice_date") == target_iso and item.get("status") == "processed"
        ]

        buckets = self._build_daily_data_buckets(filtered_records, filtered_expenses, filtered_documents, anchor_date=business_date)
        bucket = buckets[0] if buckets else {
            "id": f"date:{target_iso}",
            "business_date": target_iso,
            "total_revenue": 0.0,
            "total_expenses": 0.0,
            "total_covers": 0,
            "avg_revenue_per_cover": 0.0,
            "record_id": None,
            "created_at": datetime.now(UTC).isoformat(),
            "data_sources": [],
        }
        return self._to_daily_data_detail(bucket, invoices=filtered_documents, anchor_date=business_date, active_view="date", reference_date=business_date, period_start=business_date, period_end=business_date)

    async def get_daily_data_by_week_detail(self, current_user: dict, *, reference_date: date | None = None) -> DailyDataDetailResponse | DailyDataCollectionResponse:
        if reference_date is None:
            return await self.get_all_daily_data_by_period(current_user, view="week")
        return await self._get_daily_data_period_detail(current_user, view="week", reference_date=reference_date)

    async def get_daily_data_by_month_detail(self, current_user: dict, *, reference_date: date | None = None) -> DailyDataDetailResponse | DailyDataCollectionResponse:
        if reference_date is None:
            return await self.get_all_daily_data_by_period(current_user, view="month")
        return await self._get_daily_data_period_detail(current_user, view="month", reference_date=reference_date)

    async def get_all_daily_data_by_date(self, current_user: dict) -> DailyDataCollectionResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        all_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_records = self.serialize_list(all_records)
        serialized_expenses = self.serialize_list(all_expenses)
        serialized_documents = self.serialize_list(all_documents)
        buckets = self._build_daily_data_buckets(serialized_records, serialized_expenses, serialized_documents, anchor_date=datetime.now(UTC).date())
        items = [
            self._to_daily_data_detail(
                bucket,
                invoices=[item for item in serialized_documents if item.get("status") == "processed" and item.get("invoice_date") == bucket["business_date"]],
                anchor_date=datetime.fromisoformat(bucket["business_date"]).date(),
                active_view="date",
                reference_date=datetime.fromisoformat(bucket["business_date"]).date(),
                period_start=datetime.fromisoformat(bucket["business_date"]).date(),
                period_end=datetime.fromisoformat(bucket["business_date"]).date(),
            )
            for bucket in buckets
        ]
        return DailyDataCollectionResponse(active_view="date", total=len(items), items=items)

    async def get_all_daily_data_by_period(self, current_user: dict, *, view: str) -> DailyDataCollectionResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        all_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_records = self.serialize_list(all_records)
        serialized_expenses = self.serialize_list(all_expenses)
        serialized_documents = self.serialize_list(all_documents)

        unique_dates: set[date] = set()
        for item in serialized_records:
            unique_dates.add(datetime.fromisoformat(item["business_date"]).date())
        for item in serialized_expenses:
            unique_dates.add(datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date())
        for item in serialized_documents:
            if item.get("invoice_date"):
                unique_dates.add(datetime.fromisoformat(str(item["invoice_date"])).date())

        anchors: dict[str, date] = {}
        for item_date in unique_dates:
            start_date, _ = self._resolve_date_range(view=view, anchor_date=item_date)
            if start_date is not None:
                anchors[start_date.isoformat()] = start_date

        items: list[DailyDataDetailResponse] = []
        for anchor_date in sorted(anchors.values(), reverse=True):
            items.append(await self._get_daily_data_period_detail(current_user, view=view, reference_date=anchor_date))
        return DailyDataCollectionResponse(active_view=view, total=len(items), items=items)

    async def _get_daily_data_period_detail(self, current_user: dict, *, view: str, reference_date: date) -> DailyDataDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        start_date, end_date = self._resolve_date_range(view=view, anchor_date=reference_date)
        all_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)

        serialized_records = self.serialize_list(all_records)
        serialized_expenses = self.serialize_list(all_expenses)
        serialized_documents = self.serialize_list(all_documents)

        filtered_records = self._filter_daily_records_by_date_range(serialized_records, start_date=start_date, end_date=end_date)
        filtered_expenses = self._filter_expenses_by_date_range(serialized_expenses, start_date=start_date, end_date=end_date)
        filtered_documents = [
            item
            for item in serialized_documents
            if item.get("status") == "processed"
            and item.get("invoice_date")
            and start_date <= datetime.fromisoformat(str(item["invoice_date"])).date() <= end_date
        ]
        buckets = self._build_daily_data_buckets(filtered_records, filtered_expenses, filtered_documents, anchor_date=reference_date)
        aggregate_bucket = {
            "id": f"{view}:{reference_date.isoformat()}",
            "business_date": reference_date.isoformat(),
            "total_revenue": round(sum(float(item.get("total_revenue", 0)) for item in buckets), 2),
            "total_expenses": round(sum(float(item.get("total_expenses", 0)) for item in buckets), 2),
            "total_covers": int(sum(int(item.get("total_covers", 0)) for item in buckets)),
            "avg_revenue_per_cover": 0.0,
            "record_id": None,
            "created_at": datetime.now(UTC).isoformat(),
            "data_sources": [],
        }
        if aggregate_bucket["total_revenue"]:
            aggregate_bucket["avg_revenue_per_cover"] = round(aggregate_bucket["total_revenue"] / max(aggregate_bucket["total_covers"], 1), 2)
        aggregate_bucket["data_sources"] = [
            DailyDataEntrySourceResponse(
                kind="uploaded_invoice",
                label="Uploaded invoices",
                count=len(filtered_documents),
                total_amount=round(sum(float(item.get("total_amount", 0)) for item in filtered_documents), 2),
                endpoint=f"/api/v1/restaurant/documents?from_date={start_date.isoformat()}&to_date={end_date.isoformat()}",
            )
        ] if filtered_documents else []
        return self._to_daily_data_detail(
            aggregate_bucket,
            invoices=filtered_documents,
            anchor_date=reference_date,
            active_view=view,
            reference_date=reference_date,
            period_start=start_date,
            period_end=end_date,
        )

    async def delete_daily_data(self, current_user: dict, record_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        record = await self.daily_record_repository.get_scoped_by_id(record_id, scope_id)
        business_date = record.get("business_date")
        await self.daily_record_repository.delete(record["_id"])
        if business_date:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)

    async def create_inventory_item(self, current_user: dict, payload: Any) -> InventoryItemResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        history = []
        if payload.stock_quantity:
            history.append({"kind": "purchase_record", "quantity_delta": round(payload.stock_quantity * payload.unit_price, 2), "occurred_at": datetime.now(UTC)})
            history.append({"kind": "stock_added", "quantity_delta": payload.stock_quantity, "occurred_at": datetime.now(UTC)})
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
                "history": history,
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        return self._to_inventory_item_response(document)

    async def list_inventory(self, current_user: dict, *, page: int, page_size: int, search: str | None, status: str | None, category: str | None) -> InventoryListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.inventory_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size, search=search, status=status, category=category)
        serialized_items = self.serialize_list(items)
        total_inventory_value = round(sum(item["stock_quantity"] * item["unit_price"] for item in serialized_items), 2)
        return InventoryListResponse(total_inventory_value=total_inventory_value, total_inventory_value_formatted=self._format_currency(total_inventory_value), inventory_growth_percent=4.2 if serialized_items else 0.0, items=[self._to_inventory_item_response(item) for item in items], **build_pagination_meta(total=total, page=page, page_size=page_size))

    async def get_inventory_item(self, current_user: dict, item_id: str) -> InventoryDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        return self._to_inventory_detail_response(item)

    async def update_inventory_item(self, current_user: dict, item_id: str, payload: InventoryUpdateRequest) -> InventoryDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        updates = payload.model_dump(exclude_none=True)
        if "purchase_date" in updates and updates["purchase_date"] is not None:
            updates["purchase_date"] = updates["purchase_date"].isoformat()
        stock_quantity = float(updates.get("stock_quantity", item.get("stock_quantity", 0)))
        alert_threshold = float(updates.get("alert_threshold", item.get("alert_threshold", 0)))
        updates["stock_status"] = self._resolve_stock_status(stock_quantity, alert_threshold)
        updated = await self.inventory_repository.update(item["_id"], updates)
        return self._to_inventory_detail_response(updated)

    async def delete_inventory_item(self, current_user: dict, item_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        await self.inventory_repository.delete(item["_id"])

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

    async def get_analytics(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsOverviewResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)

        filtered_daily_records = self._filter_home_daily_records(daily_records, period=period, from_date=from_date, to_date=to_date)
        filtered_expenses = self._filter_home_expenses(expenses, period=period, from_date=from_date, to_date=to_date)

        serialized_documents = [item for item in self.serialize_list(documents) if item.get("status") == "processed"]
        filtered_documents = []
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date)
        for item in serialized_documents:
            invoice_date = self._safe_parse_date(item.get('invoice_date'))
            if start_date is not None and invoice_date < start_date:
                continue
            if end_date is not None and invoice_date > end_date:
                continue
            filtered_documents.append(item)

        context = self._build_metrics_context(daily_records=filtered_daily_records, expenses=filtered_expenses)
        serialized_records = filtered_daily_records
        serialized_expenses = filtered_expenses
        this_week_revenue = round(sum(float(item.get("total_revenue", 0)) for item in serialized_records), 2)
        last_week_revenue = round(this_week_revenue / 1.125, 2) if this_week_revenue else 0.0
        lunch_covers = int(sum(int(item.get("lunch_covers", 0)) for item in serialized_records))
        dinner_covers = int(sum(int(item.get("dinner_covers", 0)) for item in serialized_records))
        food_cost_total = round(sum(float(item.get("amount", 0)) for item in serialized_expenses if "food" in str(item.get("category", "")).lower()), 2)
        staff_cost_total = round(sum(float(item.get("amount", 0)) for item in serialized_expenses if "staff" in str(item.get("category", "")).lower()), 2)
        supplier_alerts = [
            AnalyticsSupplierAlertResponse(**item)
            for item in await self._build_supplier_alerts(serialized_expenses=serialized_expenses, serialized_documents=filtered_documents)
        ]
        return AnalyticsOverviewResponse(
            active_filter=self._analytics_filter_label(period),
            insight_banner=await self._build_analytics_insight_banner(serialized_records=serialized_records, serialized_expenses=serialized_expenses),
            estimated_profit=context["profit_total"],
            estimated_profit_formatted=self._format_currency(float(context["profit_total"])),
            peak_hour_label="7:00 PM",
            peak_hour_subtitle="92% Capacity Avg",
            revenue_total=context["revenue_total"],
            revenue_total_formatted=self._format_currency(float(context["revenue_total"])),
            revenue_change_percent=context["revenue_change_percent"],
            weekly_revenue=self._build_home_revenue_chart(filtered_daily_records, period=period),
            metric_tiles=[
                AnalyticsMetricTileResponse(label="Estimated Profit", value=float(context["profit_total"]), value_formatted=self._format_currency(float(context["profit_total"])), change_percent=8.2),
                AnalyticsMetricTileResponse(label="Peak Hour", value="7:00 PM", value_formatted="7:00 PM", subtitle="92% Capacity Avg"),
            ],
            summary_stats=[
                AnalyticsSummaryStatResponse(label="Revenue", value=round(this_week_revenue / 1000, 1), value_formatted=f"${round(this_week_revenue / 1000, 1):.1f}k"),
                AnalyticsSummaryStatResponse(label="Covers", value=context["covers_total"], value_formatted=str(context["covers_total"])),
                AnalyticsSummaryStatResponse(label="Avg Rev", value=context["avg_revenue_per_cover"], value_formatted=f"${float(context['avg_revenue_per_cover']):.2f}"),
            ],
            revenue_comparison=[
                AnalyticsComparisonRowResponse(label=self._analytics_current_revenue_label(period), value=this_week_revenue, value_formatted=self._format_currency(this_week_revenue)),
                AnalyticsComparisonRowResponse(label=self._analytics_previous_revenue_label(period), value=last_week_revenue, value_formatted=self._format_currency(last_week_revenue)),
            ],
            covers_total=context["covers_total"],
            covers_activity=[
                AnalyticsSummaryStatResponse(label="Lunch", value=lunch_covers, value_formatted=str(lunch_covers)),
                AnalyticsSummaryStatResponse(label="Dinner", value=dinner_covers, value_formatted=str(dinner_covers)),
            ],
            avg_revenue_per_cover=context["avg_revenue_per_cover"],
            avg_revenue_per_cover_formatted=f"${float(context['avg_revenue_per_cover']):.2f}",
            cost_breakdown=[
                AnalyticsSummaryStatResponse(label="Food Cost", value=round((food_cost_total / max(this_week_revenue, 1)) * 100, 1), value_formatted=f"{round((food_cost_total / max(this_week_revenue, 1)) * 100, 1):.0f}%"),
                AnalyticsSummaryStatResponse(label="Staff Cost", value=round((staff_cost_total / max(this_week_revenue, 1)) * 100, 1), value_formatted=f"{round((staff_cost_total / max(this_week_revenue, 1)) * 100, 1):.0f}%"),
            ],
            supplier_price_alerts=supplier_alerts,
        )

    async def export_analytics_report(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        export_format: str = "pdf",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[str, str, bytes]:
        analytics = await self.get_analytics(current_user, period=period, from_date=from_date, to_date=to_date)
        period_label = self._analytics_filter_label(period)

        if export_format == 'excel':
            lines = [
                'Section,Label,Value',
                f'Header,Period,{period_label}',
                f'Metric,Estimated Profit,{analytics.estimated_profit}',
                f'Metric,Revenue Total,{analytics.revenue_total}',
                f'Metric,Avg Rev Per Cover,{analytics.avg_revenue_per_cover}',
            ]
            for item in analytics.weekly_revenue:
                lines.append(f'Revenue Trend,{item.label},{item.value}')
            for item in analytics.revenue_comparison:
                lines.append(f'Revenue Comparison,{item.label},{item.value}')
            for item in analytics.supplier_price_alerts:
                lines.append(f'Supplier Alert,{item.title},{item.subtitle}')
            content = ('\n'.join(lines) + '\n').encode('utf-8')
            return (f'analytics_{period}_report.csv', 'text/csv; charset=utf-8', content)

        pdf_text = [
            f'Risto AI - Analytics Report ({period_label})',
            f'Estimated Profit: {analytics.estimated_profit_formatted}',
            f'Revenue Total: {analytics.revenue_total_formatted}',
            f'Peak Hour: {analytics.peak_hour_label}',
            'Revenue Trend:',
        ]
        for item in analytics.weekly_revenue:
            pdf_text.append(f'- {item.label}: {item.value:.2f}')
        pdf_text.append('Revenue Comparison:')
        for item in analytics.revenue_comparison:
            pdf_text.append(f'- {item.label}: {item.value_formatted}')
        pdf_text.append('Supplier Alerts:')
        for item in analytics.supplier_price_alerts:
            pdf_text.append(f'- {item.title}: {item.subtitle}')
        content = self._build_simple_pdf('\n'.join(pdf_text))
        return (f'analytics_{period}_report.pdf', 'application/pdf', content)

    async def get_analytics_business_insight(self, current_user: dict) -> AnalyticsInsightBannerResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=90)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=90)
        return await self._build_analytics_insight_banner(
            serialized_records=self.serialize_list(daily_records),
            serialized_expenses=self.serialize_list(expenses),
        )

    async def list_chat_messages(self, current_user: dict) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=40)
        messages = [self._to_chat_message_response(item) for item in items]
        if not messages:
            messages = [
                ChatMessageResponse(
                    id="welcome-message",
                    role="assistant",
                    sender_label="Risto AI",
                    variant="assistant",
                    message="Hello! I can help you analyze your restaurant data. What would you like to know?",
                    created_at=datetime.now(UTC).isoformat(),
                )
            ]
        return ChatConversationResponse(
            quick_prompts=[
                ChatQuickPromptResponse(label="How can I increase revenue?"),
                ChatQuickPromptResponse(label="What are my biggest expenses?"),
            ],
            attachment_options=[
                ChatAttachmentOptionResponse(key="attach", label="Attach"),
                ChatAttachmentOptionResponse(key="camera", label="Camera"),
                ChatAttachmentOptionResponse(key="gallery", label="Gallery"),
                ChatAttachmentOptionResponse(key="docs", label="Docs"),
            ],
            realtime=self._build_chat_realtime_config(),
            messages=messages,
        )

    async def create_chat_message(self, current_user: dict, payload: ChatMessageCreateRequest) -> ChatConversationResponse:
        return await self._create_chat_conversation(current_user=current_user, payload=payload)

    async def create_chat_message_with_attachment(
        self,
        current_user: dict,
        *,
        payload: ChatMessageCreateRequest,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
    ) -> ChatConversationResponse:
        if not file_bytes:
            raise ValidationException("Uploaded chat attachment is empty")
        attachment_context = await self.openai_service.summarize_chat_attachment(
            file_name=file_name,
            content_type=content_type,
            file_bytes=file_bytes,
        )
        return await self._create_chat_conversation(
            current_user=current_user,
            payload=payload,
            attachment_name=file_name,
            attachment_source=payload.attachment_source,
            attachment_summary=attachment_context.get("summary"),
            attachment_context=attachment_context,
        )

    async def _create_chat_conversation(
        self,
        *,
        current_user: dict,
        payload: ChatMessageCreateRequest,
        attachment_name: str | None = None,
        attachment_source: str | None = None,
        attachment_summary: str | None = None,
        attachment_context: dict[str, Any] | None = None,
    ) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        user_message_payload = {
            "tenant_id": scope_id,
            "role": "user",
            "message": payload.message,
            "created_by_user_id": str(current_user["_id"]),
        }
        if attachment_name:
            user_message_payload["attachment_name"] = attachment_name
            user_message_payload["attachment_source"] = attachment_source
            user_message_payload["attachment_summary"] = attachment_summary
        await self.chat_repository.create(user_message_payload)
        recent = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=12)
        daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=30)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=30)
        metrics_context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
        assistant_text = await self.openai_service.generate_chat_reply(
            prompt=payload.message,
            metrics_context=metrics_context,
            recent_messages=[self.serialize(item) for item in recent],
            attachment_context=attachment_context,
        )
        insight_message = self._build_chat_insight_message(metrics_context)
        await self.chat_repository.create({"tenant_id": scope_id, "role": "insight", "message": insight_message, "created_by_user_id": str(current_user["_id"])})
        await self.chat_repository.create({"tenant_id": scope_id, "role": "assistant", "message": assistant_text, "created_by_user_id": str(current_user["_id"])})
        items = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=40)
        return ChatConversationResponse(
            quick_prompts=[
                ChatQuickPromptResponse(label="How can I increase revenue?"),
                ChatQuickPromptResponse(label="What are my biggest expenses?"),
            ],
            attachment_options=[
                ChatAttachmentOptionResponse(key="attach", label="Attach"),
                ChatAttachmentOptionResponse(key="camera", label="Camera"),
                ChatAttachmentOptionResponse(key="gallery", label="Gallery"),
                ChatAttachmentOptionResponse(key="docs", label="Docs"),
            ],
            realtime=self._build_chat_realtime_config(),
            messages=[self._to_chat_message_response(item) for item in items],
        )

    def _build_chat_realtime_config(self) -> ChatRealtimeConfigResponse:
        try:
            import socketio  # type: ignore
        except ImportError:
            enabled = False
        else:
            enabled = socketio is not None
        return ChatRealtimeConfigResponse(enabled=enabled)

    async def get_profile(self, current_user: dict) -> RestaurantProfileResponse:
        serialized = self.serialize(current_user)
        preferred_language = serialized.get("preferred_language", "en")
        location = serialized.get("city_location") or serialized.get("location")
        restaurant_name = serialized.get("restaurant_name")
        profile_subtitle = f"{restaurant_name} ? {location}" if restaurant_name and location else restaurant_name or location
        return RestaurantProfileResponse(
            full_name=serialized["full_name"],
            email=serialized["email"],
            phone=serialized.get("phone"),
            restaurant_name=restaurant_name,
            restaurant_type=serialized.get("restaurant_type"),
            location=serialized.get("location"),
            city_location=location,
            number_of_seats=serialized.get("number_of_seats"),
            preferred_language=preferred_language,
            profile_subtitle=profile_subtitle,
            language_options=[
                SettingsLanguageOptionResponse(code="en", label="English", active=preferred_language == "en"),
                SettingsLanguageOptionResponse(code="it", label="Italian", active=preferred_language == "it"),
            ],
            account_settings=[
                SettingsActionItemResponse(label="Manage Subscription", endpoint="/api/v1/subscriptions/user/current"),
                SettingsActionItemResponse(label="Notification Settings", endpoint="/api/v1/restaurant/settings/profile"),
                SettingsActionItemResponse(label="Change Password", endpoint="/api/v1/auth/restaurant/forgot-password"),
                SettingsActionItemResponse(label="Two-Factor Authentication", endpoint="/api/v1/restaurant/settings/profile"),
            ],
            support_legal=[
                SettingsActionItemResponse(label="Terms & Conditions", endpoint="/api/v1/support/tickets"),
                SettingsActionItemResponse(label="Privacy Policy", endpoint="/api/v1/support/tickets"),
                SettingsActionItemResponse(label="Help Center", endpoint="/api/v1/support/tickets"),
            ],
        )

    async def update_profile(self, current_user: dict, payload: RestaurantProfileUpdateRequest) -> RestaurantProfileResponse:
        updates = payload.model_dump(exclude_none=True)
        if "city_location" in updates and "location" not in updates:
            updates["location"] = updates["city_location"]
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

    async def _sync_restaurant_record(self, *, scope_id: str, business_date: date, current_user: dict) -> None:
        resolved_business_date = business_date if hasattr(business_date, "isoformat") else datetime.fromisoformat(str(business_date)).date()
        all_daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)

        target_date = resolved_business_date.isoformat()
        serialized_daily_records = self.serialize_list(all_daily_records)
        serialized_expenses = self.serialize_list(all_expenses)
        serialized_documents = self.serialize_list(all_documents)

        manual_record = next((item for item in serialized_daily_records if str(item.get("business_date", "")).startswith(target_date)), None)
        manual_expenses = [
            item
            for item in serialized_expenses
            if datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date().isoformat() == target_date
        ]
        uploaded_invoices = [
            item
            for item in serialized_documents
            if item.get("status") == "processed" and str(item.get("invoice_date", "")).startswith(target_date)
        ]

        now = datetime.now(UTC)
        if not manual_record and not manual_expenses and not uploaded_invoices:
            existing = await self.record_repository.find_by_business_date(scope_id=scope_id, business_date=resolved_business_date)
            if existing:
                await self.record_repository.delete(existing["_id"])
        else:
            manual_revenue = float(manual_record.get("total_revenue", 0)) if manual_record else 0.0
            manual_entry_expenses = float(manual_record.get("total_expenses", 0)) if manual_record else 0.0
            uploaded_invoice_total = round(sum(float(item.get("total_amount", 0)) for item in uploaded_invoices), 2)
            manual_expense_total = round(sum(float(item.get("amount", 0)) for item in manual_expenses), 2)
            lunch_covers = int(manual_record.get("lunch_covers", 0)) if manual_record else 0
            dinner_covers = int(manual_record.get("dinner_covers", 0)) if manual_record else 0
            total_covers = lunch_covers + dinner_covers
            total_expenses = round(manual_entry_expenses + uploaded_invoice_total + manual_expense_total, 2)
            total_revenue = round(manual_revenue, 2)

            await self.record_repository.upsert_by_business_date(
                scope_id=scope_id,
                business_date=resolved_business_date,
                payload={
                    "manual_entry_id": manual_record.get("id") if manual_record else None,
                    "manual_method": manual_record.get("method") if manual_record else None,
                    "manual_revenue": total_revenue,
                    "manual_entry_expenses": manual_entry_expenses,
                    "uploaded_invoice_total": uploaded_invoice_total,
                    "uploaded_invoice_count": len(uploaded_invoices),
                    "uploaded_invoice_document_ids": [item["id"] for item in uploaded_invoices],
                    "manual_expense_total": manual_expense_total,
                    "manual_expense_count": len(manual_expenses),
                    "manual_expense_ids": [item["id"] for item in manual_expenses],
                    "total_revenue": total_revenue,
                    "total_expenses": total_expenses,
                    "profit": round(total_revenue - total_expenses, 2),
                    "lunch_covers": lunch_covers,
                    "dinner_covers": dinner_covers,
                    "total_covers": total_covers,
                    "avg_revenue_per_cover": round(total_revenue / max(total_covers, 1), 2) if total_revenue else 0.0,
                    "source_breakdown": {
                        "manual_entry": bool(manual_record),
                        "uploaded_invoice_count": len(uploaded_invoices),
                        "manual_expense_count": len(manual_expenses),
                    },
                    "last_synced_by_user_id": str(current_user["_id"]),
                    "last_synced_at": now,
                },
            )

        await self._sync_restaurant_week_record(
            scope_id=scope_id,
            business_date=resolved_business_date,
            serialized_daily_records=serialized_daily_records,
            serialized_expenses=serialized_expenses,
            serialized_documents=serialized_documents,
            current_user=current_user,
        )
        await self._sync_restaurant_month_record(
            scope_id=scope_id,
            business_date=resolved_business_date,
            serialized_daily_records=serialized_daily_records,
            serialized_expenses=serialized_expenses,
            serialized_documents=serialized_documents,
            current_user=current_user,
        )

    async def _sync_restaurant_week_record(
        self,
        *,
        scope_id: str,
        business_date: date,
        serialized_daily_records: list[dict[str, Any]],
        serialized_expenses: list[dict[str, Any]],
        serialized_documents: list[dict[str, Any]],
        current_user: dict,
    ) -> None:
        week_start = business_date - timedelta(days=business_date.weekday())
        week_end = week_start + timedelta(days=6)
        weekly_manual_records = [
            item for item in serialized_daily_records if week_start <= datetime.fromisoformat(str(item["business_date"])).date() <= week_end
        ]
        weekly_expenses = [
            item for item in serialized_expenses if week_start <= datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date() <= week_end
        ]
        weekly_invoices = [
            item
            for item in serialized_documents
            if item.get("status") == "processed"
            and item.get("invoice_date")
            and week_start <= datetime.fromisoformat(str(item["invoice_date"])).date() <= week_end
        ]
        if not weekly_manual_records and not weekly_expenses and not weekly_invoices:
            existing = await self.weekly_record_repository.find_by_week_start_date(scope_id=scope_id, week_start_date=week_start)
            if existing:
                await self.weekly_record_repository.delete(existing["_id"])
            return
        total_revenue = round(sum(float(item.get("total_revenue", 0)) for item in weekly_manual_records), 2)
        manual_entry_expenses = round(sum(float(item.get("total_expenses", 0)) for item in weekly_manual_records), 2)
        manual_expense_total = round(sum(float(item.get("amount", 0)) for item in weekly_expenses), 2)
        uploaded_invoice_total = round(sum(float(item.get("total_amount", 0)) for item in weekly_invoices), 2)
        total_expenses = round(manual_entry_expenses + manual_expense_total + uploaded_invoice_total, 2)
        total_covers = int(sum(int(item.get("lunch_covers", 0)) + int(item.get("dinner_covers", 0)) for item in weekly_manual_records))
        await self.weekly_record_repository.upsert_by_week_start_date(
            scope_id=scope_id,
            week_start_date=week_start,
            payload={
                "week_end_date": week_end.isoformat(),
                "manual_entry_ids": [item["id"] for item in weekly_manual_records],
                "manual_expense_ids": [item["id"] for item in weekly_expenses],
                "uploaded_invoice_document_ids": [item["id"] for item in weekly_invoices],
                "total_revenue": total_revenue,
                "manual_entry_expenses": manual_entry_expenses,
                "manual_expense_total": manual_expense_total,
                "uploaded_invoice_total": uploaded_invoice_total,
                "total_expenses": total_expenses,
                "profit": round(total_revenue - total_expenses, 2),
                "total_covers": total_covers,
                "avg_revenue_per_cover": round(total_revenue / max(total_covers, 1), 2) if total_revenue else 0.0,
                "invoice_count": len(weekly_invoices),
                "manual_entry_count": len(weekly_manual_records),
                "manual_expense_count": len(weekly_expenses),
                "last_synced_by_user_id": str(current_user["_id"]),
                "last_synced_at": datetime.now(UTC),
            },
        )

    async def _sync_restaurant_month_record(
        self,
        *,
        scope_id: str,
        business_date: date,
        serialized_daily_records: list[dict[str, Any]],
        serialized_expenses: list[dict[str, Any]],
        serialized_documents: list[dict[str, Any]],
        current_user: dict,
    ) -> None:
        month_start = business_date.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        month_key = month_start.strftime("%Y-%m")
        monthly_manual_records = [
            item for item in serialized_daily_records if month_start <= datetime.fromisoformat(str(item["business_date"])).date() <= month_end
        ]
        monthly_expenses = [
            item for item in serialized_expenses if month_start <= datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date() <= month_end
        ]
        monthly_invoices = [
            item
            for item in serialized_documents
            if item.get("status") == "processed"
            and item.get("invoice_date")
            and month_start <= datetime.fromisoformat(str(item["invoice_date"])).date() <= month_end
        ]
        if not monthly_manual_records and not monthly_expenses and not monthly_invoices:
            existing = await self.monthly_record_repository.find_by_month_key(scope_id=scope_id, month_key=month_key)
            if existing:
                await self.monthly_record_repository.delete(existing["_id"])
            return
        total_revenue = round(sum(float(item.get("total_revenue", 0)) for item in monthly_manual_records), 2)
        manual_entry_expenses = round(sum(float(item.get("total_expenses", 0)) for item in monthly_manual_records), 2)
        manual_expense_total = round(sum(float(item.get("amount", 0)) for item in monthly_expenses), 2)
        uploaded_invoice_total = round(sum(float(item.get("total_amount", 0)) for item in monthly_invoices), 2)
        total_expenses = round(manual_entry_expenses + manual_expense_total + uploaded_invoice_total, 2)
        total_covers = int(sum(int(item.get("lunch_covers", 0)) + int(item.get("dinner_covers", 0)) for item in monthly_manual_records))
        await self.monthly_record_repository.upsert_by_month_key(
            scope_id=scope_id,
            month_key=month_key,
            payload={
                "month_start_date": month_start.isoformat(),
                "month_end_date": month_end.isoformat(),
                "manual_entry_ids": [item["id"] for item in monthly_manual_records],
                "manual_expense_ids": [item["id"] for item in monthly_expenses],
                "uploaded_invoice_document_ids": [item["id"] for item in monthly_invoices],
                "total_revenue": total_revenue,
                "manual_entry_expenses": manual_entry_expenses,
                "manual_expense_total": manual_expense_total,
                "uploaded_invoice_total": uploaded_invoice_total,
                "total_expenses": total_expenses,
                "profit": round(total_revenue - total_expenses, 2),
                "total_covers": total_covers,
                "avg_revenue_per_cover": round(total_revenue / max(total_covers, 1), 2) if total_revenue else 0.0,
                "invoice_count": len(monthly_invoices),
                "manual_entry_count": len(monthly_manual_records),
                "manual_expense_count": len(monthly_expenses),
                "last_synced_by_user_id": str(current_user["_id"]),
                "last_synced_at": datetime.now(UTC),
            },
        )

    async def _build_analytics_insight_banner(
        self,
        *,
        serialized_records: list[dict[str, Any]],
        serialized_expenses: list[dict[str, Any]],
    ) -> AnalyticsInsightBannerResponse:
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        revenue_by_weekday: dict[int, float] = {}
        for item in serialized_records:
            try:
                weekday = datetime.fromisoformat(str(item.get("business_date"))).date().weekday()
            except ValueError:
                continue
            revenue_by_weekday[weekday] = revenue_by_weekday.get(weekday, 0.0) + float(item.get("total_revenue", 0))

        category_groups = {
            "staff": ("staff", "labor", "payroll", "salary"),
            "food": ("food", "inventory", "supplier", "grocery"),
            "operations": ("operations", "utility", "cleaning", "rent", "maintenance"),
        }
        costs_by_group_by_weekday: dict[str, dict[int, float]] = {key: {} for key in category_groups}
        for item in serialized_expenses:
            category = str(item.get("category", "")).lower()
            try:
                weekday = datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date().weekday()
            except (KeyError, ValueError):
                continue
            amount = float(item.get("amount", 0))
            for group_name, keywords in category_groups.items():
                if any(keyword in category for keyword in keywords):
                    costs_by_group_by_weekday[group_name][weekday] = costs_by_group_by_weekday[group_name].get(weekday, 0.0) + amount
                    break

        best_group = None
        best_weekday = None
        best_lift = None
        best_ratio = 0.0
        for group_name, weekday_costs in costs_by_group_by_weekday.items():
            weekday_ratios: list[tuple[int, float]] = []
            for weekday, cost in weekday_costs.items():
                revenue = revenue_by_weekday.get(weekday, 0.0)
                if revenue <= 0:
                    continue
                weekday_ratios.append((weekday, cost / revenue))
            if len(weekday_ratios) < 1:
                continue
            ratios_only = [ratio for _, ratio in weekday_ratios]
            baseline = sum(ratios_only) / len(ratios_only) if ratios_only else 0.0
            for weekday, ratio in weekday_ratios:
                lift = ((ratio - baseline) / baseline * 100) if baseline > 0 else ratio * 100
                if best_lift is None or lift > best_lift:
                    best_group = group_name
                    best_weekday = weekday
                    best_lift = lift
                    best_ratio = ratio

        if best_group is not None and best_weekday is not None and best_lift is not None and best_lift > 0:
            percent = max(1, round(best_lift))
            group_label = {"staff": "Staffing costs", "food": "Food costs", "operations": "Operating costs"}.get(best_group, "Costs")
            subtitle = {
                "staff": "Review labor scheduling against demand patterns.",
                "food": "Review purchasing and menu mix for this day.",
                "operations": "Review overhead allocations and shift planning.",
            }.get(best_group, "Review cost drivers for this day.")
            fallback_title = f"Optimization Tip: {group_label} are {percent}% higher on {weekday_names[best_weekday]}s relative to revenue."
            fallback_subtitle = subtitle
            generated = await self.openai_service.generate_business_insight(
                analytics_context={
                    "insight_type": best_group,
                    "weekday": weekday_names[best_weekday],
                    "lift_percent": percent,
                    "ratio": round(best_ratio * 100, 2),
                    "revenue_by_weekday": revenue_by_weekday,
                    "costs_by_group_by_weekday": costs_by_group_by_weekday,
                },
                fallback_title=fallback_title,
                fallback_subtitle=fallback_subtitle,
            )
            return AnalyticsInsightBannerResponse(title=generated["title"], subtitle=generated["subtitle"])

        if serialized_expenses:
            top_expense = max(serialized_expenses, key=lambda item: float(item.get("amount", 0)))
            category_name = str(top_expense.get("category", "operating"))
            fallback_title = f"Optimization Tip: {category_name} is your largest recent cost driver."
            fallback_subtitle = "Review the largest expense category against revenue trend."
            generated = await self.openai_service.generate_business_insight(
                analytics_context={
                    "insight_type": "largest_expense",
                    "category": category_name,
                    "top_expense_amount": float(top_expense.get("amount", 0)),
                },
                fallback_title=fallback_title,
                fallback_subtitle=fallback_subtitle,
            )
            return AnalyticsInsightBannerResponse(title=generated["title"], subtitle=generated["subtitle"])

        generated = await self.openai_service.generate_business_insight(
            analytics_context={"insight_type": "insufficient_data"},
            fallback_title="Optimization Tip: Add more daily data to unlock pattern-based insights.",
            fallback_subtitle="We need a bit more revenue and cost history to generate stronger recommendations.",
        )
        return AnalyticsInsightBannerResponse(title=generated["title"], subtitle=generated["subtitle"])

    async def _build_supplier_alerts(
        self,
        *,
        serialized_expenses: list[dict[str, Any]],
        serialized_documents: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        category_totals: dict[str, float] = {}

        for expense in serialized_expenses:
            category = str(expense.get("category") or "Supplier").strip() or "Supplier"
            category_totals[category] = round(category_totals.get(category, 0.0) + float(expense.get("amount", 0)), 2)

        for document in serialized_documents:
            supplier_name = str(document.get("supplier_name") or document.get("source_file_name") or "Supplier").strip() or "Supplier"
            category_totals[supplier_name] = round(category_totals.get(supplier_name, 0.0) + float(document.get("total_amount", 0)), 2)

        if not category_totals:
            return []

        sorted_categories = sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
        total_spend = round(sum(category_totals.values()), 2)
        fallback_alerts: list[dict[str, str]] = []
        for category, amount in sorted_categories[:3]:
            share = round((amount / max(total_spend, 1)) * 100, 1)
            impact = round(amount * 0.1, 2)
            fallback_alerts.append(
                {
                    "title": f"{category} prices increased by {max(5, int(round(share / 2)))}%",
                    "subtitle": f"Impact: +{self._format_currency(impact)} monthly cost pressure",
                }
            )

        generated_alerts = await self.openai_service.generate_supplier_alerts(
            analytics_context={
                "total_spend": total_spend,
                "expense_count": len(serialized_expenses),
                "invoice_count": len(serialized_documents),
                "top_categories": [
                    {"category": category, "amount": amount, "share_percent": round((amount / max(total_spend, 1)) * 100, 1)}
                    for category, amount in sorted_categories[:5]
                ],
            },
            fallback_alerts=fallback_alerts,
        )
        return generated_alerts

    @staticmethod
    def _pdf_escape(value: str) -> str:
        return value.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    def _build_invoice_pdf(self, document: dict[str, Any]) -> bytes:
        line_items = document.get('line_items', [])
        supplier_name = str(document.get('supplier_name') or 'Unknown Supplier')
        invoice_number = str(document.get('invoice_number') or 'N/A')
        invoice_date = str(self._format_human_date(document.get('invoice_date')) or '-')
        upload_date = str(self._format_human_date(document.get('upload_date')) or '-')
        total_amount = self._format_currency(float(document.get('total_amount', 0)))

        width = 595
        height = 842
        margin = 32

        row_height = 26
        max_rows = 15
        visible_items = line_items[:max_rows]
        table_top = 562
        table_height = max(160, 54 + len(visible_items) * row_height + 24)
        table_bottom = table_top - table_height

        cmds: list[str] = []
        cmds.append('0.985 0.99 1 rg')
        cmds.append(f'0 0 {width} {height} re f')

        cmds.append('1 1 1 rg')
        cmds.append('0.85 0.89 0.93 RG')
        cmds.append('1 w')
        cmds.append(f'12 12 {width - 24} {height - 24} re B')

        cmds.append('0.94 0.9 0.85 rg')
        cmds.append('430 640 140 52 re f')

        cmds.append('0.85 0.89 0.93 RG')
        cmds.append('1 w')
        cmds.append(f'{margin} {table_bottom} {width - margin * 2} {table_height} re S')

        y_div = table_top - 34
        cmds.append('0.85 0.89 0.93 RG')
        cmds.append('1 w')
        cmds.append(f'{margin + 10} {y_div} {width - margin * 2 - 20} {y_div} l S')

        def add_text(x: float, y: float, size: int, value: str, *, bold: bool = False, color: str = '0.06 0.14 0.27') -> None:
            font = 'F2' if bold else 'F1'
            safe = self._pdf_escape(value)
            cmds.append(f'BT {color} rg /{font} {size} Tf 1 0 0 1 {x} {y} Tm ({safe}) Tj ET')

        add_text(margin, 776, 20, 'INVOICE', bold=True)
        add_text(margin, 742, 10, 'Supplier', color='0.35 0.45 0.57')
        add_text(margin, 720, 16, supplier_name, bold=True)

        add_text(355, 742, 10, 'Invoice Number', color='0.35 0.45 0.57')
        add_text(355, 720, 15, invoice_number, bold=True)

        add_text(margin, 674, 10, 'Invoice Date', color='0.35 0.45 0.57')
        add_text(margin, 652, 14, invoice_date, bold=True)

        add_text(190, 674, 10, 'Upload Date', color='0.35 0.45 0.57')
        add_text(190, 652, 14, upload_date, bold=True)

        add_text(442, 666, 10, 'Total Amount', color='0.55 0.24 0.08')
        add_text(442, 644, 20, total_amount, bold=True, color='0.95 0.45 0.1')

        add_text(margin + 14, table_top - 22, 10, 'PRODUCT', color='0.35 0.45 0.57')
        add_text(304, table_top - 22, 10, 'QTY', color='0.35 0.45 0.57')
        add_text(388, table_top - 22, 10, 'PRICE', color='0.35 0.45 0.57')
        add_text(490, table_top - 22, 10, 'TOTAL', color='0.35 0.45 0.57')

        y = table_top - 44
        for item in visible_items:
            product_name = str(item.get('product_name') or 'Item')
            quantity = float(item.get('quantity', 0))
            unit_price = self._format_currency(float(item.get('unit_price', 0)))
            row_total = self._format_currency(float(item.get('total_price', 0)))

            add_text(margin + 14, y, 10, product_name)
            add_text(304, y, 10, f'Qty {quantity:.1f}', color='0.35 0.45 0.57')
            add_text(388, y, 10, unit_price, color='0.35 0.45 0.57')
            add_text(490, y, 10, row_total, bold=True)

            y_line = y - 10
            cmds.append('0.92 0.94 0.97 RG')
            cmds.append('0.8 w')
            cmds.append(f'{margin + 10} {y_line} {width - margin - 10} {y_line} l S')
            y -= row_height

        if len(line_items) > max_rows:
            add_text(margin + 14, table_bottom + 12, 9, f'... {len(line_items) - max_rows} more items omitted in preview export', color='0.55 0.45 0.35')

        stream = '\n'.join(cmds).encode('utf-8')
        return self._build_pdf_document(stream)

    def _build_document_svg(self, document: dict[str, Any]) -> str:
        line_items = document.get("line_items", [])
        width = 900
        row_height = 44
        items_top = 310
        items_height = max(220, len(line_items) * row_height + 60)
        height = items_top + items_height + 140
        supplier_name = escape(str(document.get("supplier_name") or "Unknown Supplier"))
        invoice_number = escape(str(document.get("invoice_number") or "N/A"))
        invoice_date = escape(str(self._format_human_date(document.get("invoice_date")) or "-"))
        upload_date = escape(str(self._format_human_date(document.get("upload_date")) or "-"))
        total_amount = escape(self._format_currency(float(document.get("total_amount", 0))))
        row_parts: list[str] = []
        y = items_top + 46
        for item in line_items:
            product_name = escape(str(item.get("product_name") or "Item"))
            quantity = escape(str(item.get("quantity", 0)))
            unit_price = escape(self._format_currency(float(item.get("unit_price", 0))))
            total_price = escape(self._format_currency(float(item.get("total_price", 0))))
            row_parts.append(
                f'<line x1="70" y1="{y + 18}" x2="830" y2="{y + 18}" stroke="#f1f5f9" stroke-width="1" />'
                f'<text x="80" y="{y}" font-size="20" fill="#0f172a" font-family="Arial">{product_name}</text>'
                f'<text x="470" y="{y}" font-size="20" fill="#64748b" font-family="Arial">Qty {quantity}</text>'
                f'<text x="590" y="{y}" font-size="20" fill="#64748b" font-family="Arial">{unit_price}</text>'
                f'<text x="730" y="{y}" font-size="20" fill="#111827" font-family="Arial" font-weight="700">{total_price}</text>'
            )
            y += row_height
        rows_svg = ''.join(row_parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="100%" height="100%" fill="#f8fafc"/>'
            f'<rect x="36" y="36" width="828" height="{height - 72}" rx="28" fill="#ffffff" stroke="#e2e8f0" stroke-width="2"/>'
            f'<text x="70" y="96" font-size="30" font-weight="700" fill="#0f172a" font-family="Arial">INVOICE</text>'
            f'<text x="70" y="145" font-size="18" fill="#64748b" font-family="Arial">Supplier</text>'
            f'<text x="70" y="174" font-size="28" font-weight="700" fill="#111827" font-family="Arial">{supplier_name}</text>'
            f'<text x="540" y="145" font-size="18" fill="#64748b" font-family="Arial">Invoice Number</text>'
            f'<text x="540" y="174" font-size="24" font-weight="700" fill="#111827" font-family="Arial">{invoice_number}</text>'
            f'<text x="70" y="220" font-size="18" fill="#64748b" font-family="Arial">Invoice Date</text>'
            f'<text x="70" y="248" font-size="22" font-weight="700" fill="#111827" font-family="Arial">{invoice_date}</text>'
            f'<text x="300" y="220" font-size="18" fill="#64748b" font-family="Arial">Upload Date</text>'
            f'<text x="300" y="248" font-size="22" font-weight="700" fill="#111827" font-family="Arial">{upload_date}</text>'
            f'<rect x="560" y="204" width="240" height="62" rx="18" fill="#fff7ed"/>'
            f'<text x="585" y="229" font-size="18" fill="#9a3412" font-family="Arial">Total Amount</text>'
            f'<text x="585" y="255" font-size="28" font-weight="700" fill="#f97316" font-family="Arial">{total_amount}</text>'
            f'<rect x="60" y="290" width="780" height="{items_height}" rx="22" fill="#ffffff" stroke="#e2e8f0" stroke-width="2"/>'
            f'<text x="80" y="330" font-size="18" fill="#64748b" font-family="Arial">PRODUCT</text>'
            f'<text x="470" y="330" font-size="18" fill="#64748b" font-family="Arial">QTY</text>'
            f'<text x="590" y="330" font-size="18" fill="#64748b" font-family="Arial">PRICE</text>'
            f'<text x="730" y="330" font-size="18" fill="#64748b" font-family="Arial">TOTAL</text>'
            f'<line x1="70" y1="346" x2="830" y2="346" stroke="#e2e8f0" stroke-width="2" />'
            f'{rows_svg}'
            f'</svg>'
        )

    def _build_home_revenue_chart(self, daily_records: list[dict], *, period: str) -> list[ChartPointResponse]:
        if period == 'monthly':
            return self._build_monthly_revenue_chart(daily_records)
        return self._build_weekly_revenue_chart(daily_records)

    def _build_monthly_revenue_chart(self, daily_records: list[dict]) -> list[ChartPointResponse]:
        today = datetime.now(UTC).date()
        start_date = today - timedelta(days=29)
        by_day: dict[str, float] = {}
        for item in self.serialize_list(daily_records):
            key = item['business_date']
            by_day[key] = by_day.get(key, 0.0) + float(item['total_revenue'])

        points: list[ChartPointResponse] = []
        for index in range(4):
            segment_start = start_date + timedelta(days=index * 7)
            segment_end = segment_start + timedelta(days=6)
            total = 0.0
            current = segment_start
            while current <= segment_end and current <= today:
                total += by_day.get(current.isoformat(), 0.0)
                current += timedelta(days=1)
            points.append(ChartPointResponse(label=f'W{index + 1}', value=round(total, 2)))
        return points

    def _filter_home_daily_records(self, daily_records: list[dict], *, period: str, from_date: date | None = None, to_date: date | None = None) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date)
        records = self.serialize_list(daily_records)
        if start_date is None and end_date is None:
            return records
        return [
            item for item in records
            if (start_date is None or self._safe_parse_date(item.get('business_date')) >= start_date)
            and (end_date is None or self._safe_parse_date(item.get('business_date')) <= end_date)
        ]

    def _filter_home_expenses(self, expenses: list[dict], *, period: str, from_date: date | None = None, to_date: date | None = None) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date)
        records = self.serialize_list(expenses)
        if start_date is None and end_date is None:
            return records
        filtered: list[dict] = []
        for item in records:
            expense_date = self._safe_parse_date(item.get('expense_date'))
            if start_date is not None and expense_date < start_date:
                continue
            if end_date is not None and expense_date > end_date:
                continue
            filtered.append(item)
        return filtered

    def _filter_home_cash_deposits(self, deposits: list[dict], *, period: str, from_date: date | None = None, to_date: date | None = None) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date)
        records = self.serialize_list(deposits)
        if start_date is None and end_date is None:
            return records
        filtered: list[dict] = []
        for item in records:
            deposit_date = self._safe_parse_date(item.get('deposit_date'))
            if start_date is not None and deposit_date < start_date:
                continue
            if end_date is not None and deposit_date > end_date:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _resolve_home_date_range(period: str, *, from_date: date | None = None, to_date: date | None = None) -> tuple[date | None, date | None]:
        if from_date is not None or to_date is not None:
            return from_date, to_date
        today = datetime.now(UTC).date()
        if period == 'weekly':
            return today - timedelta(days=6), today
        if period == 'monthly':
            return today - timedelta(days=29), today
        return None, None

    @staticmethod
    def _safe_parse_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value is None:
            return datetime.now(UTC).date()
        candidate = str(value).replace('Z', '+00:00')
        try:
            if 'T' in candidate:
                return datetime.fromisoformat(candidate).date()
            return date.fromisoformat(candidate)
        except ValueError:
            return datetime.now(UTC).date()

    @staticmethod
    def _analytics_filter_label(period: str) -> str:
        return 'Monthly' if period == 'monthly' else 'Weekly'

    @staticmethod
    def _analytics_current_revenue_label(period: str) -> str:
        return 'This Month Revenue' if period == 'monthly' else 'This Week Revenue'

    @staticmethod
    def _analytics_previous_revenue_label(period: str) -> str:
        return 'Last Month Revenue' if period == 'monthly' else 'Last Week Revenue'

    @staticmethod
    def _build_simple_pdf(content: str) -> bytes:
        safe_content = content.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        lines = safe_content.split('\n')
        y_position = 780
        content_lines = ['BT', '/F1 12 Tf', '50 800 Td']
        first = True
        for line in lines:
            if not first:
                y_position -= 16
                content_lines.append(f'50 {y_position} Td')
            content_lines.append(f'({line}) Tj')
            first = False
        content_lines.append('ET')
        stream = '\n'.join(content_lines).encode('utf-8')
        return RestaurantOperationsService._build_pdf_document(stream)

    @staticmethod
    def _build_pdf_document(stream: bytes) -> bytes:
        objects: list[bytes] = [
            b'1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n',
            b'2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n',
            b'3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>endobj\n',
            b'4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n',
            b'5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>endobj\n',
            b'6 0 obj<< /Length ' + str(len(stream)).encode('utf-8') + b' >>stream\n' + stream + b'\nendstream endobj\n',
        ]

        output = bytearray(b'%PDF-1.4\n')
        offsets = [0]
        for obj in objects:
            offsets.append(len(output))
            output.extend(obj)

        xref_start = len(output)
        output.extend(f'xref\n0 {len(offsets)}\n'.encode('utf-8'))
        output.extend(b'0000000000 65535 f \n')
        for offset in offsets[1:]:
            output.extend(f'{offset:010d} 00000 n \n'.encode('utf-8'))
        output.extend(f'trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF'.encode('utf-8'))
        return bytes(output)

    @staticmethod
    def _format_human_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            normalized = str(value).replace("Z", "+00:00")
            if "T" in normalized or "+" in normalized:
                parsed = datetime.fromisoformat(normalized)
                return parsed.strftime("%b %d, %Y")
            parsed_date = datetime.fromisoformat(normalized).date()
            return parsed_date.strftime("%b %d, %Y")
        except ValueError:
            return value

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

    @staticmethod
    def _resolve_date_range(*, view: str, anchor_date: date) -> tuple[date | None, date | None]:
        if view == "week":
            start_date = anchor_date - timedelta(days=anchor_date.weekday())
            return start_date, start_date + timedelta(days=6)
        if view == "month":
            start_date = anchor_date.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            return start_date, next_month - timedelta(days=1)
        return None, None

    def _build_daily_data_buckets(self, records: list[dict[str, Any]], expenses: list[dict[str, Any]], documents: list[dict[str, Any]], *, anchor_date: date) -> list[dict[str, Any]]:
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

        for document in documents:
            invoice_date = str(document.get("invoice_date") or "")
            if not invoice_date:
                continue
            group = expense_groups.setdefault(invoice_date, {"uploaded_invoice": {"count": 0, "total": 0.0, "endpoint": None}, "manual_expense": {"count": 0, "total": 0.0, "endpoint": "/api/v1/restaurant/expenses"}})
            group["uploaded_invoice"]["count"] += 1
            group["uploaded_invoice"]["total"] += float(document.get("total_amount", 0))
            group["uploaded_invoice"]["endpoint"] = f"/api/v1/restaurant/daily-data/by-date?business_date={invoice_date}"
            bucket = buckets.setdefault(
                invoice_date,
                {
                    "id": f"date:{invoice_date}",
                    "business_date": invoice_date,
                    "total_revenue": 0.0,
                    "total_expenses": 0.0,
                    "total_covers": 0,
                    "avg_revenue_per_cover": 0.0,
                    "record_id": None,
                    "created_at": document.get("created_at", datetime.now(UTC).isoformat()),
                    "data_sources": [],
                },
            )
            bucket["total_expenses"] = round(bucket.get("total_expenses", 0.0) + float(document.get("total_amount", 0)), 2)

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
        invoice_date = serialized.get("invoice_date")
        status = str(serialized.get("status", "pending_review"))
        return DocumentListItemResponse(
            id=serialized["id"],
            supplier_name=serialized["supplier_name"],
            invoice_number=serialized.get("invoice_number"),
            invoice_date=invoice_date,
            invoice_date_formatted=self._format_human_date(invoice_date),
            upload_date=serialized["upload_date"],
            total_amount=float(serialized.get("total_amount", 0.0)),
            status=status,
            line_item_count=len(serialized.get("line_items", [])),
            created_by_user_id=serialized.get("created_by_user_id"),
            last_edited_by_user_id=serialized.get("last_edited_by_user_id"),
            confirmed_at=serialized.get("confirmed_at"),
        )

    def _to_document_confirm_save(self, document: dict) -> DocumentConfirmSaveResponse:
        serialized = self.serialize(document)
        return DocumentConfirmSaveResponse(
            id=serialized["id"],
            supplier_name=serialized["supplier_name"],
            invoice_number=serialized.get("invoice_number"),
            invoice_date=serialized.get("invoice_date"),
            total_amount=float(serialized.get("total_amount", 0.0)),
            line_items=[DocumentLineItemSchema(**item) for item in serialized.get("line_items", [])],
            source_file_name=serialized["source_file_name"],
            ai_provider=serialized["ai_provider"],
            ai_summary=serialized.get("ai_summary", ""),
            upload_date=serialized["upload_date"],
            status=str(serialized.get("status", "pending_review")),
            created_by_user_id=serialized.get("created_by_user_id"),
            last_edited_by_user_id=serialized.get("last_edited_by_user_id"),
            confirmed_by_user_id=serialized.get("confirmed_by_user_id"),
            confirmed_at=serialized.get("confirmed_at"),
        )

    def _to_document_detail(self, document: dict) -> DocumentDetailResponse:
        serialized = self.serialize(document)
        invoice_date = serialized.get("invoice_date")
        upload_date = serialized.get("upload_date")
        status = str(serialized.get("status", "pending_review"))
        return DocumentDetailResponse(
            id=serialized["id"],
            supplier_name=serialized["supplier_name"],
            invoice_number=serialized.get("invoice_number"),
            invoice_number_display=f"Inv #{serialized.get('invoice_number')}" if serialized.get("invoice_number") else None,
            invoice_date=invoice_date,
            invoice_date_formatted=self._format_human_date(invoice_date),
            upload_date=upload_date,
            upload_date_formatted=self._format_human_date(upload_date),
            total_amount=float(serialized.get("total_amount", 0.0)),
            status=status,
            ai_provider=serialized["ai_provider"],
            ai_summary=serialized.get("ai_summary", ""),
            line_items=[DocumentLineItemSchema(**item) for item in serialized.get("line_items", [])],
            download_endpoint=f"/api/v1/restaurant/documents/{serialized['id']}/download",
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    def _to_expense_response(self, expense: dict) -> ExpenseResponse:
        serialized = self.serialize(expense)
        amount = float(serialized["amount"])
        category = str(serialized.get("category") or "Expense")
        subtitle = serialized.get("notes") or category
        return ExpenseResponse(
            id=serialized["id"],
            category=category,
            amount=amount,
            amount_formatted=self._format_currency(amount),
            expense_date=serialized["expense_date"],
            expense_date_formatted=self._format_human_date(serialized.get("expense_date")),
            notes=serialized.get("notes"),
            subtitle=subtitle,
            created_at=serialized["created_at"],
        )

    def _to_cash_deposit_response(self, deposit: dict) -> CashDepositResponse:
        serialized = self.serialize(deposit)
        amount = float(serialized["amount"])
        title = serialized.get("notes") or serialized.get("deposit_type")
        return CashDepositResponse(
            id=serialized["id"],
            deposit_date=serialized["deposit_date"],
            deposit_date_formatted=self._format_human_date(serialized.get("deposit_date")),
            amount=amount,
            amount_formatted=self._format_currency(amount),
            deposit_type=serialized["deposit_type"],
            display_title=title,
            display_subtitle=self._format_human_date(serialized.get("deposit_date")),
            notes=serialized.get("notes"),
            created_at=serialized["created_at"],
        )

    def _to_daily_data_response(self, record: dict) -> DailyDataResponse:
        serialized = self.serialize(record)
        lunch_covers = int(serialized.get("lunch_covers", 0))
        dinner_covers = int(serialized.get("dinner_covers", 0))
        total_covers = lunch_covers + dinner_covers
        if serialized.get("method") == "method_2":
            revenue_breakdown = [
                DailyDataRevenueBreakdownItemResponse(label="POS Payments", amount=float(serialized.get("pos_payments", 0)), amount_formatted=self._format_currency(float(serialized.get("pos_payments", 0)))),
                DailyDataRevenueBreakdownItemResponse(label="Cash Payments", amount=float(serialized.get("cash_payments", 0)), amount_formatted=self._format_currency(float(serialized.get("cash_payments", 0)))),
                DailyDataRevenueBreakdownItemResponse(label="Bank Transfer", amount=float(serialized.get("bank_transfer_payments", 0)), amount_formatted=self._format_currency(float(serialized.get("bank_transfer_payments", 0)))),
            ]
        else:
            revenue_breakdown = [
                DailyDataRevenueBreakdownItemResponse(label="POS Payments", amount=float(serialized.get("pos_payments", 0)), amount_formatted=self._format_currency(float(serialized.get("pos_payments", 0)))),
                DailyDataRevenueBreakdownItemResponse(label="Cash In", amount=float(serialized.get("cash_in", 0)), amount_formatted=self._format_currency(float(serialized.get("cash_in", 0)))),
            ]
        return DailyDataResponse(
            id=serialized["id"],
            business_date=serialized["business_date"],
            method=serialized["method"],
            total_revenue=serialized["total_revenue"],
            total_expenses=serialized["total_expenses"],
            profit=serialized["profit"],
            net_profit_formatted=self._format_currency(float(serialized["profit"])),
            total_revenue_formatted=self._format_currency(float(serialized["total_revenue"])),
            total_expenses_formatted=self._format_currency(float(serialized["total_expenses"])),
            lunch_covers=lunch_covers,
            dinner_covers=dinner_covers,
            total_covers=total_covers,
            avg_revenue_per_cover=serialized.get("avg_revenue_per_cover", 0.0),
            revenue_breakdown=revenue_breakdown,
            covers_summary=DailyDataCoversSummaryResponse(lunch=lunch_covers, dinner=dinner_covers, total=total_covers),
            register_summary=DailyDataRegisterSummaryResponse(
                opening_cash=float(serialized.get("opening_cash", 0)),
                opening_cash_formatted=self._format_currency(float(serialized.get("opening_cash", 0))),
                closing_cash=float(serialized.get("closing_cash", 0)),
                closing_cash_formatted=self._format_currency(float(serialized.get("closing_cash", 0))),
            ),
            edit_endpoint=f"/api/v1/restaurant/manual-entry/{serialized['id']}",
            export_endpoint=f"/api/v1/restaurant/daily-data/{serialized['id']}",
            created_at=serialized["created_at"],
        )

    def _to_daily_data_bucket_item(self, bucket: dict[str, Any], *, anchor_date: date | None = None, active_view: str = "date") -> DailyDataListItemResponse:
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
                view_endpoint=(
                    f"/api/v1/restaurant/daily-data/by-date?business_date={bucket['business_date']}"
                    if active_view == "date"
                    else (f"/api/v1/restaurant/daily-data/by-week?reference_date={anchor.isoformat()}" if active_view == "week" else f"/api/v1/restaurant/daily-data/by-month?reference_date={anchor.isoformat()}")
                ),
                delete_endpoint=f"/api/v1/restaurant/daily-data/{record_id}" if record_id else None,
            ),
            created_at=str(bucket.get("created_at")),
        )

    def _to_daily_data_detail(
        self,
        bucket: dict[str, Any],
        *,
        invoices: list[dict[str, Any]],
        anchor_date: date | None = None,
        active_view: str = "date",
        reference_date: date | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> DailyDataDetailResponse:
        list_item = self._to_daily_data_bucket_item(bucket, anchor_date=anchor_date, active_view=active_view)
        revenue_label = "Revenue" if active_view == "date" else ("Week Revenue" if active_view == "week" else "Month Revenue")
        covers_label = "Covers" if active_view == "date" else ("Week Covers" if active_view == "week" else "Month Covers")
        avg_label = "AVG" if active_view == "date" else ("Week AVG" if active_view == "week" else "Month AVG")
        return DailyDataDetailResponse(
            active_view=active_view,
            reference_date=reference_date.isoformat() if reference_date else None,
            period_start=period_start.isoformat() if period_start else None,
            period_end=period_end.isoformat() if period_end else None,
            business_date=list_item.business_date,
            business_date_formatted=list_item.business_date_formatted,
            day_label=list_item.day_label,
            summary_cards=[
                DailyDataSummaryCardResponse(label=revenue_label, value=list_item.total_revenue, value_prefix="EUR", value_formatted=list_item.total_revenue_formatted, icon_key="revenue"),
                DailyDataSummaryCardResponse(label=covers_label, value=float(list_item.total_covers), value_formatted=str(list_item.total_covers), icon_key=None),
                DailyDataSummaryCardResponse(label=avg_label, value=list_item.avg_revenue_per_cover, value_prefix="USD", value_formatted=list_item.avg_revenue_per_cover_formatted, icon_key=None),
            ],
            total_revenue=list_item.total_revenue,
            total_revenue_formatted=list_item.total_revenue_formatted,
            total_expenses=list_item.total_expenses,
            total_expenses_formatted=list_item.total_expenses_formatted,
            total_covers=list_item.total_covers,
            avg_revenue_per_cover=list_item.avg_revenue_per_cover,
            avg_revenue_per_cover_formatted=list_item.avg_revenue_per_cover_formatted,
            invoices=[
                DailyDataDocumentItemResponse(
                    id=item["id"],
                    supplier_name=item["supplier_name"],
                    invoice_number=item.get("invoice_number"),
                    invoice_date=item.get("invoice_date"),
                    total_amount=float(item.get("total_amount", 0)),
                    status=item.get("status", "processed"),
                    source_file_name=item.get("source_file_name", ""),
                    upload_date=item.get("upload_date", ""),
                    confirmed_at=item.get("confirmed_at"),
                )
                for item in invoices
            ],
            invoice_count=len(invoices),
            data_sources=list_item.data_sources,
        )

    def _to_inventory_item_response(self, item: dict) -> InventoryItemResponse:
        serialized = self.serialize(item)
        stock_quantity = float(serialized["stock_quantity"])
        purchase_date = serialized.get("purchase_date")
        return InventoryItemResponse(
            id=serialized["id"],
            product_name=serialized["product_name"],
            category=serialized["category"],
            stock_quantity=stock_quantity,
            stock_quantity_label=f"{int(stock_quantity) if stock_quantity.is_integer() else stock_quantity} {serialized['unit_type']}",
            unit_type=serialized["unit_type"],
            supplier_name=serialized.get("supplier_name"),
            supplier_subtitle=serialized.get("supplier_name"),
            unit_price=serialized["unit_price"],
            alert_threshold=serialized["alert_threshold"],
            stock_status=serialized["stock_status"],
            stock_status_label=serialized["stock_status"].replace("_", " ").upper(),
            purchase_date=purchase_date,
            last_purchase_label=datetime.fromisoformat(purchase_date).strftime("%d %b") if purchase_date else None,
            actions=InventoryListItemActionResponse(view_endpoint=f"/api/v1/restaurant/inventory/{serialized['id']}", stock_update_endpoint=f"/api/v1/restaurant/inventory/{serialized['id']}/stock-update"),
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    def _to_inventory_detail_response(self, item: dict) -> InventoryDetailResponse:
        base_item = self._to_inventory_item_response(item)
        serialized = self.serialize(item)
        unit_type = serialized.get("unit_type", "unit")
        current_stock = float(serialized.get("stock_quantity", 0))
        purchase_date = serialized.get("purchase_date")
        return InventoryDetailResponse(
            **base_item.model_dump(),
            current_stock_value=current_stock,
            current_stock_display=f"{int(current_stock) if current_stock.is_integer() else current_stock} {unit_type}",
            stock_update_endpoint=f"/api/v1/restaurant/inventory/{serialized['id']}/stock-update",
            supplier_card=InventorySupplierCardResponse(
                supplier_name=serialized.get("supplier_name"),
                last_purchase=datetime.fromisoformat(purchase_date).strftime("%b %d, %Y") if purchase_date else None,
                price_per_unit=f"${float(serialized.get('unit_price', 0)):.2f} / {unit_type}",
            ),
            edit_endpoint=f"/api/v1/restaurant/inventory/{serialized['id']}",
            delete_endpoint=f"/api/v1/restaurant/inventory/{serialized['id']}",
            history=[InventoryHistoryItemResponse(**entry) for entry in serialized.get("history", [])],
        )

    def _build_chat_insight_message(self, metrics_context: dict[str, Any]) -> str:
        revenue_total = float(metrics_context.get("revenue_total", 0))
        expense_total = float(metrics_context.get("expenses_total", 0))
        if revenue_total > 0 and expense_total >= 0:
            margin = max(revenue_total - expense_total, 0)
            if margin > 0:
                lift_percent = min(25, max(5, int(round((margin / max(revenue_total, 1)) * 15))))
                return f"Your dinner revenue increased by {lift_percent}% this week."
        return "Your revenue is trending upward compared to last week."

    def _to_chat_message_response(self, item: dict) -> ChatMessageResponse:
        serialized = self.serialize(item)
        role = serialized["role"]
        sender_label = "YOU" if role == "user" else ("AI Insight" if role == "insight" else "Risto AI")
        variant = "user" if role == "user" else ("insight" if role == "insight" else "assistant")
        return ChatMessageResponse(
            id=serialized["id"],
            role=role,
            message=serialized["message"],
            created_at=serialized["created_at"],
            sender_label=sender_label,
            variant=variant,
            attachment_name=serialized.get("attachment_name"),
            attachment_source=serialized.get("attachment_source"),
            attachment_summary=serialized.get("attachment_summary"),
        )

