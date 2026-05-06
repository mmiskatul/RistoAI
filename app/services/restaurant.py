from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import UTC, date, datetime, timedelta
from html import escape
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from bson import ObjectId
from fastapi import UploadFile

from app.core.security import password_manager
from app.core.exceptions import ConflictException, ValidationException
from app.repositories.restaurant_ops import (
    RestaurantBankAccountRepository,
    RestaurantCashDepositRepository,
    RestaurantChatRepository,
    RestaurantDailyRecordRepository,
    RestaurantRecordRepository,
    RestaurantWeeklyRecordRepository,
    RestaurantMonthlyRecordRepository,
    RestaurantDocumentRepository,
    RestaurantExpenseRepository,
    RestaurantFinanceTransactionRepository,
    RestaurantInsightRepository,
    RestaurantInventoryCategoryRepository,
    RestaurantInventoryRepository,
    RestaurantInventorySupplierRepository,
    ScopedRepository,
)
from app.repositories.onboarding_profile import OnboardingProfileRepository
from app.repositories.user import UserRepository
from app.schemas.restaurant import (
    ActivityItemResponse,
    AnalyticsActivityCostResponse,
    AnalyticsCostBreakdownResponse,
    AnalyticsCoversActivityResponse,
    AnalyticsOverviewResponse,
    AnalyticsInsightBannerResponse,
    AnalyticsMetricTileResponse,
    AnalyticsMetricTilesResponse,
    AnalyticsRevenueComparisonResponse,
    AnalyticsRevenueTrendResponse,
    AnalyticsSummaryStatsResponse,
    AnalyticsSupplierAlertsResponse,
    AnalyticsSummaryStatResponse,
    AnalyticsComparisonRowResponse,
    AnalyticsSupplierAlertResponse,
    BankAccountCreateRequest,
    BankAccountListResponse,
    BankAccountResponse,
    BankAccountUpdateRequest,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashDepositUpdateRequest,
    CashManagementItemResponse,
    CashManagementSummaryResponse,
    CashOverviewPeriodsResponse,
    CashPeriodOverviewResponse,
    CashPeriodStatusResponse,
    CashPeriodSummaryResponse,
    ChartPointResponse,
    ChatAttachmentOptionResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
    ChatMessageResponse,
    ChatMessageUpdateRequest,
    ChatQuickPromptResponse,
    ChatRealtimeConfigResponse,
    DailyDataCollectionResponse,
    DailyDataCreateRequest,
    DailyDataDetailResponse,
    DailyDataDocumentItemResponse,
    DailyDataFormFieldResponse,
    DailyDataManualEntryResponse,
    DailyDataManualMethodResponse,
    DailyDataEntrySourceResponse,
    DailyDataListItemResponse,
    DailyDataListResponse,
    DailyDataResponse,
    DailyDataSectionFieldResponse,
    DailyDataSectionResponse,
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
    ExpensePeriodResponse,
    ExpenseResponse,
    InsightActionResponse,
    InsightDetailResponse,
    InsightSummaryResponse,
    InventoryCategoryCreateRequest,
    InventoryCategoryListResponse,
    InventoryCategoryResponse,
    InventoryCreateRequest,
    InventoryDetailResponse,
    InventoryHistoryItemResponse,
    InventoryItemResponse,
    InventoryListResponse,
    InventoryListItemActionResponse,
    InventoryStockUpdateRequest,
    InventorySupplierCardResponse,
    InventorySupplierCreateRequest,
    InventorySupplierListResponse,
    InventorySupplierResponse,
    InventoryUpdateRequest,
    InventoryValueResponse,
    DailyDataRevenueBreakdownItemResponse,
    DailyDataCoversSummaryResponse,
    DailyDataRegisterSummaryResponse,
    MetricCardResponse,
    RestaurantChangePasswordRequest,
    RestaurantHomeCashManagementResponse,
    RestaurantHomeInsightResponse,
    RestaurantHomeMetricsResponse,
    RestaurantHomePeriodResponse,
    RestaurantHomeRecentActivityResponse,
    RestaurantHomeRevenueResponse,
    RestaurantHomeResponse,
    RestaurantHomeVatBalanceResponse,
    RestaurantNotificationFeedResponse,
    RestaurantNotificationSettingsResponse,
    RestaurantNotificationSettingsUpdateRequest,
    PushDeviceRegistrationRequest,
    PushDeviceUnregisterRequest,
    RestaurantProfileResponse,
    RestaurantProfileUpdateRequest,
    RestaurantSettingsSubscriptionResponse,
    SettingsActionItemResponse,
    SettingsLanguageOptionResponse,
    QuickActionResponse,
    VatOverviewResponse,
)
from app.schemas.common import MessageResponse
from app.services.base import BaseService
from app.services.image_storage import ImageStorageService, UploadedImage
from app.services.openai_ops import OpenAIOperationsService
from app.services.restaurant_cash import build_aggregate_snapshot, calculate_cash_ledger
from app.utils.pagination import build_pagination_meta

logger = logging.getLogger(__name__)


class RestaurantOperationsService(BaseService):
    VAT_RATE = 0.1
    SUPPORTED_DOCUMENT_TYPES = {"expense", "cash", "revenue", "profit", "unknown"}
    CASH_TRANSACTION_TYPES = {
        "bank_deposit",
        "cash_deposit",
        "pos_payment",
        "cash_in",
        "bank_transfer_payment",
        "cash_withdrawal",
        "cash_out",
        "cash_expense",
    }
    CASH_OUTFLOW_TRANSACTION_TYPES = {"cash_withdrawal", "cash_out", "cash_expense"}

    @staticmethod
    def _resolve_chat_language(current_user: dict, requested_language: str | None = None) -> str:
        candidate = str(requested_language or current_user.get("preferred_language") or "en").strip().lower()
        return "it" if candidate.startswith("it") else "en"

    @staticmethod
    def _build_chat_welcome_message(language: str) -> str:
        if language == "it":
            return "Ciao! Posso aiutarti ad analizzare i dati del tuo ristorante. Cosa vuoi sapere?"
        return "Hello! I can help you analyze your restaurant data. What would you like to know?"

    @staticmethod
    def _build_fallback_restaurant_insight(context: dict[str, float | int], *, language: str) -> dict[str, Any]:
        percent = abs(float(context["food_cost_change_percent"]))
        increased = float(context["food_cost_change_percent"]) >= 0
        if language == "it":
            return {
                "title": "Costo del cibo in aumento" if increased else "Costo del cibo migliorato",
                "summary": (
                    f"Il costo del cibo e cambiato del {percent:.1f}% rispetto alla settimana precedente. "
                    "Controlla i prezzi dei fornitori e gli sprechi in preparazione."
                ),
                "priority": "high" if percent >= 10 else "medium",
                "metric_value": f"{percent:.0f}%",
                "metric_caption": "variazione questa settimana",
                "root_causes": [
                    "Aumento dei prezzi dei fornitori sui prodotti principali",
                    "Maggiore utilizzo degli ingredienti nei piatti principali",
                    "Aumento degli sprechi nella preparazione",
                ],
                "recommended_actions": [
                    {"title": "Controlla i prezzi dei fornitori", "description": "Confronta i principali fornitori e rinegozia questa settimana."},
                    {"title": "Ottimizza le porzioni", "description": "Verifica guarnizioni e pesi di preparazione sui piatti piu lenti."},
                    {"title": "Monitora gli sprechi", "description": "Esegui una checklist giornaliera degli sprechi per i prossimi 7 giorni."},
                ],
            }
        return {
            "title": "Food Cost Increased" if increased else "Food Cost Improved",
            "summary": f"Food cost changed by {percent:.1f}% compared with the previous week. Review supplier pricing and prep waste.",
            "priority": "high" if percent >= 10 else "medium",
            "metric_value": f"{percent:.0f}%",
            "metric_caption": "change this week",
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
        }

    @staticmethod
    def _build_localized_text(*, en: str, it: str) -> dict[str, str]:
        return {"en": en, "it": it}

    @staticmethod
    def _build_localized_list(*, en: list[str], it: list[str]) -> dict[str, list[str]]:
        return {"en": en, "it": it}

    @staticmethod
    def _build_localized_actions(*, en: list[dict[str, str]], it: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
        return {"en": en, "it": it}

    @staticmethod
    def _resolve_localized_text(
        translations: Any,
        *,
        language: str,
        fallback: str = "",
    ) -> str:
        if isinstance(translations, dict):
            value = translations.get("it" if language == "it" else "en")
            if value:
                return str(value)
            alternate = translations.get("en" if language == "it" else "it")
            if alternate:
                return str(alternate)
        return fallback

    @staticmethod
    def _resolve_localized_list(
        translations: Any,
        *,
        language: str,
        fallback: list[str] | None = None,
    ) -> list[str]:
        if isinstance(translations, dict):
            value = translations.get("it" if language == "it" else "en")
            if isinstance(value, list) and value:
                return [str(item) for item in value]
            alternate = translations.get("en" if language == "it" else "it")
            if isinstance(alternate, list) and alternate:
                return [str(item) for item in alternate]
        return fallback or []

    @staticmethod
    def _resolve_localized_actions(
        translations: Any,
        *,
        language: str,
        fallback: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        if isinstance(translations, dict):
            value = translations.get("it" if language == "it" else "en")
            if isinstance(value, list) and value:
                return [
                    {
                        "title": str(item.get("title") or ""),
                        "description": str(item.get("description") or ""),
                    }
                    for item in value
                    if isinstance(item, dict)
                ]
            alternate = translations.get("en" if language == "it" else "it")
            if isinstance(alternate, list) and alternate:
                return [
                    {
                        "title": str(item.get("title") or ""),
                        "description": str(item.get("description") or ""),
                    }
                    for item in alternate
                    if isinstance(item, dict)
                ]
        return fallback or []

    def __init__(
        self,
        user_repository: UserRepository,
        document_repository: RestaurantDocumentRepository,
        expense_repository: RestaurantExpenseRepository,
        cash_repository: RestaurantCashDepositRepository,
        bank_account_repository: RestaurantBankAccountRepository,
        daily_record_repository: RestaurantDailyRecordRepository,
        record_repository: RestaurantRecordRepository,
        weekly_record_repository: RestaurantWeeklyRecordRepository,
        monthly_record_repository: RestaurantMonthlyRecordRepository,
        finance_transaction_repository: RestaurantFinanceTransactionRepository,
        inventory_repository: RestaurantInventoryRepository,
        inventory_category_repository: RestaurantInventoryCategoryRepository,
        inventory_supplier_repository: RestaurantInventorySupplierRepository,
        chat_repository: RestaurantChatRepository,
        insight_repository: RestaurantInsightRepository,
        openai_service: OpenAIOperationsService,
        onboarding_repository: OnboardingProfileRepository | None = None,
        image_storage_service: ImageStorageService | None = None,
    ) -> None:
        self.user_repository = user_repository
        self.document_repository = document_repository
        self.expense_repository = expense_repository
        self.cash_repository = cash_repository
        self.bank_account_repository = bank_account_repository
        self.daily_record_repository = daily_record_repository
        self.record_repository = record_repository
        self.weekly_record_repository = weekly_record_repository
        self.monthly_record_repository = monthly_record_repository
        self.finance_transaction_repository = finance_transaction_repository
        self.inventory_repository = inventory_repository
        self.inventory_category_repository = inventory_category_repository
        self.inventory_supplier_repository = inventory_supplier_repository
        self.chat_repository = chat_repository
        self.insight_repository = insight_repository
        self.onboarding_repository = onboarding_repository
        self.openai_service = openai_service
        self.image_storage_service = image_storage_service

    async def _replace_transactions_for_source(
        self,
        *,
        scope_id: str,
        source_kind: str,
        source_id: str,
        transactions: list[dict[str, Any]],
    ) -> None:
        now = datetime.now(UTC)
        normalized = []
        for item in transactions:
            normalized.append(
                {
                    "tenant_id": scope_id,
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "created_at": now,
                    "updated_at": now,
                    **item,
                }
            )
        await self.finance_transaction_repository.replace_for_source(
            scope_id=scope_id,
            source_kind=source_kind,
            source_id=source_id,
            transactions=normalized,
        )

    async def _delete_transactions_for_source(self, *, scope_id: str, source_kind: str, source_id: str) -> None:
        await self.finance_transaction_repository.delete_for_source(scope_id=scope_id, source_kind=source_kind, source_id=source_id)

    def _build_document_transactions(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        if document.get("status") != "processed" or not document.get("invoice_date"):
            return []
        business_date = str(document.get("invoice_date"))
        document_type = str(document.get("document_type", "expense")).lower()
        amount_field = {
            "expense": "expense_amount",
            "cash": "cash_amount",
            "revenue": "revenue_amount",
            "profit": "profit_amount",
        }.get(document_type, "total_amount")
        amount = self._safe_float(document.get(amount_field), default=self._safe_float(document.get("total_amount")))
        if amount <= 0:
            return []
        transaction_type = {
            "expense": "expense",
            "cash": "cash_collection",
            "revenue": "bank_collection",
            "profit": "profit_adjustment",
        }.get(document_type, "document")
        payment_channel = "cash" if document_type == "cash" else "document"
        if document_type == "revenue":
            payment_channel = "bank_transfer"
        return [
            {
                "business_date": business_date,
                "transaction_type": transaction_type,
                "payment_channel": payment_channel,
                "amount": amount,
                "currency": str(document.get("currency") or "EUR"),
                "reference_label": str(document.get("counterparty_name") or document.get("supplier_name") or document.get("source_file_name") or "Document"),
                "metadata": {
                    "document_type": document_type,
                    "document_id": document.get("id"),
                },
            }
        ]

    def _build_expense_transactions(self, expense: dict[str, Any]) -> list[dict[str, Any]]:
        expense_date = expense.get("expense_date")
        if not expense_date:
            return []
        payment_channel = str(expense.get("section") or "cash").lower()
        business_date = str(expense_date).replace("Z", "+00:00")[:10]
        return [
            {
                "business_date": business_date,
                "transaction_type": "expense",
                "payment_channel": payment_channel,
                "amount": self._safe_float(expense.get("amount")),
                "currency": "EUR",
                "reference_label": str(expense.get("category") or "Expense"),
                "metadata": {
                    "category": expense.get("category"),
                    "notes": expense.get("notes"),
                    "ledger_group": "expense",
                    "affects_revenue": False,
                    "affects_cash": payment_channel == "cash",
                    "affects_profit": True,
                },
            }
        ]

    async def _upsert_inventory_linked_expense(
        self,
        *,
        scope_id: str,
        current_user: dict,
        inventory_item_id: str,
        product_name: str,
        category: str,
        stock_quantity: float,
        unit_price: float,
        purchase_date: date | None,
        section: str = "cash",
    ) -> dict[str, Any] | None:
        if purchase_date is None:
            return None

        amount = round(max(stock_quantity, 0) * max(unit_price, 0), 2)
        existing = await self.expense_repository.find_inventory_linked_expense(
            scope_id=scope_id,
            inventory_item_id=inventory_item_id,
        )
        payload = {
            "category": category,
            "amount": amount,
            "expense_date": datetime.combine(purchase_date, datetime.min.time(), tzinfo=UTC),
            "section": section,
            "notes": product_name,
            "source_kind": "inventory",
            "source_id": inventory_item_id,
            "source_inventory_item_id": inventory_item_id,
        }
        if existing is None:
            created = await self.expense_repository.create(
                {
                    "tenant_id": scope_id,
                    **payload,
                    "created_by_user_id": str(current_user["_id"]),
                }
            )
            serialized_created = self.serialize(created)
            await self._replace_transactions_for_source(
                scope_id=scope_id,
                source_kind="expense",
                source_id=serialized_created["id"],
                transactions=self._build_expense_transactions(serialized_created),
            )
            return created

        updated = await self.expense_repository.update(existing["_id"], payload)
        serialized_updated = self.serialize(updated)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="expense",
            source_id=serialized_updated["id"],
            transactions=self._build_expense_transactions(serialized_updated),
        )
        return updated

    async def _delete_inventory_linked_expense(self, *, scope_id: str, inventory_item_id: str) -> date | None:
        existing = await self.expense_repository.find_inventory_linked_expense(
            scope_id=scope_id,
            inventory_item_id=inventory_item_id,
        )
        if existing is None:
            return None
        existing_expense_date = self._safe_parse_date(existing.get("expense_date"))
        await self._delete_transactions_for_source(
            scope_id=scope_id,
            source_kind="expense",
            source_id=str(existing["_id"]),
        )
        await self.expense_repository.delete(existing["_id"])
        return existing_expense_date

    async def _upsert_source_linked_expense(
        self,
        *,
        scope_id: str,
        current_user: dict,
        source_kind: str,
        source_id: str,
        category: str,
        amount: float,
        expense_date: date,
        section: str = "cash",
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.expense_repository.find_source_linked_expense(
            scope_id=scope_id,
            source_kind=source_kind,
            source_id=source_id,
        )
        resolved_amount = round(max(float(amount or 0), 0.0), 2)
        if resolved_amount <= 0:
            if existing is not None:
                await self.expense_repository.delete(existing["_id"])
            return None

        payload = {
            "category": category.strip() or "Expense",
            "amount": resolved_amount,
            "expense_date": datetime.combine(expense_date, datetime.min.time(), tzinfo=UTC),
            "section": section if section in {"cash", "bank"} else "cash",
            "notes": notes,
            "source_kind": source_kind,
            "source_id": source_id,
        }
        if existing is None:
            return await self.expense_repository.create(
                {
                    "tenant_id": scope_id,
                    **payload,
                    "created_by_user_id": str(current_user["_id"]),
                }
            )
        return await self.expense_repository.update(existing["_id"], payload)

    async def _delete_source_linked_expense(self, *, scope_id: str, source_kind: str, source_id: str) -> None:
        await self.expense_repository.delete_source_linked_expenses(
            scope_id=scope_id,
            source_kind=source_kind,
            source_id=source_id,
        )

    async def _sync_document_linked_expense(
        self,
        *,
        scope_id: str,
        current_user: dict,
        document: dict[str, Any],
    ) -> None:
        source_id = str(document.get("id") or document.get("_id") or "")
        if not source_id:
            return
        document_type = str(document.get("document_type") or "").lower()
        raw_invoice_date = document.get("invoice_date")
        if document.get("status") != "processed" or document_type != "expense" or not raw_invoice_date:
            await self._delete_source_linked_expense(scope_id=scope_id, source_kind="document", source_id=source_id)
            return
        invoice_date = self._safe_parse_date(raw_invoice_date)
        amount = self._safe_float(document.get("expense_amount"), default=self._safe_float(document.get("total_amount")))
        await self._upsert_source_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="document",
            source_id=source_id,
            category=str(document.get("document_label") or "Expense"),
            amount=amount,
            expense_date=invoice_date,
            section="cash",
            notes=str(document.get("counterparty_name") or document.get("supplier_name") or "Uploaded document"),
        )

    async def _sync_daily_record_linked_expense(
        self,
        *,
        scope_id: str,
        current_user: dict,
        record: dict[str, Any],
    ) -> None:
        source_id = str(record.get("id") or record.get("_id") or "")
        raw_business_date = record.get("business_date")
        if not source_id or not raw_business_date:
            return
        business_date = self._safe_parse_date(raw_business_date)
        await self._upsert_source_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="manual_entry",
            source_id=source_id,
            category="Expenses in Cash",
            amount=self._safe_float(record.get("expenses_in_cash")),
            expense_date=business_date,
            section="cash",
            notes=str(record.get("notes") or "Entered from daily data"),
        )

    async def _upsert_source_linked_cash_deposit(
        self,
        *,
        scope_id: str,
        current_user: dict,
        source_kind: str,
        source_id: str,
        source_subtype: str,
        deposit_date: date,
        amount: float,
        deposit_type: str,
        bank_account: str,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.cash_repository.find_source_linked_deposit(
            scope_id=scope_id,
            source_kind=source_kind,
            source_id=source_id,
            source_subtype=source_subtype,
        )
        resolved_amount = round(max(float(amount or 0), 0.0), 2)
        if resolved_amount <= 0:
            if existing is not None:
                await self.cash_repository.delete(existing["_id"])
            return None

        resolved_deposit_type = str(deposit_type or "").strip().lower()
        if resolved_deposit_type not in self.CASH_TRANSACTION_TYPES:
            resolved_deposit_type = "cash_deposit"

        payload = {
            "deposit_date": datetime.combine(deposit_date, datetime.min.time(), tzinfo=UTC),
            "amount": resolved_amount,
            "type": resolved_deposit_type,
            "bank_account": bank_account.strip() or "Cash",
            "notes": notes,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_subtype": source_subtype,
        }
        if existing is None:
            return await self.cash_repository.create(
                {
                    "tenant_id": scope_id,
                    **payload,
                    "created_by_user_id": str(current_user["_id"]),
                }
            )
        return await self.cash_repository.update(existing["_id"], payload)

    async def _delete_source_linked_cash_deposits(self, *, scope_id: str, source_kind: str, source_id: str) -> None:
        await self.cash_repository.delete_source_linked_deposits(
            scope_id=scope_id,
            source_kind=source_kind,
            source_id=source_id,
        )

    async def _sync_document_linked_cash_deposit(
        self,
        *,
        scope_id: str,
        current_user: dict,
        document: dict[str, Any],
    ) -> None:
        source_id = str(document.get("id") or document.get("_id") or "")
        if not source_id:
            return
        document_type = str(document.get("document_type") or "").lower()
        raw_invoice_date = document.get("invoice_date")
        if document.get("status") != "processed" or document_type not in {"cash", "revenue"} or not raw_invoice_date:
            await self._delete_source_linked_cash_deposits(scope_id=scope_id, source_kind="document", source_id=source_id)
            return

        invoice_date = self._safe_parse_date(raw_invoice_date)
        if document_type == "cash":
            await self.cash_repository.delete_source_linked_deposit(
                scope_id=scope_id,
                source_kind="document",
                source_id=source_id,
                source_subtype="revenue_amount",
            )
            await self._upsert_source_linked_cash_deposit(
                scope_id=scope_id,
                current_user=current_user,
                source_kind="document",
                source_id=source_id,
                source_subtype="cash_amount",
                deposit_date=invoice_date,
                amount=self._safe_float(document.get("cash_amount"), default=self._safe_float(document.get("total_amount"))),
                deposit_type="cash_deposit",
                bank_account=str(document.get("document_label") or "Cash Collection"),
                notes=str(document.get("counterparty_name") or document.get("supplier_name") or "Uploaded cash document"),
            )
            return

        await self.cash_repository.delete_source_linked_deposit(
            scope_id=scope_id,
            source_kind="document",
            source_id=source_id,
            source_subtype="cash_amount",
        )
        await self._upsert_source_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="document",
            source_id=source_id,
            source_subtype="revenue_amount",
            deposit_date=invoice_date,
            amount=self._safe_float(document.get("revenue_amount"), default=self._safe_float(document.get("total_amount"))),
            deposit_type="bank_deposit",
            bank_account=str(document.get("counterparty_name") or document.get("supplier_name") or "Bank Revenue"),
            notes=str(document.get("document_label") or "Uploaded revenue document"),
        )

    async def _sync_daily_record_linked_cash_deposits(
        self,
        *,
        scope_id: str,
        current_user: dict,
        record: dict[str, Any],
    ) -> None:
        source_id = str(record.get("id") or record.get("_id") or "")
        raw_business_date = record.get("business_date")
        if not source_id or not raw_business_date:
            return
        business_date = self._safe_parse_date(raw_business_date)
        method = str(record.get("method") or "")

        await self._upsert_source_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="manual_entry",
            source_id=source_id,
            source_subtype="pos_payments",
            deposit_date=business_date,
            amount=self._safe_float(record.get("pos_payments")),
            deposit_type="pos_payment",
            bank_account="POS Settlement",
            notes="Entered from daily data",
        )

        if method == "method_2":
            await self._upsert_source_linked_cash_deposit(
                scope_id=scope_id,
                current_user=current_user,
                source_kind="manual_entry",
                source_id=source_id,
                source_subtype="cash_payments",
                deposit_date=business_date,
                amount=self._safe_float(record.get("cash_payments")),
                deposit_type="cash_in",
                bank_account="Cash Payments",
                notes="Entered from daily data",
            )
            await self._upsert_source_linked_cash_deposit(
                scope_id=scope_id,
                current_user=current_user,
                source_kind="manual_entry",
                source_id=source_id,
                source_subtype="bank_transfer_payments",
                deposit_date=business_date,
                amount=self._safe_float(record.get("bank_transfer_payments")),
                deposit_type="bank_transfer_payment",
                bank_account="Bank Transfer Collection",
                notes="Entered from daily data",
            )
            await self._upsert_source_linked_cash_deposit(
                scope_id=scope_id,
                current_user=current_user,
                source_kind="manual_entry",
                source_id=source_id,
                source_subtype="cash_out",
                deposit_date=business_date,
                amount=self._safe_float(record.get("cash_out")),
                deposit_type="cash_out",
                bank_account="Register Cash Out",
                notes="Entered from daily data",
            )
            await self._upsert_source_linked_cash_deposit(
                scope_id=scope_id,
                current_user=current_user,
                source_kind="manual_entry",
                source_id=source_id,
                source_subtype="expenses_in_cash",
                deposit_date=business_date,
                amount=self._safe_float(record.get("expenses_in_cash")),
                deposit_type="cash_expense",
                bank_account="Expenses in Cash",
                notes="Entered from daily data",
            )
            for stale_subtype in ("cash_in", "cash_withdrawals"):
                await self.cash_repository.delete_source_linked_deposit(
                    scope_id=scope_id,
                    source_kind="manual_entry",
                    source_id=source_id,
                    source_subtype=stale_subtype,
                )
            return

        await self._upsert_source_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="manual_entry",
            source_id=source_id,
            source_subtype="cash_in",
            deposit_date=business_date,
            amount=self._safe_float(record.get("cash_in")),
            deposit_type="cash_in",
            bank_account="Cash In",
            notes=str(record.get("notes") or "Entered from daily data"),
        )
        await self._upsert_source_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="manual_entry",
            source_id=source_id,
            source_subtype="cash_withdrawals",
            deposit_date=business_date,
            amount=self._safe_float(record.get("cash_withdrawals")),
            deposit_type="cash_withdrawal",
            bank_account="Cash Withdrawals",
            notes=str(record.get("notes") or "Entered from daily data"),
        )
        await self._upsert_source_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="manual_entry",
            source_id=source_id,
            source_subtype="cash_out",
            deposit_date=business_date,
            amount=self._safe_float(record.get("cash_out")),
            deposit_type="cash_out",
            bank_account="Cash Out",
            notes=str(record.get("notes") or "Entered from daily data"),
        )
        await self._upsert_source_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            source_kind="manual_entry",
            source_id=source_id,
            source_subtype="expenses_in_cash",
            deposit_date=business_date,
            amount=self._safe_float(record.get("expenses_in_cash")),
            deposit_type="cash_expense",
            bank_account="Expenses in Cash",
            notes=str(record.get("notes") or "Entered from daily data"),
        )
        for stale_subtype in ("cash_payments", "bank_transfer_payments"):
            await self.cash_repository.delete_source_linked_deposit(
                scope_id=scope_id,
                source_kind="manual_entry",
                source_id=source_id,
                source_subtype=stale_subtype,
            )

    def _build_cash_deposit_transactions(self, deposit: dict[str, Any]) -> list[dict[str, Any]]:
        deposit_date = self._safe_parse_date(deposit.get("deposit_date"))
        if deposit_date is None:
            return []
        return [
            {
                "business_date": deposit_date.isoformat(),
                "transaction_type": str(deposit.get("type") or "bank_deposit").lower(),
                "payment_channel": "cash",
                "amount": self._safe_float(deposit.get("amount")),
                "currency": "EUR",
                "reference_label": str(deposit.get("bank_account") or "Deposit"),
                "metadata": {
                    "bank_account": deposit.get("bank_account"),
                    "notes": deposit.get("notes"),
                    "ledger_group": "cash_movement",
                    "affects_revenue": False,
                    "affects_cash": True,
                    "affects_profit": False,
                },
            }
        ]

    def _build_daily_record_transactions(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        business_date = str(record.get("business_date") or "")
        if not business_date:
            return []
        transactions: list[dict[str, Any]] = []

        def add_transaction(*, transaction_type: str, amount: float, payment_channel: str, reference_label: str) -> None:
            resolved_amount = round(float(amount), 2)
            if resolved_amount <= 0:
                return
            ledger_group = {
                "bank_collection": "sale",
                "cash_collection": "sale",
                "withdrawal": "cash_movement",
                "expense": "expense",
            }.get(transaction_type, "other")
            transactions.append(
                {
                    "business_date": business_date,
                    "transaction_type": transaction_type,
                    "payment_channel": payment_channel,
                    "amount": resolved_amount,
                    "currency": "EUR",
                    "reference_label": reference_label,
                    "metadata": {
                        "method": record.get("method"),
                        "manual_entry_id": record.get("id"),
                        "ledger_group": ledger_group,
                        "affects_revenue": transaction_type in {"bank_collection", "cash_collection"},
                        "affects_cash": transaction_type in {"cash_collection", "withdrawal", "expense"},
                        "affects_profit": transaction_type == "expense",
                    },
                }
            )

        if record.get("method") == "method_1":
            add_transaction(transaction_type="bank_collection", amount=self._safe_float(record.get("pos_payments")), payment_channel="pos", reference_label="POS Payments")
            add_transaction(transaction_type="cash_collection", amount=self._safe_float(record.get("cash_in")), payment_channel="cash", reference_label="Cash In")
            add_transaction(transaction_type="withdrawal", amount=self._safe_float(record.get("cash_withdrawals")), payment_channel="cash", reference_label="Cash Withdrawals")
            add_transaction(transaction_type="withdrawal", amount=self._safe_float(record.get("cash_out")), payment_channel="cash", reference_label="Cash Out")
            add_transaction(transaction_type="expense", amount=self._safe_float(record.get("expenses_in_cash")), payment_channel="cash", reference_label="Expenses in Cash")
            return transactions

        add_transaction(transaction_type="bank_collection", amount=self._safe_float(record.get("pos_payments")), payment_channel="pos", reference_label="POS Payments")
        add_transaction(transaction_type="cash_collection", amount=self._safe_float(record.get("cash_payments")), payment_channel="cash", reference_label="Cash Payments")
        add_transaction(transaction_type="bank_collection", amount=self._safe_float(record.get("bank_transfer_payments")), payment_channel="bank_transfer", reference_label="Bank Transfer Payments")
        add_transaction(transaction_type="withdrawal", amount=self._safe_float(record.get("cash_out")), payment_channel="cash", reference_label="Register Cash Out")
        add_transaction(transaction_type="expense", amount=self._safe_float(record.get("expenses_in_cash")), payment_channel="cash", reference_label="Expenses in Cash")
        return transactions

    async def get_home(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
        include_metrics: bool = True,
        include_cash_management: bool = True,
        include_revenue: bool = True,
        include_featured_insight: bool = True,
        include_recent_activity: bool = True,
    ) -> RestaurantHomeResponse:
        del period
        scope_id, daily_records, expenses, documents, cash_deposits, inventory_items = await self._load_home_dependencies(current_user)
        recent_daily_records = (
            await self._load_recent_activity_daily_records(scope_id)
            if include_recent_activity
            else []
        )

        weekly_snapshot, monthly_snapshot = await asyncio.gather(
            self._build_home_period_snapshot(
                scope_id=scope_id,
                daily_records=daily_records,
                expenses=expenses,
                documents=documents,
                cash_deposits=cash_deposits,
                period='weekly',
                from_date=from_date,
                to_date=to_date,
                include_metrics=include_metrics,
                include_cash_management=include_cash_management,
                include_revenue=include_revenue,
                include_featured_insight=include_featured_insight,
            ),
            self._build_home_period_snapshot(
                scope_id=scope_id,
                daily_records=daily_records,
                expenses=expenses,
                documents=documents,
                cash_deposits=cash_deposits,
                period='monthly',
                from_date=from_date,
                to_date=to_date,
                include_metrics=include_metrics,
                include_cash_management=include_cash_management,
                include_revenue=include_revenue,
                include_featured_insight=include_featured_insight,
            ),
        )

        recent_activity = (
            self._build_recent_activity(
                current_user=current_user,
                daily_records=recent_daily_records,
                expenses=self.serialize_list(expenses),
                documents=self.serialize_list(documents),
                cash_deposits=self.serialize_list(cash_deposits),
                inventory_items=self.serialize_list(inventory_items),
            )
            if include_recent_activity
            else []
        )

        return RestaurantHomeResponse(
            greeting_name=current_user["full_name"].split()[0],
            restaurant_name=current_user.get("restaurant_name"),
            preferred_language=str(current_user.get("preferred_language", "en")),
            weekly=weekly_snapshot,
            monthly=monthly_snapshot,
            quick_actions=[
                QuickActionResponse(key="upload_invoice", label="Upload Invoice"),
                QuickActionResponse(key="daily_data", label="Daily Data"),
                QuickActionResponse(key="expenses", label="Expenses"),
                QuickActionResponse(key="cash", label="Cash"),
            ],
            recent_activity=recent_activity,
        )

    async def get_home_metrics(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> RestaurantHomeMetricsResponse:
        _, daily_records, expenses, _, _, _ = await self._load_home_dependencies(current_user)
        filtered_daily_records = self._filter_home_daily_records(daily_records, period=period, from_date=from_date, to_date=to_date)
        filtered_expenses = self._filter_home_expenses(expenses, period=period, from_date=from_date, to_date=to_date)
        metrics_context = self._build_metrics_context(daily_records=filtered_daily_records, expenses=filtered_expenses)
        home_revenue_total = round(sum(self._resolve_home_revenue_amount(item) for item in filtered_daily_records), 2)
        return RestaurantHomeMetricsResponse(
            period=period,
            items=self._build_home_metric_cards(home_revenue_total=home_revenue_total, metrics_context=metrics_context),
        )

    async def get_home_cash_management(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> RestaurantHomeCashManagementResponse:
        _, daily_records, _, _, cash_deposits, _ = await self._load_home_dependencies(current_user)
        filtered_daily_records = self._filter_home_daily_records(daily_records, period=period, from_date=from_date, to_date=to_date)
        filtered_cash_deposits = self._filter_home_cash_deposits(cash_deposits, period=period, from_date=from_date, to_date=to_date)
        return RestaurantHomeCashManagementResponse(
            period=period,
            items=self._build_home_cash_management_items(
                filtered_daily_records=filtered_daily_records,
                filtered_cash_deposits=filtered_cash_deposits,
            ),
        )

    async def get_home_revenue(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> RestaurantHomeRevenueResponse:
        _, daily_records, _, _, _, _ = await self._load_home_dependencies(current_user)
        anchor_date = self._resolve_latest_business_date(daily_records)
        filtered_daily_records = self._filter_home_daily_records(
            daily_records,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        revenue_points = self._build_home_revenue_chart(filtered_daily_records, period=period, anchor_date=anchor_date)
        if period == 'monthly':
            revenue_points = [ChartPointResponse(label=point.label.replace('W', 'Week '), value=point.value) for point in revenue_points]
        return RestaurantHomeRevenueResponse(period=period, items=revenue_points)

    async def get_home_insight(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> RestaurantHomeInsightResponse:
        scope_id, daily_records, expenses, _, _, _ = await self._load_home_dependencies(current_user)
        filtered_daily_records = self._filter_home_daily_records(daily_records, period=period, from_date=from_date, to_date=to_date)
        filtered_expenses = self._filter_home_expenses(expenses, period=period, from_date=from_date, to_date=to_date)
        insights = await self._get_or_generate_insights(
            current_user=current_user,
            scope_id=scope_id,
            daily_records=filtered_daily_records,
            expenses=filtered_expenses,
        )
        return RestaurantHomeInsightResponse(period=period, insight=insights[0] if insights else None)

    async def get_home_recent_activity(self, current_user: dict, *, limit: int = 6, diverse: bool = True) -> RestaurantHomeRecentActivityResponse:
        scope_id, _, expenses, documents, cash_deposits, inventory_items = await self._load_home_dependencies(current_user)
        return RestaurantHomeRecentActivityResponse(
            items=self._build_recent_activity(
                current_user=current_user,
                daily_records=await self._load_recent_activity_daily_records(scope_id),
                expenses=self.serialize_list(expenses),
                documents=self.serialize_list(documents),
                cash_deposits=self.serialize_list(cash_deposits),
                inventory_items=self.serialize_list(inventory_items),
                max_items=limit,
                prefer_distinct_kinds=diverse,
            )
        )

    async def get_notification_feed(self, current_user: dict) -> RestaurantNotificationFeedResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        (
            daily_records,
            expenses_result,
            documents_result,
            cash_deposits_result,
            inventory_result,
        ) = await asyncio.gather(
            self._load_recent_activity_daily_records(scope_id),
            self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=25),
            self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=25),
            self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=25),
            self.inventory_repository.list_by_scope(scope_id=scope_id, page=1, page_size=25),
        )
        expenses, _ = expenses_result
        documents, _ = documents_result
        cash_deposits, _ = cash_deposits_result
        inventory_items, _ = inventory_result
        return RestaurantNotificationFeedResponse(
            items=self._build_notification_feed(
                daily_records=daily_records,
                expenses=self.serialize_list(expenses),
                documents=self.serialize_list(documents),
                cash_deposits=self.serialize_list(cash_deposits),
                inventory_items=self.serialize_list(inventory_items),
            )
        )

    async def get_home_vat_balance(self, current_user: dict) -> RestaurantHomeVatBalanceResponse:
        vat_overview = await self.get_vat_overview(current_user)
        return RestaurantHomeVatBalanceResponse(balance=vat_overview.estimated_vat_balance)

    async def _load_home_dependencies(self, current_user: dict) -> tuple[str, list[dict], list[dict], list[dict], list[dict], list[dict]]:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        (
            (daily_records, _),
            (expenses, _),
            (documents, _),
            (cash_deposits, _),
            (inventory_items, _),
        ) = await asyncio.gather(
            self.record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365),
            self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365),
            self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365),
            self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=120),
            self.inventory_repository.list_by_scope(scope_id=scope_id, page=1, page_size=120),
        )
        return scope_id, daily_records, expenses, documents, cash_deposits, inventory_items

    async def _load_recent_activity_daily_records(self, scope_id: str) -> list[dict]:
        daily_records, _ = await self.daily_record_repository.list_by_scope(
            scope_id=scope_id,
            page=1,
            page_size=120,
        )
        return self.serialize_list(daily_records)

    async def _build_home_period_snapshot(
        self,
        *,
        scope_id: str,
        daily_records: list[dict],
        expenses: list[dict],
        documents: list[dict],
        cash_deposits: list[dict],
        period: str,
        from_date: date | None,
        to_date: date | None,
        include_metrics: bool = True,
        include_cash_management: bool = True,
        include_revenue: bool = True,
        include_featured_insight: bool = True,
    ) -> RestaurantHomePeriodResponse:
        anchor_date = self._resolve_latest_business_date(daily_records)
        filtered_daily_records = self._filter_home_daily_records(
            daily_records,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        filtered_expenses = self._filter_home_expenses(
            expenses,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        filtered_cash_deposits = self._filter_home_cash_deposits(
            cash_deposits,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        filtered_documents = self._filter_home_documents(
            documents,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )

        insights = (
            await self._get_or_generate_insights(
                current_user=current_user,
                scope_id=scope_id,
                daily_records=filtered_daily_records,
                expenses=filtered_expenses,
            )
            if include_featured_insight
            else []
        )
        metrics_context = self._build_metrics_context(daily_records=filtered_daily_records, expenses=filtered_expenses)
        home_revenue_total = round(sum(self._resolve_home_revenue_amount(item) for item in filtered_daily_records), 2)

        revenue_points: list[ChartPointResponse] = []
        if include_revenue:
            revenue_points = self._build_home_revenue_chart(filtered_daily_records, period=period, anchor_date=anchor_date)
            if period == 'monthly':
                revenue_points = [ChartPointResponse(label=point.label.replace('W', 'Week '), value=point.value) for point in revenue_points]
        invoice_document_total = round(sum(float(item.get("total_amount", 0)) for item in filtered_documents if item.get("status") == "processed"), 2)

        return RestaurantHomePeriodResponse(
            metrics=self._build_home_metric_cards(home_revenue_total=home_revenue_total, metrics_context=metrics_context) if include_metrics else [],
            cash_management=self._build_home_cash_management_items(
                filtered_daily_records=filtered_daily_records,
                filtered_cash_deposits=filtered_cash_deposits,
            ) if include_cash_management else [],
            vat_balance=self._calculate_vat_balance(home_revenue_total, metrics_context["expenses_total"]),
            revenue=revenue_points,
            operating_revenue_total=home_revenue_total,
            invoice_document_total=invoice_document_total,
            featured_insight=insights[0] if include_featured_insight and insights else None,
        )

    def _build_home_metric_cards(self, *, home_revenue_total: float, metrics_context: dict[str, float | int]) -> list[MetricCardResponse]:
        return [
            MetricCardResponse(label="Revenue", value=home_revenue_total, change_percent=float(metrics_context["revenue_change_percent"])),
            MetricCardResponse(label="Expenses", value=float(metrics_context["expenses_total"]), change_percent=float(metrics_context["expense_change_percent"])),
            MetricCardResponse(label="Food Cost", value=float(metrics_context["food_cost_total"]), change_percent=float(metrics_context["food_cost_change_percent"])),
            MetricCardResponse(label="Profit", value=float(metrics_context["profit_total"]), change_percent=float(metrics_context["profit_change_percent"])),
        ]

    def _build_home_cash_management_items(
        self,
        *,
        filtered_daily_records: list[dict],
        filtered_cash_deposits: list[dict],
    ) -> list[CashManagementItemResponse]:
        cash_available = self._calculate_cash_available_flow(filtered_daily_records)
        cash_deposit_total = round(
            sum(
                float(
                    item.get("bank_deposits_total", item.get("deposits_collection_total", 0)) or 0
                )
                for item in filtered_daily_records
            ),
            2,
        )
        if not cash_deposit_total and filtered_cash_deposits:
            cash_deposit_total = round(sum(float(item.get("amount", 0)) for item in filtered_cash_deposits), 2)
        pos_payments_total = round(
            sum(float(item.get("pos_payments_total", item.get("pos_payments", 0)) or 0) for item in filtered_daily_records),
            2,
        )
        total_collection = round(cash_available + cash_deposit_total, 2)
        return [
            CashManagementItemResponse(label="Total Collection", amount=total_collection, subtitle="Cash and POS collections"),
            CashManagementItemResponse(label="POS Payments", amount=pos_payments_total, subtitle="Card and POS settlements"),
            CashManagementItemResponse(label="Available Cash", amount=cash_available, subtitle="Cash remaining after expenses and withdrawals"),
            CashManagementItemResponse(label="Cash Deposit", amount=cash_deposit_total, subtitle="Bank transfers and recorded deposits"),
        ]

    @staticmethod
    def _calculate_cash_available_flow(records: list[dict]) -> float:
        has_cash_flow_inputs = any(
            any(key in item for key in ("cash_in", "cash_payments", "cash_out", "cash_withdrawals"))
            for item in records
        )
        if not has_cash_flow_inputs:
            return round(sum(float(item.get("cash_available", 0) or 0) for item in records), 2)

        cash_in_total = sum(float(item.get("cash_in", item.get("cash_payments", 0)) or 0) for item in records)
        cash_out_total = sum(float(item.get("cash_out", 0) or 0) for item in records)
        cash_withdrawals_total = sum(float(item.get("cash_withdrawals", 0) or 0) for item in records)
        expenses_total = sum(float(item.get("total_expenses", 0) or 0) for item in records)
        return round(max(cash_in_total - (cash_out_total + cash_withdrawals_total + expenses_total), 0.0), 2)

    async def get_vat_overview(self, current_user: dict) -> VatOverviewResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=120)
        serialized_records = self.serialize_list(daily_records)
        revenue_total = sum(float(item.get("total_revenue", 0)) for item in serialized_records)
        expenses_total = sum(float(item.get("total_expenses", 0)) for item in serialized_records)
        vat_payable = round(revenue_total * self.VAT_RATE, 2)
        vat_receivable = round(expenses_total * self.VAT_RATE, 2)
        today = datetime.now(UTC).date()
        filing_deadline = today.replace(day=min(20, max(today.day, 1)))
        return VatOverviewResponse(
            estimated_vat_balance=round(vat_payable - vat_receivable, 2),
            vat_payable=vat_payable,
            vat_receivable=vat_receivable,
            filing_deadline=filing_deadline.isoformat(),
            report_ready=bool(serialized_records),
        )

    async def list_insights(self, current_user: dict) -> InsightDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        cash_deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=60)
        inventory_items, _ = await self.inventory_repository.list_by_scope(scope_id=scope_id, page=1, page_size=100)
        transactions, _ = await self.finance_transaction_repository.list_by_scope(scope_id=scope_id, page=1, page_size=250)
        insights = await self._get_or_generate_insights(
            current_user=current_user,
            scope_id=scope_id,
            daily_records=daily_records,
            expenses=expenses,
            documents=documents,
            cash_deposits=cash_deposits,
            inventory_items=inventory_items,
            transactions=transactions,
        )
        return await self.get_insight_detail(current_user, insights[0].id)

    async def get_insight_detail(self, current_user: dict, insight_id: str) -> InsightDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        insight = self.serialize(await self.insight_repository.get_by_scope_and_id(scope_id=scope_id, insight_id=insight_id))
        insight_language = self._resolve_chat_language(current_user)
        related_items = self._build_other_related_insights(insight)
        return InsightDetailResponse(
            id=insight["id"],
            title=self._resolve_localized_text(
                insight.get("title_translations"),
                language=insight_language,
                fallback=str(insight.get("title") or ""),
            ),
            priority=insight["priority"],
            metric_value=insight["metric_value"],
            metric_caption=self._resolve_localized_text(
                insight.get("metric_caption_translations"),
                language=insight_language,
                fallback=str(insight.get("metric_caption") or ""),
            ),
            trend=[ChartPointResponse(**item) for item in insight.get("trend", [])],
            root_causes=self._resolve_localized_list(
                insight.get("root_causes_translations"),
                language=insight_language,
                fallback=insight.get("root_causes", []),
            ),
            recommended_actions=[
                InsightActionResponse(**item)
                for item in self._resolve_localized_actions(
                    insight.get("recommended_actions_translations"),
                    language=insight_language,
                    fallback=insight.get("recommended_actions", []),
                )
            ],
            other_related_insights=related_items,
            title_translations=insight.get("title_translations"),
            metric_caption_translations=insight.get("metric_caption_translations"),
            root_causes_translations=insight.get("root_causes_translations"),
            recommended_actions_translations=insight.get("recommended_actions_translations"),
        )

    async def upload_and_extract_document(
        self,
        current_user: dict,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        raw_file: Any | None = None,
    ) -> DocumentExtractionResponse:
        del raw_file
        if not file_bytes:
            raise ValidationException("Uploaded file is empty")
        extraction = await self.openai_service.extract_invoice(file_name=file_name, content_type=content_type, file_bytes=file_bytes)
        normalized = self._normalize_document_extraction(extraction=extraction, file_name=file_name)
        return DocumentExtractionResponse(
            document_type=normalized["document_type"],
            document_label=normalized["document_label"],
            counterparty_name=normalized["counterparty_name"],
            document_number=normalized["invoice_number"],
            document_date=normalized["invoice_date"],
            total_amount=normalized["total_amount"],
            currency=normalized["currency"],
            expense_amount=normalized["expense_amount"],
            cash_amount=normalized["cash_amount"],
            revenue_amount=normalized["revenue_amount"],
            profit_amount=normalized["profit_amount"],
            ai_provider="openai" if self.openai_service.enabled else "fallback",
            ai_summary=normalized["ai_summary"],
            source_file_name=file_name,
            line_items=[DocumentLineItemSchema(**item) for item in normalized["line_items"]],
        )

    async def create_document_from_confirmation(self, current_user: dict, payload: DocumentSaveRequest) -> DocumentConfirmSaveResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        now = datetime.now(UTC)
        normalized = self._normalize_document_extraction(extraction=payload.model_dump(mode="json"), file_name=payload.source_file_name)
        resolved_invoice_date = payload.invoice_date or now.date()
        document = await self.document_repository.create(
            {
                "tenant_id": scope_id,
                "document_type": normalized["document_type"],
                "document_label": normalized["document_label"],
                "counterparty_name": normalized["counterparty_name"],
                "supplier_name": normalized["supplier_name"],
                "invoice_number": normalized["invoice_number"],
                "invoice_date": resolved_invoice_date.isoformat(),
                "upload_date": now,
                "total_amount": normalized["total_amount"],
                "currency": normalized["currency"],
                "expense_amount": normalized["expense_amount"],
                "cash_amount": normalized["cash_amount"],
                "revenue_amount": normalized["revenue_amount"],
                "profit_amount": normalized["profit_amount"],
                "status": "processed",
                "ai_provider": payload.ai_provider,
                "ai_summary": normalized["ai_summary"],
                "source_file_name": payload.source_file_name,
                "line_items": [item.model_dump(mode="json") for item in payload.line_items],
                "created_by_user_id": str(current_user["_id"]),
                "last_edited_by_user_id": str(current_user["_id"]),
                "last_edited_at": now,
                "confirmed_by_user_id": str(current_user["_id"]),
                "confirmed_at": now,
            }
        )
        serialized_document = self.serialize(document)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="document",
            source_id=serialized_document["id"],
            transactions=self._build_document_transactions(serialized_document),
        )
        await self._sync_document_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            document=serialized_document,
        )
        await self._sync_document_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            document=serialized_document,
        )
        await self._sync_restaurant_record(scope_id=scope_id, business_date=resolved_invoice_date, current_user=current_user)
        await self._send_activity_push_for_document(current_user, serialized_document)
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
        serialized_updated = self.serialize(updated)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="document",
            source_id=serialized_updated["id"],
            transactions=self._build_document_transactions(serialized_updated),
        )
        await self._sync_document_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            document=serialized_updated,
        )
        await self._sync_document_linked_cash_deposit(
            scope_id=scope_id,
            current_user=current_user,
            document=serialized_updated,
        )
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

        pdf_bytes = self._build_invoice_pdf(serialized)
        try:
            import fitz

            try:
                pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
                page = pdf_document.load_page(0)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                png_bytes = pixmap.tobytes("png")
                png_width = pixmap.width
                png_height = pixmap.height
                pdf_document.close()
            except Exception as exc:
                raise ValidationException('Unable to render invoice image from generated PDF') from exc

            if image_format == 'png':
                return f"{safe_supplier}-{serialized['id']}.png", 'image/png', png_bytes

            if image_format == 'svg':
                encoded_png = base64.b64encode(png_bytes).decode("ascii")
                svg_text = (
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{png_width}" height="{png_height}" viewBox="0 0 {png_width} {png_height}">'
                    f'<image href="data:image/png;base64,{encoded_png}" x="0" y="0" width="{png_width}" height="{png_height}" />'
                    f'</svg>'
                )
                return f"{safe_supplier}-{serialized['id']}.svg", 'image/svg+xml', svg_text.encode('utf-8')
        except ImportError:
            # fallback if PyMuPDF is not installed yet in the runtime
            svg_text = self._build_document_svg(serialized)
            if image_format == 'svg':
                return f"{safe_supplier}-{serialized['id']}.svg", 'image/svg+xml', svg_text.encode('utf-8')
            if image_format == 'png':
                try:
                    import cairosvg
                except ImportError as exc:
                    raise ValidationException('Image export requires PyMuPDF or CairoSVG to be installed on the server') from exc
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
            serialized_updated = self.serialize(updated)
            await self._replace_transactions_for_source(
                scope_id=scope_id,
                source_kind="document",
                source_id=serialized_updated["id"],
                transactions=self._build_document_transactions(serialized_updated),
            )
            await self._sync_document_linked_expense(
                scope_id=scope_id,
                current_user=current_user,
                document=serialized_updated,
            )
            await self._sync_document_linked_cash_deposit(
                scope_id=scope_id,
                current_user=current_user,
                document=serialized_updated,
            )
            old_invoice_date_value = document.get("invoice_date")
            if old_invoice_date_value:
                await self._sync_restaurant_record(scope_id=scope_id, business_date=datetime.fromisoformat(str(old_invoice_date_value)).date(), current_user=current_user)
            await self._sync_restaurant_record(scope_id=scope_id, business_date=effective_invoice_date, current_user=current_user)
        else:
            await self._delete_transactions_for_source(scope_id=scope_id, source_kind="document", source_id=str(document["_id"]))
            await self._delete_source_linked_expense(scope_id=scope_id, source_kind="document", source_id=str(document["_id"]))
            await self._delete_source_linked_cash_deposits(scope_id=scope_id, source_kind="document", source_id=str(document["_id"]))
        return self._to_document_detail(updated)

    async def delete_document(self, current_user: dict, document_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.document_repository.get_scoped_by_id(document_id, scope_id)
        invoice_date = datetime.fromisoformat(str(document["invoice_date"])).date() if document.get("invoice_date") else None
        await self._delete_transactions_for_source(scope_id=scope_id, source_kind="document", source_id=str(document["_id"]))
        await self._delete_source_linked_expense(scope_id=scope_id, source_kind="document", source_id=str(document["_id"]))
        await self._delete_source_linked_cash_deposits(scope_id=scope_id, source_kind="document", source_id=str(document["_id"]))
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
                "section": payload.section,
                "notes": payload.notes,
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        serialized_expense = self.serialize(document)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="expense",
            source_id=serialized_expense["id"],
            transactions=self._build_expense_transactions(serialized_expense),
        )
        await self._sync_restaurant_record(scope_id=scope_id, business_date=payload.expense_date, current_user=current_user)
        await self._send_activity_push_for_expense(current_user, serialized_expense)
        return self._to_expense_response(document)

    async def list_expenses(self, current_user: dict, *, page: int, page_size: int, reference_date: date | None = None) -> ExpenseListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, _ = await self.expense_repository.list_by_scope(
            scope_id=scope_id,
            page=1,
            page_size=max(page_size, 500),
        )
        serialized_items = self.serialize_list(items)
        today = reference_date or self._resolve_anchor_date(*(item.get("expense_date") for item in serialized_items))
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        all_expense_items = sorted(
            serialized_items,
            key=lambda item: (
                str(item.get("expense_date") or ""),
                str(item.get("created_at") or ""),
            ),
            reverse=True,
        )

        def build_period(expenses: list[dict]) -> ExpensePeriodResponse:
            total = round(sum(float(item.get("amount", 0)) for item in expenses), 2)
            category_totals: dict[str, float] = {}
            for item in expenses:
                category = str(item.get("category") or "Other")
                category_totals[category] = round(category_totals.get(category, 0.0) + float(item.get("amount", 0)), 2)
            total_spend = round(sum(category_totals.values()), 2)
            distribution = [
                ExpenseDistributionItemResponse(
                    label=category,
                    percentage=round((amount / max(total_spend, 1)) * 100, 1),
                )
                for category, amount in sorted(category_totals.items(), key=lambda value: value[1], reverse=True)
            ]
            top_category = max(category_totals.items(), key=lambda value: value[1])[0] if category_totals else None
            return ExpensePeriodResponse(
                total=total,
                top_category=top_category,
                distribution=distribution,
                items=[self._to_expense_response(item) for item in expenses],
            )

        today_items = [item for item in all_expense_items if item["expense_date"][:10] == today.isoformat()]
        week_items = [item for item in all_expense_items if week_start.isoformat() <= item["expense_date"][:10] <= today.isoformat()]
        month_items = [item for item in all_expense_items if month_start.isoformat() <= item["expense_date"][:10] <= today.isoformat()]
        year_items = [item for item in all_expense_items if year_start.isoformat() <= item["expense_date"][:10] <= today.isoformat()]

        return ExpenseListResponse(
            today=build_period(today_items),
            this_week=build_period(week_items),
            this_month=build_period(month_items),
            this_year=build_period(year_items),
        )

    async def get_expense_detail(self, current_user: dict, expense_id: str) -> ExpenseResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        expense = await self.expense_repository.get_scoped_by_id(expense_id, scope_id)
        return self._to_expense_response(expense)

    async def delete_expense(self, current_user: dict, expense_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        expense = await self.expense_repository.get_scoped_by_id(expense_id, scope_id)
        if expense.get("source_kind"):
            raise ValidationException("Generated expenses must be deleted from their source record.")
        expense_date = self._safe_parse_date(expense.get("expense_date"))
        await self._delete_transactions_for_source(scope_id=scope_id, source_kind="expense", source_id=str(expense["_id"]))
        await self.expense_repository.delete(expense["_id"])
        if expense_date is not None:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=expense_date, current_user=current_user)

    async def create_cash_deposit(self, current_user: dict, payload: CashDepositCreateRequest) -> CashDepositResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        document = await self.cash_repository.create(
            {
                "tenant_id": scope_id,
                "deposit_date": datetime.combine(payload.deposit_date, datetime.min.time(), tzinfo=UTC),
                "amount": payload.amount,
                "type": payload.type,
                "bank_account": payload.bank_account,
                "notes": payload.notes,
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        serialized_deposit = self.serialize(document)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="deposit",
            source_id=serialized_deposit["id"],
            transactions=self._build_cash_deposit_transactions(serialized_deposit),
        )
        await self._sync_restaurant_record(scope_id=scope_id, business_date=payload.deposit_date, current_user=current_user)
        await self._send_activity_push_for_cash_deposit(current_user, serialized_deposit)
        return self._to_cash_deposit_response(document)

    async def get_cash_deposit(self, current_user: dict, deposit_id: str) -> CashDepositResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        deposit = await self.cash_repository.get_scoped_by_id(deposit_id, scope_id)
        return self._to_cash_deposit_response(deposit)

    async def update_cash_deposit(self, current_user: dict, deposit_id: str, payload: CashDepositUpdateRequest) -> CashDepositResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        deposit = await self.cash_repository.get_scoped_by_id(deposit_id, scope_id)
        if deposit.get("source_kind"):
            raise ValidationException("Generated cash transactions must be edited from their source record.")
        previous_deposit_date = self._safe_parse_date(deposit.get("deposit_date")) or payload.deposit_date
        updated = await self.cash_repository.update(
            deposit["_id"],
            {
                "deposit_date": datetime.combine(payload.deposit_date, datetime.min.time(), tzinfo=UTC),
                "amount": payload.amount,
                "type": payload.type,
                "bank_account": payload.bank_account,
                "notes": payload.notes,
            },
        )
        serialized_updated = self.serialize(updated)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="deposit",
            source_id=serialized_updated["id"],
            transactions=self._build_cash_deposit_transactions(serialized_updated),
        )
        await self._sync_restaurant_record(scope_id=scope_id, business_date=previous_deposit_date, current_user=current_user)
        if payload.deposit_date != previous_deposit_date:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=payload.deposit_date, current_user=current_user)
        return self._to_cash_deposit_response(updated)

    async def delete_cash_deposit(self, current_user: dict, deposit_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        deposit = await self.cash_repository.get_scoped_by_id(deposit_id, scope_id)
        if deposit.get("source_kind"):
            raise ValidationException("Generated cash transactions must be deleted from their source record.")
        previous_deposit_date = self._safe_parse_date(deposit.get("deposit_date"))
        await self._delete_transactions_for_source(scope_id=scope_id, source_kind="deposit", source_id=str(deposit["_id"]))
        await self.cash_repository.delete(deposit["_id"])
        if previous_deposit_date is not None:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=previous_deposit_date, current_user=current_user)

    async def create_bank_account(self, current_user: dict, payload: BankAccountCreateRequest) -> BankAccountResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        normalized_name = self._normalize_bank_account_name(payload.bank_account)
        existing = await self.bank_account_repository.find_by_normalized_name(scope_id=scope_id, normalized_name=normalized_name)
        if existing is not None:
            raise ConflictException("Bank account already exists", details={"bank_account": payload.bank_account})

        document = await self.bank_account_repository.create(
            {
                "tenant_id": scope_id,
                "bank_account": payload.bank_account,
                "normalized_name": normalized_name,
                "created_by_user_id": str(current_user["_id"]),
            }
        )
        return self._to_bank_account_response(document, deposited_amount=0.0)

    async def update_bank_account(self, current_user: dict, account_id: str, payload: BankAccountUpdateRequest) -> BankAccountResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        account = await self.bank_account_repository.get_scoped_by_id(account_id, scope_id)
        normalized_name = self._normalize_bank_account_name(payload.bank_account)
        existing = await self.bank_account_repository.find_by_normalized_name_excluding_id(
            scope_id=scope_id,
            normalized_name=normalized_name,
            exclude_id=account_id,
        )
        if existing is not None:
            raise ConflictException("Bank account already exists", details={"bank_account": payload.bank_account})

        updated = await self.bank_account_repository.update(
            account["_id"],
            {
                "bank_account": payload.bank_account,
                "normalized_name": normalized_name,
            },
        )
        deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        deposited_amount = 0.0
        old_normalized_name = self._normalize_bank_account_name(str(account.get("bank_account", "")))
        for item in self.serialize_list(deposits):
            deposit_normalized_name = self._normalize_bank_account_name(str(item.get("bank_account") or item.get("deposit_type") or ""))
            if deposit_normalized_name == old_normalized_name:
                deposited_amount = round(deposited_amount + float(item.get("amount", 0.0)), 2)
        return self._to_bank_account_response(updated, deposited_amount=deposited_amount)

    async def delete_bank_account(self, current_user: dict, account_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        account = await self.bank_account_repository.get_scoped_by_id(account_id, scope_id)
        await self.bank_account_repository.delete(account["_id"])

    async def list_bank_accounts(self, current_user: dict) -> BankAccountListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        accounts, total = await self.bank_account_repository.list_by_scope(scope_id=scope_id, page=1, page_size=100)
        deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        deposit_totals_by_account: dict[str, float] = {}
        for item in self.serialize_list(deposits):
            normalized_name = self._normalize_bank_account_name(str(item.get("bank_account") or item.get("deposit_type") or ""))
            if not normalized_name:
                continue
            deposit_totals_by_account[normalized_name] = round(
                deposit_totals_by_account.get(normalized_name, 0.0) + float(item.get("amount", 0.0)),
                2,
            )
        return BankAccountListResponse(
            total_accounts=total,
            items=[
                self._to_bank_account_response(
                    item,
                    deposited_amount=deposit_totals_by_account.get(
                        str(item.get("normalized_name") or self._normalize_bank_account_name(str(item.get("bank_account", "")))),
                        0.0,
                    ),
                )
                for item in accounts
            ],
        )

    async def list_inventory_categories(self, current_user: dict) -> InventoryCategoryListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items = await self.inventory_category_repository.list_by_scope(scope_id=scope_id, limit=100)
        return InventoryCategoryListResponse(items=[self._to_inventory_category_response(item) for item in items])

    async def create_inventory_category(self, current_user: dict, payload: InventoryCategoryCreateRequest) -> InventoryCategoryResponse:
        document = await self._upsert_inventory_category(current_user=current_user, name=payload.name)
        if document is None:
            raise ValidationException("Category name is required.")
        return self._to_inventory_category_response(document)

    async def list_inventory_suppliers(self, current_user: dict) -> InventorySupplierListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items = await self.inventory_supplier_repository.list_by_scope(scope_id=scope_id, limit=100)
        return InventorySupplierListResponse(items=[self._to_inventory_supplier_response(item) for item in items])

    async def create_inventory_supplier(self, current_user: dict, payload: InventorySupplierCreateRequest) -> InventorySupplierResponse:
        document = await self._upsert_inventory_supplier(current_user=current_user, name=payload.name)
        if document is None:
            raise ValidationException("Supplier name is required.")
        return self._to_inventory_supplier_response(document)

    async def get_cash_management(self, current_user: dict) -> CashManagementSummaryResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        (deposits, _), (daily_records, _), (finance_transactions, _) = await asyncio.gather(
            self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=200),
            self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=200),
            self.finance_transaction_repository.list_by_scope(scope_id=scope_id, page=1, page_size=1000),
        )

        serialized_deposits = self.serialize_list(deposits)
        serialized_daily = self.serialize_list(daily_records)
        serialized_transactions = self.serialize_list(finance_transactions)
        today = self._resolve_anchor_date(
            *(item.get("deposit_date") for item in serialized_deposits),
            *(item.get("business_date") for item in serialized_daily),
            *(item.get("business_date") for item in serialized_transactions),
        )
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        def parse_iso_date(value: Any) -> date:
            parsed = self._safe_parse_date(value)
            if parsed is not None:
                return parsed
            return today

        def in_range(value: date, start: date, end: date) -> bool:
            return start <= value <= end

        def build_period(start: date, end: date, label: str) -> CashPeriodOverviewResponse:
            daily_in_period = [item for item in serialized_daily if in_range(parse_iso_date(item.get("business_date")), start, end)]
            deposits_in_period = [item for item in serialized_deposits if in_range(parse_iso_date(item.get("deposit_date")), start, end)]
            transactions_in_period = [
                item for item in serialized_transactions
                if in_range(parse_iso_date(item.get("business_date")), start, end)
            ]
            live_snapshot = build_aggregate_snapshot(
                manual_records=daily_in_period,
                finance_transactions=transactions_in_period,
            )
            period_status = CashPeriodStatusResponse(
                total_collected=label,
                cash_available="IN_SAFE",
                pos_payments=label,
                withdrawals=label,
                bank_deposits=label,
                cash_deposits=label,
                deposits_collection=label,
            )
            period_summary = CashPeriodSummaryResponse(
                total_collected=round(float(live_snapshot.get("cash_collected_total", 0)), 2),
                cash_available=round(float(live_snapshot.get("cash_available", 0)), 2),
                pos_payments=round(float(live_snapshot.get("pos_payments_total", 0)), 2),
                withdrawals_total=round(float(live_snapshot.get("withdrawals_total", 0)), 2),
                bank_deposits=round(float(live_snapshot.get("bank_deposits_total", 0)), 2),
            )
            recent_deposits = self._build_recent_deposit_items(deposits=deposits_in_period, daily_records=daily_in_period)
            return CashPeriodOverviewResponse(
                summary=period_summary,
                status=period_status,
                recent_deposits=recent_deposits,
            )

        return CashManagementSummaryResponse(
            active_period="today",
            periods=CashOverviewPeriodsResponse(
                today=build_period(today, today, "TODAY"),
                this_week=build_period(week_start, today, "THIS_WEEK"),
                this_month=build_period(month_start, today, "THIS_MONTH"),
            ),
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
                        DailyDataFormFieldResponse(key="pos_payments", label="POS Payments", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="cash_in", label="Cash Sales", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="cash_withdrawals", label="Cash Withdrawals", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="cash_out", label="Cash Out / Transfers", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="expenses_in_cash", label="Expenses in Cash", value_type="number", placeholder="0.00", section="cash_tracking"),
                        DailyDataFormFieldResponse(key="lunch_covers", label="Lunch Coperti", value_type="integer", placeholder="0", section="customer_covers"),
                        DailyDataFormFieldResponse(key="dinner_covers", label="Dinner Coperti", value_type="integer", placeholder="0", section="customer_covers"),
                        DailyDataFormFieldResponse(key="opening_cash", label="Opening Cash", value_type="number", placeholder="0.00", section="cash_register_balance"),
                        DailyDataFormFieldResponse(key="closing_cash", label="Closing Cash", value_type="number", placeholder="0.00", section="cash_register_balance"),
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
                        DailyDataFormFieldResponse(key="expenses_in_cash", label="Expenses in Cash (-)", value_type="number", placeholder="0.00", section="payment_inputs"),
                        DailyDataFormFieldResponse(key="lunch_covers", label="Lunch Coperti", value_type="integer", placeholder="0", section="customer_covers"),
                        DailyDataFormFieldResponse(key="dinner_covers", label="Dinner Coperti", value_type="integer", placeholder="0", section="customer_covers"),
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
            total_expenses = round(data["expenses_in_cash"], 2)
            lunch_covers = data["lunch_covers"]
            dinner_covers = data["dinner_covers"]
            closing_cash = data["closing_cash"] if data["closing_cash"] > 0 else max(data["cash_in"] - data["cash_out"], 0)
            record_payload = {
                **data,
                "cash_collected_total": round(data["cash_in"] + data["pos_payments"], 2),
                "cash_available": max(data["cash_in"] - data["cash_out"] - data["cash_withdrawals"] - data["expenses_in_cash"], 0),
                "closing_cash": closing_cash,
            }
        else:
            if payload.method_two is None:
                raise ValidationException("method_two is required when method is method_2")
            data = payload.method_two.model_dump(mode="json")
            business_date = payload.method_two.business_date
            total_revenue = round(data["pos_payments"] + data["cash_payments"] + data["bank_transfer_payments"], 2)
            total_expenses = round(data["expenses_in_cash"], 2)
            lunch_covers = data["lunch_covers"]
            dinner_covers = data["dinner_covers"]
            expected_closing_cash = round(data["opening_cash"] + data["cash_payments"] - data["expenses_in_cash"], 2)
            cash_difference = round(data["closing_cash"] - expected_closing_cash, 2)
            cash_out = max(expected_closing_cash - data["closing_cash"], 0)
            record_payload = {
                **data,
                "cash_collected_total": round(data["cash_payments"] + data["pos_payments"], 2),
                "cash_available": max(data["cash_payments"] - cash_out - data["expenses_in_cash"], 0),
                "cash_withdrawals": 0.0,
                "cash_in": data["cash_payments"],
                "cash_out": cash_out,
                "cash_difference": cash_difference,
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
            "created_by_user_id": str(current_user["_id"]),
        }
        document = await self.daily_record_repository.create(final_payload)
        serialized_document = self.serialize(document)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="manual_entry",
            source_id=serialized_document["id"],
            transactions=self._build_daily_record_transactions(serialized_document),
        )
        await self._sync_daily_record_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            record=serialized_document,
        )
        await self._sync_daily_record_linked_cash_deposits(
            scope_id=scope_id,
            current_user=current_user,
            record=serialized_document,
        )
        await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)
        await self._send_activity_push_for_daily_record(current_user, serialized_document)
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
            total_expenses = round(data["expenses_in_cash"], 2)
            lunch_covers = data["lunch_covers"]
            dinner_covers = data["dinner_covers"]
            closing_cash = data["closing_cash"] if data["closing_cash"] > 0 else max(data["cash_in"] - data["cash_out"], 0)
            record_payload = {
                **data,
                "cash_collected_total": round(data["cash_in"] + data["pos_payments"], 2),
                "cash_available": max(data["cash_in"] - data["cash_out"] - data["cash_withdrawals"] - data["expenses_in_cash"], 0),
                "closing_cash": closing_cash,
            }
        else:
            if payload.method_two is None:
                raise ValidationException("method_two is required when method is method_2")
            data = payload.method_two.model_dump(mode="json")
            business_date = payload.method_two.business_date
            total_revenue = round(data["pos_payments"] + data["cash_payments"] + data["bank_transfer_payments"], 2)
            total_expenses = round(data["expenses_in_cash"], 2)
            lunch_covers = data["lunch_covers"]
            dinner_covers = data["dinner_covers"]
            expected_closing_cash = round(data["opening_cash"] + data["cash_payments"] - data["expenses_in_cash"], 2)
            cash_difference = round(data["closing_cash"] - expected_closing_cash, 2)
            cash_out = max(expected_closing_cash - data["closing_cash"], 0)
            record_payload = {
                **data,
                "cash_collected_total": round(data["cash_payments"] + data["pos_payments"], 2),
                "cash_available": max(data["cash_payments"] - cash_out - data["expenses_in_cash"], 0),
                "cash_withdrawals": 0.0,
                "cash_in": data["cash_payments"],
                "cash_out": cash_out,
                "cash_difference": cash_difference,
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
        serialized_updated = self.serialize(updated)
        await self._replace_transactions_for_source(
            scope_id=scope_id,
            source_kind="manual_entry",
            source_id=serialized_updated["id"],
            transactions=self._build_daily_record_transactions(serialized_updated),
        )
        await self._sync_daily_record_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            record=serialized_updated,
        )
        await self._sync_daily_record_linked_cash_deposits(
            scope_id=scope_id,
            current_user=current_user,
            record=serialized_updated,
        )
        old_business_date = existing_record.get("business_date")
        if old_business_date and str(old_business_date) != business_date.isoformat():
            await self._sync_restaurant_record(scope_id=scope_id, business_date=datetime.fromisoformat(str(old_business_date)).date(), current_user=current_user)
        await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)
        return self._to_daily_data_response(updated)

    async def list_daily_data(self, current_user: dict, *, page: int, page_size: int, view: str, reference_date: date | None) -> DailyDataListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        if view == "date":
            start_date = reference_date if reference_date is not None else None
            end_date = reference_date if reference_date is not None else None
            items, total = await self.daily_record_repository.list_by_scope(
                scope_id=scope_id,
                page=page,
                page_size=page_size,
                start_date=start_date,
                end_date=end_date,
            )
            return DailyDataListResponse(
                items=[self._to_daily_data_list_item_from_record(item) for item in items],
                **build_pagination_meta(total=total, page=page, page_size=page_size),
            )

        if view == "week":
            if reference_date is not None:
                detail = await self._get_daily_data_period_detail(current_user, view="week", reference_date=reference_date)
                return DailyDataListResponse(
                    items=[
                        DailyDataListItemResponse(
                            id=f"week:{reference_date.isoformat()}",
                            record_id=None,
                            business_date=detail.business_date,
                            total_revenue=detail.total_revenue,
                            operating_revenue=detail.operating_revenue,
                            total_expenses=detail.total_expenses,
                            operating_expenses=detail.operating_expenses,
                            invoice_document_total=detail.invoice_document_total,
                            total_covers=detail.total_covers,
                            avg_revenue_per_cover=detail.avg_revenue_per_cover,
                            created_at=datetime.now(UTC).isoformat(),
                        )
                    ],
                    **build_pagination_meta(total=1, page=page, page_size=page_size),
                )
            items, total = await self.weekly_record_repository.list_by_scope(
                scope_id=scope_id,
                page=page,
                page_size=page_size,
            )
            serialized_items = self.serialize_list(items)
            return DailyDataListResponse(
                items=[self._to_daily_data_list_item_from_snapshot(item, view="week") for item in serialized_items],
                **build_pagination_meta(total=total, page=page, page_size=page_size),
            )

        if view == "month":
            if reference_date is not None:
                detail = await self._get_daily_data_period_detail(current_user, view="month", reference_date=reference_date)
                return DailyDataListResponse(
                    items=[
                        DailyDataListItemResponse(
                            id=f"month:{reference_date.isoformat()}",
                            record_id=None,
                            business_date=detail.business_date,
                            total_revenue=detail.total_revenue,
                            operating_revenue=detail.operating_revenue,
                            total_expenses=detail.total_expenses,
                            operating_expenses=detail.operating_expenses,
                            invoice_document_total=detail.invoice_document_total,
                            total_covers=detail.total_covers,
                            avg_revenue_per_cover=detail.avg_revenue_per_cover,
                            created_at=datetime.now(UTC).isoformat(),
                        )
                    ],
                    **build_pagination_meta(total=1, page=page, page_size=page_size),
                )
            items, total = await self.monthly_record_repository.list_by_scope(
                scope_id=scope_id,
                page=page,
                page_size=page_size,
            )
            serialized_items = self.serialize_list(items)
            return DailyDataListResponse(
                items=[self._to_daily_data_list_item_from_snapshot(item, view="month") for item in serialized_items],
                **build_pagination_meta(total=total, page=page, page_size=page_size),
            )
        raise ValidationException("Unsupported daily data view.")

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
        bucket = {
            "id": f"date:{target_iso}",
            "business_date": target_iso,
            "total_revenue": round(sum(float(item.get("total_revenue", 0)) for item in buckets), 2),
            "total_expenses": round(sum(float(item.get("total_expenses", 0)) for item in buckets), 2),
            "invoice_document_total": round(sum(float(item.get("invoice_document_total", 0)) for item in buckets), 2),
            "total_covers": int(sum(int(item.get("total_covers", 0)) for item in buckets)),
            "avg_revenue_per_cover": 0.0,
            "opening_cash": round(sum(float(item.get("opening_cash", 0)) for item in buckets), 2),
            "closing_cash": round(sum(float(item.get("closing_cash", 0)) for item in buckets), 2),
            "cash_payments": round(sum(float(item.get("cash_payments", 0)) for item in buckets), 2),
            "record_id": None,
            "created_at": buckets[0].get("created_at") if buckets else datetime.now(UTC).isoformat(),
            "data_sources": [],
        }
        if bucket["total_revenue"]:
            bucket["avg_revenue_per_cover"] = round(bucket["total_revenue"] / max(bucket["total_covers"], 1), 2)
        return self._to_daily_data_detail(
            bucket,
            records=filtered_records,
            expenses=filtered_expenses,
            documents=filtered_documents,
            anchor_date=business_date,
            reference_date=business_date,
            period_start=business_date,
            period_end=business_date,
        )

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
                records=[item for item in serialized_records if item["business_date"] == bucket["business_date"]],
                expenses=[
                    item
                    for item in serialized_expenses
                    if datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date().isoformat() == bucket["business_date"]
                ],
                documents=[item for item in serialized_documents if item.get("status") == "processed" and item.get("invoice_date") == bucket["business_date"]],
                anchor_date=datetime.fromisoformat(bucket["business_date"]).date(),
                reference_date=datetime.fromisoformat(bucket["business_date"]).date(),
                period_start=datetime.fromisoformat(bucket["business_date"]).date(),
                period_end=datetime.fromisoformat(bucket["business_date"]).date(),
            )
            for bucket in buckets
        ]
        return DailyDataCollectionResponse(total=len(items), items=items)

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
        return DailyDataCollectionResponse(total=len(items), items=items)

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
            "invoice_document_total": round(sum(float(item.get("invoice_document_total", 0)) for item in buckets), 2),
            "total_covers": int(sum(int(item.get("total_covers", 0)) for item in buckets)),
            "avg_revenue_per_cover": 0.0,
            "opening_cash": round(sum(float(item.get("opening_cash", 0)) for item in buckets), 2),
            "closing_cash": round(sum(float(item.get("closing_cash", 0)) for item in buckets), 2),
            "cash_payments": round(sum(float(item.get("cash_payments", 0)) for item in buckets), 2),
            "record_id": None,
            "created_at": datetime.now(UTC).isoformat(),
            "data_sources": [],
        }
        if aggregate_bucket["total_revenue"]:
            aggregate_bucket["avg_revenue_per_cover"] = round(aggregate_bucket["total_revenue"] / max(aggregate_bucket["total_covers"], 1), 2)
        aggregate_bucket["data_sources"] = [
            DailyDataEntrySourceResponse(
                kind="uploaded_document",
                label="Uploaded documents",
                count=len(filtered_documents),
                total_amount=round(sum(float(item.get("total_amount", 0)) for item in filtered_documents), 2),
                endpoint=f"/api/v1/restaurant/documents?from_date={start_date.isoformat()}&to_date={end_date.isoformat()}",
            )
        ] if filtered_documents else []
        return self._to_daily_data_detail(
            aggregate_bucket,
            records=filtered_records,
            expenses=filtered_expenses,
            documents=filtered_documents,
            anchor_date=reference_date,
            reference_date=reference_date,
            period_start=start_date,
            period_end=end_date,
        )

    async def delete_daily_data(self, current_user: dict, record_id: str) -> None:
        if not ObjectId.is_valid(record_id):
            raise ValidationException("Only manual daily data records can be deleted from this screen.")
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        record = await self.daily_record_repository.get_scoped_by_id(record_id, scope_id)
        business_date = record.get("business_date")
        await self._delete_transactions_for_source(scope_id=scope_id, source_kind="manual_entry", source_id=str(record["_id"]))
        await self._delete_source_linked_expense(scope_id=scope_id, source_kind="manual_entry", source_id=str(record["_id"]))
        await self._delete_source_linked_cash_deposits(scope_id=scope_id, source_kind="manual_entry", source_id=str(record["_id"]))
        await self.daily_record_repository.delete(record["_id"])
        if business_date:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)

    async def delete_daily_data_collection_by_date(self, current_user: dict, business_date: date) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        target_iso = business_date.isoformat()
        daily_records, _ = await self.daily_record_repository.list_by_scope(
            scope_id=scope_id,
            page=1,
            page_size=500,
            start_date=business_date,
            end_date=business_date,
        )
        expenses, _ = await self.expense_repository.list_by_scope(
            scope_id=scope_id,
            page=1,
            page_size=500,
            start_date=business_date,
            end_date=business_date,
        )
        documents, _ = await self.document_repository.list_by_scope(
            scope_id=scope_id,
            page=1,
            page_size=500,
        )

        deleted_any = False
        for record in self.serialize_list(daily_records):
            await self._delete_transactions_for_source(scope_id=scope_id, source_kind="manual_entry", source_id=record["id"])
            await self._delete_source_linked_expense(scope_id=scope_id, source_kind="manual_entry", source_id=record["id"])
            await self._delete_source_linked_cash_deposits(scope_id=scope_id, source_kind="manual_entry", source_id=record["id"])
            await self.daily_record_repository.delete(record["id"])
            deleted_any = True

        for document in self.serialize_list(documents):
            if document.get("status") == "processed" and str(document.get("invoice_date") or "") == target_iso:
                await self.delete_document(current_user, document["id"])
                deleted_any = True

        for expense in self.serialize_list(expenses):
            if str(expense.get("source_kind") or "").lower() in {"manual_entry", "document"}:
                continue
            inventory_item_id = expense.get("source_inventory_item_id")
            if str(expense.get("source_kind") or "").lower() == "inventory" and inventory_item_id:
                await self.delete_inventory_item(current_user, str(inventory_item_id))
            else:
                await self._delete_transactions_for_source(scope_id=scope_id, source_kind="expense", source_id=expense["id"])
                await self.expense_repository.delete(expense["id"])
            deleted_any = True

        if not deleted_any:
            raise ValidationException("No deletable data found for this date.")
        await self._sync_restaurant_record(scope_id=scope_id, business_date=business_date, current_user=current_user)

    async def create_inventory_item(self, current_user: dict, payload: Any) -> InventoryItemResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        history = []
        if payload.stock_quantity:
            history.append({"kind": "purchase_record", "quantity_delta": round(payload.stock_quantity * payload.unit_price, 2), "occurred_at": datetime.now(UTC)})
            history.append({"kind": "stock_added", "quantity_delta": payload.stock_quantity, "occurred_at": datetime.now(UTC)})
        await self._upsert_inventory_category(current_user=current_user, name=payload.category)
        await self._upsert_inventory_supplier(current_user=current_user, name=payload.supplier_name)
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
        purchase_date = payload.purchase_date or datetime.now(UTC).date()
        await self._upsert_inventory_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            inventory_item_id=str(document["_id"]),
            product_name=payload.product_name,
            category=payload.category,
            stock_quantity=float(payload.stock_quantity),
            unit_price=float(payload.unit_price),
            purchase_date=purchase_date,
        )
        await self._sync_restaurant_record(scope_id=scope_id, business_date=purchase_date, current_user=current_user)
        await self._send_activity_push_for_inventory(current_user, self.serialize(document))
        await self._send_low_stock_push_if_needed(current_user, self.serialize(document))
        return self._to_inventory_item_response(document)

    async def list_inventory(self, current_user: dict, *, page: int, page_size: int, search: str | None, status: str | None, category: str | None) -> InventoryListResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, total = await self.inventory_repository.list_by_scope(scope_id=scope_id, page=page, page_size=page_size, search=search, status=status, category=category)
        serialized_items = self.serialize_list(items)
        total_inventory_value = round(sum(item["stock_quantity"] * item["unit_price"] for item in serialized_items), 2)
        return InventoryListResponse(total_inventory_value=total_inventory_value, items=[self._to_inventory_item_response(item) for item in items], **build_pagination_meta(total=total, page=page, page_size=page_size))

    async def get_inventory_value(self, current_user: dict) -> InventoryValueResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        items, _ = await self.inventory_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        serialized_items = self.serialize_list(items)
        total_inventory_value = round(sum(item["stock_quantity"] * item["unit_price"] for item in serialized_items), 2)
        return InventoryValueResponse(total_inventory_value=total_inventory_value)

    async def get_inventory_item(self, current_user: dict, item_id: str) -> InventoryDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        return self._to_inventory_detail_response(item)

    async def update_inventory_item(self, current_user: dict, item_id: str, payload: InventoryUpdateRequest) -> InventoryDetailResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        previous_purchase_date = self._safe_parse_date(item.get("purchase_date"))
        updates = payload.model_dump(exclude_none=True)
        if "purchase_date" in updates and updates["purchase_date"] is not None:
            updates["purchase_date"] = updates["purchase_date"].isoformat()
        stock_quantity = float(updates.get("stock_quantity", item.get("stock_quantity", 0)))
        alert_threshold = float(updates.get("alert_threshold", item.get("alert_threshold", 0)))
        updates["stock_status"] = self._resolve_stock_status(stock_quantity, alert_threshold)
        updated = await self.inventory_repository.update(item["_id"], updates)
        serialized_updated = self.serialize(updated)
        await self._upsert_inventory_category(current_user=current_user, name=str(serialized_updated.get("category") or ""))
        await self._upsert_inventory_supplier(current_user=current_user, name=str(serialized_updated.get("supplier_name") or ""))
        new_purchase_date = self._safe_parse_date(serialized_updated.get("purchase_date")) or previous_purchase_date or datetime.now(UTC).date()
        await self._upsert_inventory_linked_expense(
            scope_id=scope_id,
            current_user=current_user,
            inventory_item_id=item_id,
            product_name=str(serialized_updated.get("product_name") or ""),
            category=str(serialized_updated.get("category") or "Inventory"),
            stock_quantity=float(serialized_updated.get("stock_quantity", 0) or 0),
            unit_price=float(serialized_updated.get("unit_price", 0) or 0),
            purchase_date=new_purchase_date,
        )
        if previous_purchase_date is not None:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=previous_purchase_date, current_user=current_user)
        if new_purchase_date != previous_purchase_date:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=new_purchase_date, current_user=current_user)
        return self._to_inventory_detail_response(updated)

    async def delete_inventory_item(self, current_user: dict, item_id: str) -> None:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        item = await self.inventory_repository.get_scoped_by_id(item_id, scope_id)
        purchase_date = self._safe_parse_date(item.get("purchase_date"))
        deleted_expense_date = await self._delete_inventory_linked_expense(scope_id=scope_id, inventory_item_id=item_id)
        await self.inventory_repository.delete(item["_id"])
        if purchase_date is not None:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=purchase_date, current_user=current_user)
        if deleted_expense_date is not None and deleted_expense_date != purchase_date:
            await self._sync_restaurant_record(scope_id=scope_id, business_date=deleted_expense_date, current_user=current_user)

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
        serialized_updated = self.serialize(updated)
        await self._send_low_stock_push_if_needed(current_user, serialized_updated)
        return self._to_inventory_detail_response(updated)

    async def get_analytics(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
        include_insight: bool = True,
    ) -> AnalyticsOverviewResponse:
        analytics_bundle = await self._build_analytics_bundle(
            current_user,
            period=period,
            from_date=from_date,
            to_date=to_date,
            include_insight=include_insight,
        )
        return AnalyticsOverviewResponse(
            insight_banner=analytics_bundle["insight_banner"],
            revenue_total=analytics_bundle["revenue_total"],
            operating_revenue_total=analytics_bundle["revenue_total"],
            invoice_document_total=analytics_bundle["invoice_document_total"],
            revenue_change_percent=analytics_bundle["revenue_change_percent"],
            weekly_revenue=analytics_bundle["weekly_revenue"],
            metric_tiles=analytics_bundle["metric_tiles"],
            summary_stats=analytics_bundle["summary_stats"],
            revenue_comparison=analytics_bundle["revenue_comparison"],
            covers_total=analytics_bundle["covers_total"],
            covers_activity=analytics_bundle["covers_activity"],
            avg_revenue_per_cover=analytics_bundle["avg_revenue_per_cover"],
            cost_breakdown=analytics_bundle["cost_breakdown"],
            supplier_price_alerts=analytics_bundle["supplier_price_alerts"],
        )

    async def get_analytics_business_insight(
        self,
        current_user: dict,
        *,
        period: str = "weekly",
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> AnalyticsInsightBannerResponse:
        _, daily_records, expenses, _ = await self._load_analytics_dependencies(current_user)
        anchor_date = self._resolve_latest_business_date(daily_records)
        filtered_daily_records = self._filter_home_daily_records(
            daily_records,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        filtered_expenses = self._filter_home_expenses(
            expenses,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        return await self._build_analytics_insight_banner(
            current_user=current_user,
            serialized_records=filtered_daily_records,
            serialized_expenses=filtered_expenses,
        )

    async def get_analytics_metric_tiles(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsMetricTilesResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsMetricTilesResponse(period=period, items=analytics_bundle["metric_tiles"])

    async def get_analytics_revenue_trend(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsRevenueTrendResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsRevenueTrendResponse(
            period=period,
            revenue_total=analytics_bundle["revenue_total"],
            change_percent=analytics_bundle["revenue_change_percent"],
            points=analytics_bundle["weekly_revenue"],
        )

    async def get_analytics_summary_stats(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsSummaryStatsResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsSummaryStatsResponse(period=period, items=analytics_bundle["summary_stats"])

    async def get_analytics_revenue_comparison(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsRevenueComparisonResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsRevenueComparisonResponse(period=period, items=analytics_bundle["revenue_comparison"])

    async def get_analytics_activity_cost(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsActivityCostResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsActivityCostResponse(
            period=period,
            covers_activity=analytics_bundle["covers_activity"],
            cost_breakdown=analytics_bundle["cost_breakdown"],
        )

    async def get_analytics_covers_activity(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsCoversActivityResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsCoversActivityResponse(period=period, items=analytics_bundle["covers_activity"])

    async def get_analytics_cost_breakdown(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsCostBreakdownResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsCostBreakdownResponse(period=period, items=analytics_bundle["cost_breakdown"])

    async def get_analytics_supplier_alerts(self, current_user: dict, *, period: str = "weekly", from_date: date | None = None, to_date: date | None = None) -> AnalyticsSupplierAlertsResponse:
        analytics_bundle = await self._build_analytics_bundle(current_user, period=period, from_date=from_date, to_date=to_date)
        return AnalyticsSupplierAlertsResponse(period=period, items=analytics_bundle["supplier_price_alerts"])

    async def _load_analytics_dependencies(self, current_user: dict) -> tuple[str, list[dict], list[dict], list[dict]]:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        daily_records, _ = await self.record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=365)
        return scope_id, daily_records, expenses, documents

    async def _build_analytics_bundle(
        self,
        current_user: dict,
        *,
        period: str,
        from_date: date | None,
        to_date: date | None,
        include_insight: bool = True,
    ) -> dict[str, Any]:
        _, daily_records, expenses, documents = await self._load_analytics_dependencies(current_user)
        anchor_date = self._resolve_latest_business_date(daily_records)
        filtered_daily_records = self._filter_home_daily_records(
            daily_records,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )
        filtered_expenses = self._filter_home_expenses(
            expenses,
            period=period,
            from_date=from_date,
            to_date=to_date,
            anchor_date=anchor_date,
        )

        serialized_documents = [item for item in self.serialize_list(documents) if item.get("status") == "processed"]
        filtered_documents = []
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date, anchor_date=anchor_date)
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
        estimated_profit = float(context["profit_total"])
        current_revenue = round(sum(float(item.get("total_revenue", 0)) for item in serialized_records), 2)
        previous_revenue = round(current_revenue / 1.125, 2) if current_revenue else 0.0
        lunch_covers = int(sum(int(item.get("lunch_covers", 0)) for item in serialized_records))
        dinner_covers = int(sum(int(item.get("dinner_covers", 0)) for item in serialized_records))
        analytics_language = self._resolve_chat_language(current_user)
        food_cost_total = round(sum(float(item.get("amount", 0)) for item in serialized_expenses if "food" in str(item.get("category", "")).lower()), 2)
        staff_cost_total = round(sum(float(item.get("amount", 0)) for item in serialized_expenses if "staff" in str(item.get("category", "")).lower()), 2)
        revenue_base = max(float(context["revenue_total"]), 0.0)
        food_cost_percent = round((food_cost_total / revenue_base) * 100, 1) if revenue_base > 0 else 0.0
        staff_cost_percent = round((staff_cost_total / revenue_base) * 100, 1) if revenue_base > 0 else 0.0
        supplier_alerts = [
            AnalyticsSupplierAlertResponse(**item)
            for item in await self._build_revenue_monitoring_alerts(
                current_user=current_user,
                period=period,
                current_revenue=current_revenue,
                previous_revenue=previous_revenue,
                revenue_change_percent=float(context["revenue_change_percent"]),
                serialized_records=serialized_records,
            )
        ]

        return {
            "insight_banner": (
                await self._build_analytics_insight_banner(
                    current_user=current_user,
                    serialized_records=serialized_records,
                    serialized_expenses=serialized_expenses,
                )
                if include_insight
                else None
            ),
            "revenue_total": float(context["revenue_total"]),
            "invoice_document_total": round(sum(float(item.get("total_amount", 0)) for item in filtered_documents), 2),
            "revenue_change_percent": float(context["revenue_change_percent"]),
            "weekly_revenue": self._build_home_revenue_chart(filtered_daily_records, period=period, anchor_date=anchor_date),
            "metric_tiles": [
                AnalyticsMetricTileResponse(label="Estimated Profit", value=estimated_profit, change_percent=8.2),
                self._build_peak_hour_metric(
                    language=analytics_language,
                    lunch_covers=lunch_covers,
                    dinner_covers=dinner_covers,
                    fallback_records=daily_records,
                ),
            ],
            "summary_stats": [
                AnalyticsSummaryStatResponse(label="Revenue", value=context["revenue_total"]),
                AnalyticsSummaryStatResponse(label="Covers", value=context["covers_total"]),
                AnalyticsSummaryStatResponse(label="Avg Rev", value=context["avg_revenue_per_cover"]),
            ],
            "revenue_comparison": [
                AnalyticsComparisonRowResponse(label=self._analytics_current_revenue_label(period), value=current_revenue),
                AnalyticsComparisonRowResponse(label=self._analytics_previous_revenue_label(period), value=previous_revenue),
            ],
            "covers_total": int(context["covers_total"]),
            "avg_revenue_per_cover": float(context["avg_revenue_per_cover"]),
            "covers_activity": [
                AnalyticsSummaryStatResponse(label="Lunch", value=lunch_covers),
                AnalyticsSummaryStatResponse(label="Dinner", value=dinner_covers),
            ],
            "cost_breakdown": [
                AnalyticsSummaryStatResponse(label="Food Cost", value=food_cost_percent),
                AnalyticsSummaryStatResponse(label="Staff Cost", value=staff_cost_percent),
            ],
            "supplier_price_alerts": supplier_alerts,
        }

    async def list_chat_messages(self, current_user: dict) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        chat_language = self._resolve_chat_language(current_user)
        items = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=40)
        items = await self._hydrate_chat_message_translations(items)
        messages = [self._to_chat_message_response(item, language=chat_language) for item in items]
        if not messages:
            messages = [
                ChatMessageResponse(
                    id="welcome-message",
                    role="assistant",
                    sender_label="Risto AI",
                    variant="assistant",
                    message=self._build_chat_welcome_message(chat_language),
                    message_translations=self._build_localized_text(
                        en=self._build_chat_welcome_message("en"),
                        it=self._build_chat_welcome_message("it"),
                    ),
                    created_at=datetime.now(UTC).isoformat(),
                )
            ]
        return ChatConversationResponse(
            messages=messages,
        )

    async def _hydrate_chat_message_translations(self, items: list[dict]) -> list[dict]:
        hydrated: list[dict] = []
        for item in items:
            current = item
            updates: dict[str, Any] = {}
            serialized = self.serialize(item)

            if str(serialized.get("role") or "") in {"assistant", "insight"} and not serialized.get("message_translations"):
                original_message = str(serialized.get("message") or "").strip()
                if original_message:
                    translated_en, translated_it = await asyncio.gather(
                        self.openai_service.translate_text(text=original_message, target_language="en"),
                        self.openai_service.translate_text(text=original_message, target_language="it"),
                    )
                    updates["message_translations"] = self._build_localized_text(
                        en=translated_en,
                        it=translated_it,
                    )

            if serialized.get("attachment_summary") and not serialized.get("attachment_summary_translations"):
                original_summary = str(serialized.get("attachment_summary") or "").strip()
                if original_summary:
                    translated_en, translated_it = await asyncio.gather(
                        self.openai_service.translate_text(text=original_summary, target_language="en"),
                        self.openai_service.translate_text(text=original_summary, target_language="it"),
                    )
                    updates["attachment_summary_translations"] = self._build_localized_text(
                        en=translated_en,
                        it=translated_it,
                    )

            if updates:
                current = await self.chat_repository.update(item["_id"], updates)

            hydrated.append(current)

        return hydrated

    async def create_chat_message(self, current_user: dict, payload: ChatMessageCreateRequest) -> ChatConversationResponse:
        return await self._create_chat_conversation(current_user=current_user, payload=payload)

    async def transcribe_chat_voice(
        self,
        current_user: dict,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        language: str | None = None,
    ) -> str:
        if not file_bytes:
            raise ValidationException("Voice recording is empty")

        transcript = await self.openai_service.transcribe_audio(
            file_name=file_name,
            content_type=content_type,
            file_bytes=file_bytes,
            language=self._resolve_chat_language(current_user, language),
        )
        if not transcript:
            raise ValidationException("Could not transcribe this voice message. Please try again.")
        return transcript

    async def _load_chat_generation_context(self, *, scope_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        recent_task = self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=8)
        daily_records_task = self.record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=14)
        expenses_task = self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=14)
        recent, daily_records_result, expenses_result = await asyncio.gather(
            recent_task,
            daily_records_task,
            expenses_task,
        )
        daily_records, _ = daily_records_result
        expenses, _ = expenses_result
        metrics_context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
        return recent, metrics_context

    async def update_chat_message(self, current_user: dict, message_id: str, payload: ChatMessageUpdateRequest) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        chat_language = self._resolve_chat_language(current_user, payload.language)
        if not message_id:
            raise ValidationException("message_id is required")
        existing = await self.chat_repository.get_by_scope_and_id(scope_id=scope_id, message_id=message_id)
        if existing.get("role") != "user":
            raise ValidationException("Only user messages can be edited")

        now = datetime.now(UTC)
        updated_message = await self.chat_repository.update(
            existing["_id"],
            {
                "message": payload.message,
                "message_translations": None,
                "edited_at": now,
                "last_edited_by_user_id": str(current_user["_id"]),
            },
        )
        recent, metrics_context = await self._load_chat_generation_context(scope_id=scope_id)
        recent_context = [self._serialize_chat_message_for_context(item, language=chat_language) for item in recent]
        alternate_chat_language = "it" if chat_language == "en" else "en"
        assistant_text = await self.openai_service.generate_chat_reply(
            prompt=payload.message,
            language=chat_language,
            metrics_context=metrics_context,
            recent_messages=recent_context,
        )
        alternate_assistant_text = await self.openai_service.generate_chat_reply(
            prompt=payload.message,
            language=alternate_chat_language,
            metrics_context=metrics_context,
            recent_messages=[self._serialize_chat_message_for_context(item, language=alternate_chat_language) for item in recent],
        )
        await self.chat_repository.create(
            {
                "tenant_id": scope_id,
                "role": "assistant",
                "message": assistant_text,
                "message_translations": self._build_localized_text(
                    en=assistant_text if chat_language == "en" else alternate_assistant_text,
                    it=assistant_text if chat_language == "it" else alternate_assistant_text,
                ),
                "created_by_user_id": str(current_user["_id"]),
                "reply_to_message_id": str(updated_message["_id"]),
                "regenerated_from_message_id": str(updated_message["_id"]),
            }
        )
        return await self.list_chat_messages(current_user)

    async def create_chat_message_with_attachment(
        self,
        current_user: dict,
        *,
        payload: ChatMessageCreateRequest,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        raw_file: Any | None = None,
    ) -> ChatConversationResponse:
        if not file_bytes:
            raise ValidationException("Uploaded chat attachment is empty")
        chat_language = self._resolve_chat_language(current_user, payload.language)

        final_attachment_source = payload.attachment_source
        if raw_file and content_type.startswith("image/") and self.image_storage_service:
            try:
                raw_file.file.seek(0)
                uploaded = await self.image_storage_service.upload_file(
                    file=raw_file,
                    prefix=f"restaurant/chat/{current_user['_id']}",
                )
                final_attachment_source = uploaded.url
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to upload image attachment: {e}")

        attachment_context = await self.openai_service.summarize_chat_attachment(
            file_name=file_name,
            content_type=content_type,
            file_bytes=file_bytes,
            language=chat_language,
        )
        alternate_chat_language = "it" if chat_language == "en" else "en"
        alternate_attachment_context = await self.openai_service.summarize_chat_attachment(
            file_name=file_name,
            content_type=content_type,
            file_bytes=file_bytes,
            language=alternate_chat_language,
        )
        return await self._create_chat_conversation(
            current_user=current_user,
            payload=payload,
            attachment_name=file_name,
            attachment_source=final_attachment_source,
            attachment_summary=attachment_context.get("summary"),
            attachment_summary_translations=self._build_localized_text(
                en=str(attachment_context.get("summary") or "")
                if chat_language == "en"
                else str(alternate_attachment_context.get("summary") or ""),
                it=str(attachment_context.get("summary") or "")
                if chat_language == "it"
                else str(alternate_attachment_context.get("summary") or ""),
            ),
            attachment_context=attachment_context,
            alternate_attachment_context=alternate_attachment_context,
        )

    async def _create_chat_conversation(
        self,
        *,
        current_user: dict,
        payload: ChatMessageCreateRequest,
        attachment_name: str | None = None,
        attachment_source: str | None = None,
        attachment_summary: str | None = None,
        attachment_summary_translations: dict[str, str] | None = None,
        attachment_context: dict[str, Any] | None = None,
        alternate_attachment_context: dict[str, Any] | None = None,
    ) -> ChatConversationResponse:
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        chat_language = self._resolve_chat_language(current_user, payload.language)
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
            user_message_payload["attachment_summary_translations"] = attachment_summary_translations
        user_message = await self.chat_repository.create(user_message_payload)
        recent, metrics_context = await self._load_chat_generation_context(scope_id=scope_id)
        recent_context = [self._serialize_chat_message_for_context(item, language=chat_language) for item in recent]
        alternate_chat_language = "it" if chat_language == "en" else "en"
        assistant_text = await self.openai_service.generate_chat_reply(
            prompt=payload.message,
            language=chat_language,
            metrics_context=metrics_context,
            recent_messages=recent_context,
            attachment_context=attachment_context,
        )
        alternate_assistant_text = await self.openai_service.generate_chat_reply(
            prompt=payload.message,
            language=alternate_chat_language,
            metrics_context=metrics_context,
            recent_messages=[self._serialize_chat_message_for_context(item, language=alternate_chat_language) for item in recent],
            attachment_context=alternate_attachment_context or attachment_context,
        )
        insight_message = self._build_chat_insight_message(metrics_context, language=chat_language)
        alternate_insight_message = self._build_chat_insight_message(metrics_context, language=alternate_chat_language)
        await asyncio.gather(
            self.chat_repository.create(
                {
                    "tenant_id": scope_id,
                    "role": "insight",
                    "message": insight_message,
                    "message_translations": self._build_localized_text(
                        en=insight_message if chat_language == "en" else alternate_insight_message,
                        it=insight_message if chat_language == "it" else alternate_insight_message,
                    ),
                    "created_by_user_id": str(current_user["_id"]),
                    "reply_to_message_id": str(user_message["_id"]),
                }
            ),
            self.chat_repository.create(
                {
                    "tenant_id": scope_id,
                    "role": "assistant",
                    "message": assistant_text,
                    "message_translations": self._build_localized_text(
                        en=assistant_text if chat_language == "en" else alternate_assistant_text,
                        it=assistant_text if chat_language == "it" else alternate_assistant_text,
                    ),
                    "created_by_user_id": str(current_user["_id"]),
                    "reply_to_message_id": str(user_message["_id"]),
                }
            ),
        )
        items = await self.chat_repository.list_recent_by_scope(scope_id=scope_id, limit=40)
        return ChatConversationResponse(
            messages=[self._to_chat_message_response(item, language=chat_language) for item in items],
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
        onboarding_profile = None
        if self.onboarding_repository is not None:
            onboarding_profile = await self.onboarding_repository.get_by_user_id(str(current_user["_id"]))
        preferred_language = serialized.get("preferred_language", "en")
        location = serialized.get("city_location") or serialized.get("location")
        restaurant_name = serialized.get("restaurant_name")
        profile_image_url = (
            serialized.get("profile_image_url")
            or (onboarding_profile or {}).get("profile_image_url")
            or serialized.get("avatar_url")
        )
        return RestaurantProfileResponse(
            full_name=serialized["full_name"],
            email=serialized["email"],
            phone=serialized.get("phone"),
            restaurant_name=restaurant_name,
            restaurant_type=serialized.get("restaurant_type"),
            location=serialized.get("location"),
            city_location=location,
            number_of_seats=serialized.get("number_of_seats"),
            average_spend_per_customer=serialized.get("average_spend_per_customer"),
            main_business_goal=serialized.get("main_business_goal"),
            biggest_problem=serialized.get("biggest_problem"),
            improvement_focus=serialized.get("improvement_focus"),
            preferred_language=preferred_language,
            profile_image_url=self._resolve_profile_image_url(profile_image_url),
            interior_photo_url=self._resolve_profile_image_url(
                (onboarding_profile or {}).get("interior_photo_url")
            ),
            exterior_photo_url=self._resolve_profile_image_url(
                (onboarding_profile or {}).get("exterior_photo_url")
            ),
        )

    async def update_profile(self, current_user: dict, payload: RestaurantProfileUpdateRequest) -> RestaurantProfileResponse:
        updates = payload.model_dump(exclude_none=True)
        if "city_location" in updates and "location" not in updates:
            updates["location"] = updates["city_location"]
        if "location" in updates and "city_location" not in updates:
            updates["city_location"] = updates["location"]
        user = current_user if not updates else await self.user_repository.update(current_user["_id"], updates)
        return await self.get_profile(user)

    async def update_profile_with_image(
        self,
        current_user: dict,
        payload: RestaurantProfileUpdateRequest,
        *,
        profile_image: UploadFile | None = None,
    ) -> RestaurantProfileResponse:
        updates = payload.model_dump(exclude_none=True)
        if "city_location" in updates and "location" not in updates:
            updates["location"] = updates["city_location"]
        if "location" in updates and "city_location" not in updates:
            updates["city_location"] = updates["location"]
        if "profile_image_url" in updates and "avatar_url" not in updates:
            updates["avatar_url"] = updates["profile_image_url"]
        if profile_image:
            uploaded_image = await self._upload_profile_image(current_user, profile_image)
            updates["profile_image_url"] = uploaded_image
            updates["avatar_url"] = uploaded_image
        user = current_user if not updates else await self.user_repository.update(current_user["_id"], updates)
        return await self.get_profile(user)

    async def remove_profile_image(self, current_user: dict) -> RestaurantProfileResponse:
        user = await self.user_repository.update(
            current_user["_id"],
            {
                "profile_image_url": None,
                "avatar_url": None,
            },
        )
        return await self.get_profile(user)

    async def get_settings_subscription(self, current_user: dict) -> RestaurantSettingsSubscriptionResponse:
        serialized = self.serialize(current_user)
        return RestaurantSettingsSubscriptionResponse(
            selection_required=not bool(serialized.get("subscription_plan_name")),
            plan_name=serialized.get("subscription_plan_name"),
            billing_cycle=serialized.get("subscription_plan"),
            status=serialized.get("subscription_status"),
            started_at=serialized.get("subscription_started_at"),
            expires_at=serialized.get("subscription_expires_at"),
        )

    async def get_notification_settings(self, current_user: dict) -> RestaurantNotificationSettingsResponse:
        serialized = self.serialize(current_user)
        settings = serialized.get("notification_settings") or {}
        return RestaurantNotificationSettingsResponse(**settings)

    async def update_notification_settings(
        self,
        current_user: dict,
        payload: RestaurantNotificationSettingsUpdateRequest,
    ) -> RestaurantNotificationSettingsResponse:
        existing = await self.get_notification_settings(current_user)
        merged = existing.model_dump() | payload.model_dump(exclude_none=True)
        await self.user_repository.update(current_user["_id"], {"notification_settings": merged})
        return RestaurantNotificationSettingsResponse(**merged)

    async def register_push_device(self, current_user: dict, payload: PushDeviceRegistrationRequest) -> MessageResponse:
        serialized = self.serialize(current_user)
        existing_devices = serialized.get("push_devices") or []
        now = datetime.now(UTC)
        next_devices: list[dict[str, Any]] = []
        for item in existing_devices:
            if not isinstance(item, dict):
                continue
            same_device = str(item.get("device_id") or "") == payload.device_id
            same_token = str(item.get("expo_push_token") or "") == payload.expo_push_token
            if same_device or same_token:
                continue
            next_devices.append(item)
        next_devices.append(
            {
                "device_id": payload.device_id,
                "expo_push_token": payload.expo_push_token,
                "platform": payload.platform,
                "device_name": payload.device_name,
                "last_registered_at": now,
                "updated_at": now,
            }
        )
        await self.user_repository.update(current_user["_id"], {"push_devices": next_devices})
        return MessageResponse(message="Push device registered")

    async def unregister_push_device(self, current_user: dict, payload: PushDeviceUnregisterRequest) -> MessageResponse:
        serialized = self.serialize(current_user)
        existing_devices = serialized.get("push_devices") or []
        next_devices = [
            item
            for item in existing_devices
            if isinstance(item, dict) and str(item.get("device_id") or "") != payload.device_id
        ]
        await self.user_repository.update(current_user["_id"], {"push_devices": next_devices})
        return MessageResponse(message="Push device unregistered")

    async def change_password(self, current_user: dict, payload: RestaurantChangePasswordRequest) -> MessageResponse:
        if not password_manager.verify_password(payload.current_password, current_user["hashed_password"]):
            raise ValidationException("Current password is incorrect")
        if payload.current_password == payload.new_password:
            raise ValidationException("New password must be different from current password")
        await self.user_repository.update(
            current_user["_id"],
            {"hashed_password": password_manager.hash_password(payload.new_password)},
        )
        return MessageResponse(message="Password changed successfully")

    async def _get_or_generate_insights(
        self,
        *,
        current_user: dict,
        scope_id: str,
        daily_records: list[dict],
        expenses: list[dict],
        documents: list[dict] | None = None,
        cash_deposits: list[dict] | None = None,
        inventory_items: list[dict] | None = None,
        transactions: list[dict] | None = None,
    ) -> list[InsightSummaryResponse]:
        insights = await self.insight_repository.list_by_scope(scope_id=scope_id, limit=10)
        context = self._build_metrics_context(daily_records=daily_records, expenses=expenses)
        insight_language = self._resolve_chat_language(current_user)
        trend = self._build_weekly_revenue_chart(daily_records)
        realtime_context = self._build_realtime_insight_context(
            metrics_context=context,
            daily_records=daily_records,
            expenses=expenses,
            documents=documents or [],
            cash_deposits=cash_deposits or [],
            inventory_items=inventory_items or [],
            transactions=transactions or [],
            trend=trend,
        )
        fallback_insight_en = self._build_fallback_restaurant_insight(context, language="en")
        fallback_insight_it = self._build_fallback_restaurant_insight(context, language="it")
        insight_payload_en = await self.openai_service.generate_restaurant_insight(
            metrics_context=realtime_context,
            fallback_insight=fallback_insight_en,
            language="en",
        )
        insight_payload_it = await self.openai_service.generate_restaurant_insight(
            metrics_context=realtime_context,
            fallback_insight=fallback_insight_it,
            language="it",
        )
        primary_payload = insight_payload_it if insight_language == "it" else insight_payload_en
        insight_payload = {
            **primary_payload,
            "title_translations": self._build_localized_text(
                en=str(insight_payload_en.get("title") or ""),
                it=str(insight_payload_it.get("title") or ""),
            ),
            "summary_translations": self._build_localized_text(
                en=str(insight_payload_en.get("summary") or ""),
                it=str(insight_payload_it.get("summary") or ""),
            ),
            "metric_caption_translations": self._build_localized_text(
                en=str(insight_payload_en.get("metric_caption") or ""),
                it=str(insight_payload_it.get("metric_caption") or ""),
            ),
            "root_causes_translations": self._build_localized_list(
                en=[str(item) for item in insight_payload_en.get("root_causes", [])],
                it=[str(item) for item in insight_payload_it.get("root_causes", [])],
            ),
            "recommended_actions_translations": self._build_localized_actions(
                en=[
                    {
                        "title": str(action.get("title") or ""),
                        "description": str(action.get("description") or ""),
                    }
                    for action in insight_payload_en.get("recommended_actions", [])
                    if isinstance(action, dict)
                ],
                it=[
                    {
                        "title": str(action.get("title") or ""),
                        "description": str(action.get("description") or ""),
                    }
                    for action in insight_payload_it.get("recommended_actions", [])
                    if isinstance(action, dict)
                ],
            ),
        }
        insight_payload.update(
            {
                "tenant_id": scope_id,
                "trend": [item.model_dump(mode="json") for item in trend],
                "related_metrics": [
                    {
                        "label": "Profitto" if insight_language == "it" else "Profit",
                        "value": context["profit_total"],
                        "change_percent": context["profit_change_percent"],
                        "currency": "EUR",
                    },
                    {
                        "label": "Spese" if insight_language == "it" else "Expenses",
                        "value": context["expenses_total"],
                        "change_percent": context["expense_change_percent"],
                        "currency": "EUR",
                    },
                ],
                "ai_provider": "openai" if self.openai_service.enabled else "fallback",
                "generated_at": datetime.now(UTC).isoformat(),
            }
        )
        if insights:
            insights = [await self.insight_repository.update(insights[0]["_id"], insight_payload)]
        else:
            insights = [await self.insight_repository.create(insight_payload)]
        serialized = self.serialize_list(insights)
        return [
            InsightSummaryResponse(
                id=item["id"],
                title=item["title"],
                summary=item["summary"],
                priority=item["priority"],
                metric_value=item["metric_value"],
                metric_caption=item["metric_caption"],
                title_translations=item.get("title_translations"),
                summary_translations=item.get("summary_translations"),
                metric_caption_translations=item.get("metric_caption_translations"),
            )
            for item in serialized
        ]

    def _build_metrics_context(self, *, daily_records: list[dict], expenses: list[dict]) -> dict[str, float | int]:
        today = datetime.now(UTC).date()
        last_7_start = today - timedelta(days=6)
        prev_7_start = today - timedelta(days=13)
        prev_7_end = today - timedelta(days=7)
        serialized_records = self.serialize_list(daily_records)
        serialized_expenses = self.serialize_list(expenses)
        revenue_total = round(sum(item["total_revenue"] for item in serialized_records), 2)
        expenses_total = round(sum(float(item.get("total_expenses", 0)) for item in serialized_records), 2)
        food_cost_total = round(sum(item["amount"] for item in serialized_expenses if "food" in item["category"].lower() or "inventory" in item["category"].lower()), 2)
        profit_total = round(sum(float(item.get("profit", 0)) for item in serialized_records), 2)
        covers_total = sum(int(item.get("total_covers", item.get("lunch_covers", 0) + item.get("dinner_covers", 0))) for item in serialized_records)
        recent_revenue = sum(float(item.get("total_revenue", 0)) for item in serialized_records if item["business_date"] >= last_7_start.isoformat())
        previous_revenue = sum(float(item.get("total_revenue", 0)) for item in serialized_records if prev_7_start.isoformat() <= item["business_date"] <= prev_7_end.isoformat())
        recent_food_cost = sum(item["amount"] for item in serialized_expenses if item["expense_date"][:10] >= last_7_start.isoformat() and ("food" in item["category"].lower() or "inventory" in item["category"].lower()))
        previous_food_cost = sum(item["amount"] for item in serialized_expenses if prev_7_start.isoformat() <= item["expense_date"][:10] <= prev_7_end.isoformat() and ("food" in item["category"].lower() or "inventory" in item["category"].lower()))
        recent_expenses = sum(float(item.get("total_expenses", 0)) for item in serialized_records if item["business_date"] >= last_7_start.isoformat())
        previous_expenses = sum(float(item.get("total_expenses", 0)) for item in serialized_records if prev_7_start.isoformat() <= item["business_date"] <= prev_7_end.isoformat())
        recent_profit = sum(float(item.get("profit", 0)) for item in serialized_records if item["business_date"] >= last_7_start.isoformat())
        previous_profit = sum(float(item.get("profit", 0)) for item in serialized_records if prev_7_start.isoformat() <= item["business_date"] <= prev_7_end.isoformat())
        cash_available = self._calculate_cash_available_flow(serialized_records)
        cash_deposit_total = round(
            sum(
                float(item.get("bank_deposits_total", item.get("deposits_collection_total", 0)) or 0)
                for item in serialized_records
            ),
            2,
        )
        cash_collected_total = round(cash_available + cash_deposit_total, 2)
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

    def _build_peak_hour_metric(
        self,
        *,
        language: str,
        lunch_covers: int,
        dinner_covers: int,
        fallback_records: list[dict] | None = None,
    ) -> AnalyticsMetricTileResponse:
        total_covers = max(lunch_covers + dinner_covers, 0)
        subtitle_suffix = ""
        if total_covers <= 0 and fallback_records:
            latest_cover_record = self._find_latest_record_with_cover_data(fallback_records)
            if latest_cover_record is not None:
                lunch_covers = int(latest_cover_record.get("lunch_covers", 0) or 0)
                dinner_covers = int(latest_cover_record.get("dinner_covers", 0) or 0)
                total_covers = max(lunch_covers + dinner_covers, 0)
                subtitle_suffix = (
                    " using latest available record"
                    if language != "it"
                    else " usando l'ultimo dato disponibile"
                )

        if total_covers <= 0:
            return AnalyticsMetricTileResponse(
                label="Peak Hour",
                value="N/A",
                subtitle="No cover data yet" if language != "it" else "Nessun dato coperti",
            )

        is_dinner_peak = dinner_covers >= lunch_covers
        peak_covers = dinner_covers if is_dinner_peak else lunch_covers
        peak_share = round((peak_covers / total_covers) * 100)
        peak_service = "Dinner" if is_dinner_peak else "Lunch"

        return AnalyticsMetricTileResponse(
            label="Peak Hour",
            value="Cena" if language == "it" and is_dinner_peak else "Pranzo" if language == "it" else peak_service,
            subtitle=(
                f"{peak_covers} covers, {peak_share}% of this period{subtitle_suffix}"
                if language != "it"
                else f"{peak_covers} coperti, {peak_share}% del periodo{subtitle_suffix}"
            ),
        )

    def _build_realtime_insight_context(
        self,
        *,
        metrics_context: dict[str, Any],
        daily_records: list[dict],
        expenses: list[dict],
        documents: list[dict],
        cash_deposits: list[dict],
        inventory_items: list[dict],
        transactions: list[dict],
        trend: list[ChartPointResponse],
    ) -> dict[str, Any]:
        serialized_records = self.serialize_list(daily_records)
        serialized_expenses = self.serialize_list(expenses)
        serialized_documents = self.serialize_list(documents)
        serialized_cash_deposits = self.serialize_list(cash_deposits)
        serialized_inventory = self.serialize_list(inventory_items)
        serialized_transactions = self.serialize_list(transactions)

        expense_by_category: dict[str, float] = {}
        for item in serialized_expenses:
            category = str(item.get("category") or "Uncategorized").strip() or "Uncategorized"
            expense_by_category[category] = round(expense_by_category.get(category, 0.0) + float(item.get("amount", 0)), 2)

        document_spend_by_counterparty: dict[str, float] = {}
        processed_document_count = 0
        for item in serialized_documents:
            if item.get("status") == "processed":
                processed_document_count += 1
            counterparty = str(item.get("counterparty_name") or item.get("supplier_name") or item.get("source_file_name") or "Unknown").strip() or "Unknown"
            document_spend_by_counterparty[counterparty] = round(document_spend_by_counterparty.get(counterparty, 0.0) + float(item.get("total_amount", 0)), 2)

        transaction_totals: dict[str, float] = {}
        for item in serialized_transactions:
            transaction_type = str(item.get("transaction_type") or "unknown").strip() or "unknown"
            transaction_totals[transaction_type] = round(transaction_totals.get(transaction_type, 0.0) + float(item.get("amount", 0)), 2)

        low_stock_items = [
            {
                "product_name": item.get("product_name"),
                "category": item.get("category"),
                "stock_quantity": float(item.get("stock_quantity", 0)),
                "alert_threshold": float(item.get("alert_threshold", 0)),
                "supplier_name": item.get("supplier_name"),
            }
            for item in serialized_inventory
            if str(item.get("stock_status", "")).lower() in {"low_stock", "out_of_stock"}
            or float(item.get("stock_quantity", 0)) <= float(item.get("alert_threshold", 0))
        ][:5]

        latest_business_date = max((str(item.get("business_date") or item.get("period_start_date") or "") for item in serialized_records), default="")
        latest_invoice_date = max((str(item.get("invoice_date") or "") for item in serialized_documents), default="")
        latest_cash_deposit_date = max((str(item.get("deposit_date") or "") for item in serialized_cash_deposits), default="")
        cash_deposit_total = round(sum(float(item.get("amount", 0)) for item in serialized_cash_deposits), 2)

        return {
            **metrics_context,
            "generated_at": datetime.now(UTC).isoformat(),
            "data_sources": {
                "daily_records": len(serialized_records),
                "expenses": len(serialized_expenses),
                "documents": len(serialized_documents),
                "processed_documents": processed_document_count,
                "cash_deposits": len(serialized_cash_deposits),
                "inventory_items": len(serialized_inventory),
                "finance_transactions": len(serialized_transactions),
            },
            "latest_dates": {
                "business_date": latest_business_date,
                "invoice_date": latest_invoice_date,
                "cash_deposit_date": latest_cash_deposit_date,
            },
            "weekly_revenue_trend": [item.model_dump(mode="json") for item in trend],
            "top_expense_categories": self._top_totals(expense_by_category, limit=5, key_name="category"),
            "top_document_counterparties": self._top_totals(document_spend_by_counterparty, limit=5, key_name="counterparty"),
            "cash_deposit_total": cash_deposit_total,
            "transaction_totals": transaction_totals,
            "low_stock_items": low_stock_items,
        }

    @staticmethod
    def _top_totals(values: dict[str, float], *, limit: int, key_name: str) -> list[dict[str, float | str]]:
        return [
            {key_name: key, "amount": amount}
            for key, amount in sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]

    def _filter_home_documents(
        self,
        documents: list[dict],
        *,
        period: str,
        from_date: date | None = None,
        to_date: date | None = None,
        anchor_date: date | None = None,
    ) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date, anchor_date=anchor_date)
        records = self.serialize_list(documents)
        filtered: list[dict] = []
        for item in records:
            if item.get("status") != "processed" or not item.get("invoice_date"):
                continue
            invoice_date = self._safe_parse_date(item.get("invoice_date"))
            if invoice_date is None:
                continue
            if start_date is not None and invoice_date < start_date:
                continue
            if end_date is not None and invoice_date > end_date:
                continue
            filtered.append(item)
        return filtered

    async def _sync_restaurant_record(self, *, scope_id: str, business_date: date, current_user: dict) -> None:
        resolved_business_date = business_date if hasattr(business_date, "isoformat") else datetime.fromisoformat(str(business_date)).date()
        all_daily_records, _ = await self.daily_record_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_expenses, _ = await self.expense_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_documents, _ = await self.document_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_deposits, _ = await self.cash_repository.list_by_scope(scope_id=scope_id, page=1, page_size=500)
        all_transactions, _ = await self.finance_transaction_repository.list_by_scope(scope_id=scope_id, page=1, page_size=2000)

        target_date = resolved_business_date.isoformat()
        serialized_daily_records = self.serialize_list(all_daily_records)
        serialized_expenses = self.serialize_list(all_expenses)
        serialized_documents = self.serialize_list(all_documents)
        serialized_deposits = self.serialize_list(all_deposits)
        serialized_transactions = self.serialize_list(all_transactions)

        manual_records = [
            item
            for item in serialized_daily_records
            if str(item.get("business_date", "")).startswith(target_date)
        ]
        manual_expenses = [
            item
            for item in serialized_expenses
            if datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date().isoformat() == target_date
            and str(item.get("source_kind") or "").lower() not in {"manual_entry", "document"}
        ]
        uploaded_documents = [
            item
            for item in serialized_documents
            if item.get("status") == "processed" and str(item.get("invoice_date", "")).startswith(target_date)
        ]
        deposits = [
            item
            for item in serialized_deposits
            if str(item.get("deposit_date", "")).startswith(target_date)
        ]
        finance_transactions = [
            item
            for item in serialized_transactions
            if str(item.get("business_date", "")).startswith(target_date)
        ]

        now = datetime.now(UTC)
        if not manual_records and not manual_expenses and not uploaded_documents and not deposits:
            existing = await self.record_repository.find_by_business_date(scope_id=scope_id, business_date=resolved_business_date)
            if existing:
                await self.record_repository.delete(existing["_id"])
        else:
            snapshot = build_aggregate_snapshot(
                manual_records=manual_records,
                finance_transactions=finance_transactions,
            )
            primary_manual_record = manual_records[0] if manual_records else None

            await self.record_repository.upsert_by_business_date(
                scope_id=scope_id,
                business_date=resolved_business_date,
                payload={
                    "manual_entry_id": primary_manual_record.get("id") if primary_manual_record else None,
                    "manual_entry_ids": [item["id"] for item in manual_records],
                    "manual_entry_count": len(manual_records),
                    "manual_method": primary_manual_record.get("method") if primary_manual_record else None,
                    "manual_revenue": snapshot["revenue_summary"]["manual_entry_sales_total"],
                    "manual_entry_expenses": snapshot["manual_entry_expenses"],
                    "uploaded_document_total": snapshot["uploaded_document_total"],
                    "uploaded_document_count": len(uploaded_documents),
                    "uploaded_document_ids": [item["id"] for item in uploaded_documents],
                    "manual_expense_total": snapshot["manual_expense_total"],
                    "manual_expense_cash_total": snapshot["manual_expense_cash_total"],
                    "manual_expense_count": len(manual_expenses),
                    "manual_expense_ids": [item["id"] for item in manual_expenses],
                    "bank_deposits_total": snapshot["bank_deposits_total"],
                    "cash_deposits_total": snapshot["cash_deposits_total"],
                    "deposits_collection_total": snapshot["deposits_collection_total"],
                    "bank_deposit_count": len(deposits),
                    "bank_deposit_ids": [item["id"] for item in deposits],
                    "cash_collected_total": snapshot["cash_collected_total"],
                    "pos_payments_total": snapshot["pos_payments_total"],
                    "base_cash_available": snapshot["base_cash_available"],
                    "cash_available": snapshot["cash_available"],
                    "withdrawals_total": snapshot["withdrawals_total"],
                    "total_revenue": snapshot["total_revenue"],
                    "total_expenses": snapshot["total_expenses"],
                    "profit": snapshot["profit"],
                    "lunch_covers": snapshot["lunch_covers"],
                    "dinner_covers": snapshot["dinner_covers"],
                    "total_covers": snapshot["total_covers"],
                    "avg_revenue_per_cover": snapshot["avg_revenue_per_cover"],
                    "revenue_summary": snapshot["revenue_summary"],
                    "expense_summary": snapshot["expense_summary"],
                    "deposit_summary": snapshot["deposit_summary"],
                    "cash_summary": snapshot["cash_summary"],
                    "operations_summary": snapshot["operations_summary"],
                    "source_breakdown": {
                        "manual_entry": bool(manual_records),
                        "manual_entry_count": len(manual_records),
                        "uploaded_document_count": len(uploaded_documents),
                        "manual_expense_count": len(manual_expenses),
                        "bank_deposit_count": len(deposits),
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
            serialized_deposits=serialized_deposits,
            serialized_transactions=serialized_transactions,
            current_user=current_user,
        )
        await self._sync_restaurant_month_record(
            scope_id=scope_id,
            business_date=resolved_business_date,
            serialized_daily_records=serialized_daily_records,
            serialized_expenses=serialized_expenses,
            serialized_documents=serialized_documents,
            serialized_deposits=serialized_deposits,
            serialized_transactions=serialized_transactions,
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
        serialized_deposits: list[dict[str, Any]],
        serialized_transactions: list[dict[str, Any]],
        current_user: dict,
    ) -> None:
        week_start = business_date - timedelta(days=business_date.weekday())
        week_end = week_start + timedelta(days=6)
        weekly_manual_records = [
            item for item in serialized_daily_records if week_start <= datetime.fromisoformat(str(item["business_date"])).date() <= week_end
        ]
        weekly_expenses = [
            item
            for item in serialized_expenses
            if week_start <= datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date() <= week_end
            and str(item.get("source_kind") or "").lower() not in {"manual_entry", "document"}
        ]
        weekly_documents = [
            item
            for item in serialized_documents
            if item.get("status") == "processed"
            and item.get("invoice_date")
            and week_start <= datetime.fromisoformat(str(item["invoice_date"])).date() <= week_end
        ]
        weekly_deposits = []
        for item in serialized_deposits:
            deposit_date = self._safe_parse_date(item.get("deposit_date"))
            if deposit_date is not None and week_start <= deposit_date <= week_end:
                weekly_deposits.append(item)
        weekly_transactions = [
            item
            for item in serialized_transactions
            if item.get("business_date")
            and week_start <= datetime.fromisoformat(str(item["business_date"])).date() <= week_end
        ]
        if not weekly_manual_records and not weekly_expenses and not weekly_documents and not weekly_deposits:
            existing = await self.weekly_record_repository.find_by_week_start_date(scope_id=scope_id, week_start_date=week_start)
            if existing:
                await self.weekly_record_repository.delete(existing["_id"])
            return
        snapshot = build_aggregate_snapshot(
            manual_records=weekly_manual_records,
            finance_transactions=weekly_transactions,
        )
        await self.weekly_record_repository.upsert_by_week_start_date(
            scope_id=scope_id,
            week_start_date=week_start,
            payload={
                "week_end_date": week_end.isoformat(),
                "manual_entry_ids": [item["id"] for item in weekly_manual_records],
                "manual_expense_ids": [item["id"] for item in weekly_expenses],
                "uploaded_document_ids": [item["id"] for item in weekly_documents],
                "bank_deposit_ids": [item["id"] for item in weekly_deposits],
                "manual_revenue": snapshot["revenue_summary"]["manual_entry_sales_total"],
                "cash_collected_total": snapshot["cash_collected_total"],
                "pos_payments_total": snapshot["pos_payments_total"],
                "base_cash_available": snapshot["base_cash_available"],
                "cash_available": snapshot["cash_available"],
                "withdrawals_total": snapshot["withdrawals_total"],
                "total_revenue": snapshot["total_revenue"],
                "manual_entry_expenses": snapshot["manual_entry_expenses"],
                "manual_expense_total": snapshot["manual_expense_total"],
                "manual_expense_cash_total": snapshot["manual_expense_cash_total"],
                "uploaded_document_total": snapshot["uploaded_document_total"],
                "bank_deposits_total": snapshot["bank_deposits_total"],
                "cash_deposits_total": snapshot["cash_deposits_total"],
                "deposits_collection_total": snapshot["deposits_collection_total"],
                "total_expenses": snapshot["total_expenses"],
                "profit": snapshot["profit"],
                "total_covers": snapshot["total_covers"],
                "avg_revenue_per_cover": snapshot["avg_revenue_per_cover"],
                "revenue_summary": snapshot["revenue_summary"],
                "expense_summary": snapshot["expense_summary"],
                "deposit_summary": snapshot["deposit_summary"],
                "cash_summary": snapshot["cash_summary"],
                "operations_summary": snapshot["operations_summary"],
                "invoice_count": len(weekly_documents),
                "manual_entry_count": len(weekly_manual_records),
                "manual_expense_count": len(weekly_expenses),
                "bank_deposit_count": len(weekly_deposits),
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
        serialized_deposits: list[dict[str, Any]],
        serialized_transactions: list[dict[str, Any]],
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
            item
            for item in serialized_expenses
            if month_start <= datetime.fromisoformat(item["expense_date"].replace("Z", "+00:00")).date() <= month_end
            and str(item.get("source_kind") or "").lower() not in {"manual_entry", "document"}
        ]
        monthly_documents = [
            item
            for item in serialized_documents
            if item.get("status") == "processed"
            and item.get("invoice_date")
            and month_start <= datetime.fromisoformat(str(item["invoice_date"])).date() <= month_end
        ]
        monthly_deposits = []
        for item in serialized_deposits:
            deposit_date = self._safe_parse_date(item.get("deposit_date"))
            if deposit_date is not None and month_start <= deposit_date <= month_end:
                monthly_deposits.append(item)
        monthly_transactions = [
            item
            for item in serialized_transactions
            if item.get("business_date")
            and month_start <= datetime.fromisoformat(str(item["business_date"])).date() <= month_end
        ]
        if not monthly_manual_records and not monthly_expenses and not monthly_documents and not monthly_deposits:
            existing = await self.monthly_record_repository.find_by_month_key(scope_id=scope_id, month_key=month_key)
            if existing:
                await self.monthly_record_repository.delete(existing["_id"])
            return
        snapshot = build_aggregate_snapshot(
            manual_records=monthly_manual_records,
            finance_transactions=monthly_transactions,
        )
        await self.monthly_record_repository.upsert_by_month_key(
            scope_id=scope_id,
            month_key=month_key,
            payload={
                "month_start_date": month_start.isoformat(),
                "month_end_date": month_end.isoformat(),
                "manual_entry_ids": [item["id"] for item in monthly_manual_records],
                "manual_expense_ids": [item["id"] for item in monthly_expenses],
                "uploaded_document_ids": [item["id"] for item in monthly_documents],
                "bank_deposit_ids": [item["id"] for item in monthly_deposits],
                "manual_revenue": snapshot["revenue_summary"]["manual_entry_sales_total"],
                "cash_collected_total": snapshot["cash_collected_total"],
                "pos_payments_total": snapshot["pos_payments_total"],
                "base_cash_available": snapshot["base_cash_available"],
                "cash_available": snapshot["cash_available"],
                "withdrawals_total": snapshot["withdrawals_total"],
                "total_revenue": snapshot["total_revenue"],
                "manual_entry_expenses": snapshot["manual_entry_expenses"],
                "manual_expense_total": snapshot["manual_expense_total"],
                "manual_expense_cash_total": snapshot["manual_expense_cash_total"],
                "uploaded_document_total": snapshot["uploaded_document_total"],
                "bank_deposits_total": snapshot["bank_deposits_total"],
                "cash_deposits_total": snapshot["cash_deposits_total"],
                "deposits_collection_total": snapshot["deposits_collection_total"],
                "total_expenses": snapshot["total_expenses"],
                "profit": snapshot["profit"],
                "total_covers": snapshot["total_covers"],
                "avg_revenue_per_cover": snapshot["avg_revenue_per_cover"],
                "revenue_summary": snapshot["revenue_summary"],
                "expense_summary": snapshot["expense_summary"],
                "deposit_summary": snapshot["deposit_summary"],
                "cash_summary": snapshot["cash_summary"],
                "operations_summary": snapshot["operations_summary"],
                "invoice_count": len(monthly_documents),
                "manual_entry_count": len(monthly_manual_records),
                "manual_expense_count": len(monthly_expenses),
                "bank_deposit_count": len(monthly_deposits),
                "last_synced_by_user_id": str(current_user["_id"]),
                "last_synced_at": datetime.now(UTC),
            },
        )

    async def _build_analytics_insight_banner(
        self,
        *,
        current_user: dict,
        serialized_records: list[dict[str, Any]],
        serialized_expenses: list[dict[str, Any]],
    ) -> AnalyticsInsightBannerResponse:
        insight_language = self._resolve_chat_language(current_user)
        alternate_language = "it" if insight_language == "en" else "en"
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday_names_it = ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]
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
            weekday_name = weekday_names_it[best_weekday] if insight_language == "it" else weekday_names[best_weekday]
            group_label = (
                {"staff": "Costi del personale", "food": "Costi del cibo", "operations": "Costi operativi"}.get(best_group, "Costi")
                if insight_language == "it"
                else {"staff": "Staffing costs", "food": "Food costs", "operations": "Operating costs"}.get(best_group, "Costs")
            )
            subtitle = (
                {
                    "staff": "Controlla la pianificazione del personale rispetto alla domanda.",
                    "food": "Controlla acquisti e mix del menu per questo giorno.",
                    "operations": "Controlla costi generali e pianificazione dei turni.",
                }.get(best_group, "Controlla i principali costi di questa giornata.")
                if insight_language == "it"
                else {
                    "staff": "Review labor scheduling against demand patterns.",
                    "food": "Review purchasing and menu mix for this day.",
                    "operations": "Review overhead allocations and shift planning.",
                }.get(best_group, "Review cost drivers for this day.")
            )
            fallback_title = (
                f"Suggerimento di ottimizzazione: {group_label} sono superiori del {percent}% di {weekday_name} rispetto ai ricavi."
                if insight_language == "it"
                else f"Optimization Tip: {group_label} are {percent}% higher on {weekday_name}s relative to revenue."
            )
            fallback_subtitle = subtitle
            generated = await self.openai_service.generate_business_insight(
                analytics_context={
                    "insight_type": best_group,
                    "weekday": weekday_name,
                    "lift_percent": percent,
                    "ratio": round(best_ratio * 100, 2),
                    "revenue_by_weekday": revenue_by_weekday,
                    "costs_by_group_by_weekday": costs_by_group_by_weekday,
                },
                fallback_title=fallback_title,
                fallback_subtitle=fallback_subtitle,
                language=insight_language,
            )
            alternate_generated = await self.openai_service.generate_business_insight(
                analytics_context={
                    "insight_type": best_group,
                    "weekday": weekday_names_it[best_weekday] if alternate_language == "it" else weekday_names[best_weekday],
                    "lift_percent": percent,
                    "ratio": round(best_ratio * 100, 2),
                    "revenue_by_weekday": revenue_by_weekday,
                    "costs_by_group_by_weekday": costs_by_group_by_weekday,
                },
                fallback_title=(
                    f"Suggerimento di ottimizzazione: "
                    f"{({'staff': 'Costi del personale', 'food': 'Costi del cibo', 'operations': 'Costi operativi'}.get(best_group, 'Costi'))} "
                    f"sono superiori del {percent}% di {weekday_names_it[best_weekday]} rispetto ai ricavi."
                    if alternate_language == "it"
                    else f"Optimization Tip: "
                    f"{({'staff': 'Staffing costs', 'food': 'Food costs', 'operations': 'Operating costs'}.get(best_group, 'Costs'))} "
                    f"are {percent}% higher on {weekday_names[best_weekday]}s relative to revenue."
                ),
                fallback_subtitle=(
                    {
                        "staff": "Controlla la pianificazione del personale rispetto alla domanda.",
                        "food": "Controlla acquisti e mix del menu per questo giorno.",
                        "operations": "Controlla costi generali e pianificazione dei turni.",
                    }.get(best_group, "Controlla i principali costi di questa giornata.")
                    if alternate_language == "it"
                    else {
                        "staff": "Review labor scheduling against demand patterns.",
                        "food": "Review purchasing and menu mix for this day.",
                        "operations": "Review overhead allocations and shift planning.",
                    }.get(best_group, "Review cost drivers for this day.")
                ),
                language=alternate_language,
            )
            return AnalyticsInsightBannerResponse(
                title=generated["title"],
                subtitle=generated["subtitle"],
                ai_provider=str(generated.get("ai_provider") or "fallback"),
                title_translations=self._build_localized_text(
                    en=generated["title"] if insight_language == "en" else alternate_generated["title"],
                    it=generated["title"] if insight_language == "it" else alternate_generated["title"],
                ),
                subtitle_translations=self._build_localized_text(
                    en=generated["subtitle"] if insight_language == "en" else alternate_generated["subtitle"],
                    it=generated["subtitle"] if insight_language == "it" else alternate_generated["subtitle"],
                ),
            )

        if serialized_expenses:
            top_expense = max(serialized_expenses, key=lambda item: float(item.get("amount", 0)))
            category_name = str(top_expense.get("category", "operating"))
            fallback_title = (
                f"Suggerimento di ottimizzazione: {category_name} e il principale costo recente."
                if insight_language == "it"
                else f"Optimization Tip: {category_name} is your largest recent cost driver."
            )
            fallback_subtitle = (
                "Controlla la categoria di spesa piu alta rispetto all'andamento dei ricavi."
                if insight_language == "it"
                else "Review the largest expense category against revenue trend."
            )
            generated = await self.openai_service.generate_business_insight(
                analytics_context={
                    "insight_type": "largest_expense",
                    "category": category_name,
                    "top_expense_amount": float(top_expense.get("amount", 0)),
                },
                fallback_title=fallback_title,
                fallback_subtitle=fallback_subtitle,
                language=insight_language,
            )
            alternate_generated = await self.openai_service.generate_business_insight(
                analytics_context={
                    "insight_type": "largest_expense",
                    "category": category_name,
                    "top_expense_amount": float(top_expense.get("amount", 0)),
                },
                fallback_title=(
                    f"Suggerimento di ottimizzazione: {category_name} e il principale costo recente."
                    if alternate_language == "it"
                    else f"Optimization Tip: {category_name} is your largest recent cost driver."
                ),
                fallback_subtitle=(
                    "Controlla la categoria di spesa piu alta rispetto all'andamento dei ricavi."
                    if alternate_language == "it"
                    else "Review the largest expense category against revenue trend."
                ),
                language=alternate_language,
            )
            return AnalyticsInsightBannerResponse(
                title=generated["title"],
                subtitle=generated["subtitle"],
                ai_provider=str(generated.get("ai_provider") or "fallback"),
                title_translations=self._build_localized_text(
                    en=generated["title"] if insight_language == "en" else alternate_generated["title"],
                    it=generated["title"] if insight_language == "it" else alternate_generated["title"],
                ),
                subtitle_translations=self._build_localized_text(
                    en=generated["subtitle"] if insight_language == "en" else alternate_generated["subtitle"],
                    it=generated["subtitle"] if insight_language == "it" else alternate_generated["subtitle"],
                ),
            )

        generated = await self.openai_service.generate_business_insight(
            analytics_context={"insight_type": "insufficient_data"},
            fallback_title=(
                "Suggerimento di ottimizzazione: aggiungi piu dati giornalieri per sbloccare insight utili."
                if insight_language == "it"
                else "Optimization Tip: Add more daily data to unlock pattern-based insights."
            ),
            fallback_subtitle=(
                "Servono piu dati su ricavi e costi per generare raccomandazioni piu forti."
                if insight_language == "it"
                else "We need a bit more revenue and cost history to generate stronger recommendations."
            ),
            language=insight_language,
        )
        alternate_generated = await self.openai_service.generate_business_insight(
            analytics_context={"insight_type": "insufficient_data"},
            fallback_title=(
                "Suggerimento di ottimizzazione: aggiungi piu dati giornalieri per sbloccare insight utili."
                if alternate_language == "it"
                else "Optimization Tip: Add more daily data to unlock pattern-based insights."
            ),
            fallback_subtitle=(
                "Servono piu dati su ricavi e costi per generare raccomandazioni piu forti."
                if alternate_language == "it"
                else "We need a bit more revenue and cost history to generate stronger recommendations."
            ),
            language=alternate_language,
        )
        return AnalyticsInsightBannerResponse(
            title=generated["title"],
            subtitle=generated["subtitle"],
            ai_provider=str(generated.get("ai_provider") or "fallback"),
            title_translations=self._build_localized_text(
                en=generated["title"] if insight_language == "en" else alternate_generated["title"],
                it=generated["title"] if insight_language == "it" else alternate_generated["title"],
            ),
            subtitle_translations=self._build_localized_text(
                en=generated["subtitle"] if insight_language == "en" else alternate_generated["subtitle"],
                it=generated["subtitle"] if insight_language == "it" else alternate_generated["subtitle"],
            ),
        )

    async def _build_supplier_alerts(
        self,
        *,
        current_user: dict,
        serialized_expenses: list[dict[str, Any]],
        serialized_documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        alert_language = self._resolve_chat_language(current_user)
        alternate_language = "it" if alert_language == "en" else "en"
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
                    "title": (
                        f"I prezzi di {category} sono aumentati del {max(5, int(round(share / 2)))}%"
                        if alert_language == "it"
                        else f"{category} prices increased by {max(5, int(round(share / 2)))}%"
                    ),
                    "subtitle": (
                        f"Impatto: +{self._format_currency(impact)} di pressione mensile sui costi"
                        if alert_language == "it"
                        else f"Impact: +{self._format_currency(impact)} monthly cost pressure"
                    ),
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
            language=alert_language,
        )
        alternate_fallback_alerts: list[dict[str, str]] = []
        for category, amount in sorted_categories[:3]:
            share = round((amount / max(total_spend, 1)) * 100, 1)
            impact = round(amount * 0.1, 2)
            alternate_fallback_alerts.append(
                {
                    "title": (
                        f"I prezzi di {category} sono aumentati del {max(5, int(round(share / 2)))}%"
                        if alternate_language == "it"
                        else f"{category} prices increased by {max(5, int(round(share / 2)))}%"
                    ),
                    "subtitle": (
                        f"Impatto: +{self._format_currency(impact)} di pressione mensile sui costi"
                        if alternate_language == "it"
                        else f"Impact: +{self._format_currency(impact)} monthly cost pressure"
                    ),
                }
            )
        alternate_generated_alerts = await self.openai_service.generate_supplier_alerts(
            analytics_context={
                "total_spend": total_spend,
                "expense_count": len(serialized_expenses),
                "invoice_count": len(serialized_documents),
                "top_categories": [
                    {"category": category, "amount": amount, "share_percent": round((amount / max(total_spend, 1)) * 100, 1)}
                    for category, amount in sorted_categories[:5]
                ],
            },
            fallback_alerts=alternate_fallback_alerts,
            language=alternate_language,
        )
        localized_alerts: list[dict[str, Any]] = []
        for index, item in enumerate(generated_alerts):
            alternate_item = alternate_generated_alerts[index] if index < len(alternate_generated_alerts) else {"title": "", "subtitle": ""}
            localized_alerts.append(
                {
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "ai_provider": str(item.get("ai_provider") or "fallback"),
                    "title_translations": self._build_localized_text(
                        en=item["title"] if alert_language == "en" else str(alternate_item.get("title") or ""),
                        it=item["title"] if alert_language == "it" else str(alternate_item.get("title") or ""),
                    ),
                    "subtitle_translations": self._build_localized_text(
                        en=item["subtitle"] if alert_language == "en" else str(alternate_item.get("subtitle") or ""),
                        it=item["subtitle"] if alert_language == "it" else str(alternate_item.get("subtitle") or ""),
                    ),
                }
            )
        return localized_alerts

    async def _build_revenue_monitoring_alerts(
        self,
        *,
        current_user: dict,
        period: str,
        current_revenue: float,
        previous_revenue: float,
        revenue_change_percent: float,
        serialized_records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        alert_language = self._resolve_chat_language(current_user)
        alternate_language = "it" if alert_language == "en" else "en"
        period_label = "month" if period == "monthly" else "week"
        period_label_it = "mese" if period == "monthly" else "settimana"
        revenue_points = [
            {
                "business_date": item.get("business_date"),
                "revenue": round(float(item.get("total_revenue", 0) or 0), 2),
                "covers": int(item.get("total_covers", item.get("lunch_covers", 0) + item.get("dinner_covers", 0)) or 0),
            }
            for item in serialized_records
        ]

        if current_revenue <= 0 and not revenue_points:
            return []

        fallback_alerts_en: list[dict[str, str]] = []
        fallback_alerts_it: list[dict[str, str]] = []

        if previous_revenue > 0:
            if revenue_change_percent < -5:
                fallback_alerts_en.append(
                    {
                        "title": f"Revenue down {abs(round(revenue_change_percent, 1))}% this {period_label}",
                        "subtitle": f"Current revenue is {self._format_currency(current_revenue)} versus {self._format_currency(previous_revenue)} previously.",
                    }
                )
                fallback_alerts_it.append(
                    {
                        "title": f"Ricavi in calo del {abs(round(revenue_change_percent, 1))}% questa {period_label_it}",
                        "subtitle": f"I ricavi attuali sono {self._format_currency(current_revenue)} contro {self._format_currency(previous_revenue)} precedenti.",
                    }
                )
            elif revenue_change_percent > 5:
                fallback_alerts_en.append(
                    {
                        "title": f"Revenue up {round(revenue_change_percent, 1)}% this {period_label}",
                        "subtitle": f"Current revenue reached {self._format_currency(current_revenue)} versus {self._format_currency(previous_revenue)} previously.",
                    }
                )
                fallback_alerts_it.append(
                    {
                        "title": f"Ricavi in crescita del {round(revenue_change_percent, 1)}% questa {period_label_it}",
                        "subtitle": f"I ricavi attuali sono {self._format_currency(current_revenue)} contro {self._format_currency(previous_revenue)} precedenti.",
                    }
                )

        if revenue_points:
            lowest_point = min(revenue_points, key=lambda item: float(item["revenue"]))
            highest_point = max(revenue_points, key=lambda item: float(item["revenue"]))
            if float(highest_point["revenue"]) > 0 and float(lowest_point["revenue"]) < float(highest_point["revenue"]) * 0.5:
                fallback_alerts_en.append(
                    {
                        "title": "Revenue volatility detected",
                        "subtitle": f"Lowest day {lowest_point['business_date']} was {self._format_currency(float(lowest_point['revenue']))}, below half of the period peak.",
                    }
                )
                fallback_alerts_it.append(
                    {
                        "title": "Volatilita ricavi rilevata",
                        "subtitle": f"Il giorno piu basso {lowest_point['business_date']} e stato {self._format_currency(float(lowest_point['revenue']))}, sotto meta del picco del periodo.",
                    }
                )

        if not fallback_alerts_en:
            fallback_alerts_en.append(
                {
                    "title": "Revenue holding steady",
                    "subtitle": f"Current {period_label} revenue is {self._format_currency(current_revenue)}. Keep monitoring covers and average spend.",
                }
            )
            fallback_alerts_it.append(
                {
                    "title": "Ricavi stabili",
                    "subtitle": f"I ricavi attuali della {period_label_it} sono {self._format_currency(current_revenue)}. Continua a monitorare coperti e spesa media.",
                }
            )

        selected_fallback = fallback_alerts_it if alert_language == "it" else fallback_alerts_en
        alternate_fallback = fallback_alerts_it if alternate_language == "it" else fallback_alerts_en
        analytics_context = {
            "period": period,
            "current_revenue": current_revenue,
            "previous_revenue": previous_revenue,
            "revenue_change_percent": round(revenue_change_percent, 2),
            "revenue_points": revenue_points,
        }
        generated_alerts = await self.openai_service.generate_supplier_alerts(
            analytics_context=analytics_context,
            fallback_alerts=selected_fallback,
            language=alert_language,
        )
        alternate_generated_alerts = await self.openai_service.generate_supplier_alerts(
            analytics_context=analytics_context,
            fallback_alerts=alternate_fallback,
            language=alternate_language,
        )

        localized_alerts: list[dict[str, Any]] = []
        for index, item in enumerate(generated_alerts[:3]):
            alternate_item = alternate_generated_alerts[index] if index < len(alternate_generated_alerts) else {"title": "", "subtitle": ""}
            localized_alerts.append(
                {
                    "title": item["title"],
                    "subtitle": item["subtitle"],
                    "ai_provider": str(item.get("ai_provider") or "fallback"),
                    "title_translations": self._build_localized_text(
                        en=item["title"] if alert_language == "en" else str(alternate_item.get("title") or ""),
                        it=item["title"] if alert_language == "it" else str(alternate_item.get("title") or ""),
                    ),
                    "subtitle_translations": self._build_localized_text(
                        en=item["subtitle"] if alert_language == "en" else str(alternate_item.get("subtitle") or ""),
                        it=item["subtitle"] if alert_language == "it" else str(alternate_item.get("subtitle") or ""),
                    ),
                }
            )
        return localized_alerts

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

        # A4 landscape (96 DPI)
        width = 1123
        height = 794
        page_margin = 18
        frame_x = page_margin
        frame_y = page_margin
        frame_w = width - (page_margin * 2)
        frame_h = height - (page_margin * 2)

        header_left_x = frame_x + 34
        header_right_x = frame_x + 700
        table_x = frame_x + 34
        table_y = frame_y + 350
        table_w = frame_w - 68
        table_h = 290
        header_line_y = table_y + 52

        def truncate_text(value: Any, limit: int) -> str:
            raw = str(value or "").strip()
            if len(raw) <= limit:
                return raw
            return f"{raw[:max(limit - 3, 0)]}..."

        supplier_name = escape(truncate_text(document.get("supplier_name") or "Unknown Supplier", 30))
        invoice_number = escape(truncate_text(document.get("invoice_number") or "N/A", 16))
        invoice_date = escape(str(self._format_human_date(document.get("invoice_date")) or "-"))
        upload_date = escape(str(self._format_human_date(document.get("upload_date")) or "-"))
        total_amount = escape(self._format_currency(float(document.get("total_amount", 0))))

        max_rows = max(1, int((table_h - 78) // 56))
        visible_rows = line_items[:max_rows]
        hidden_count = max(0, len(line_items) - len(visible_rows))

        row_parts: list[str] = []
        y = table_y + 92
        for item in visible_rows:
            product_name = escape(truncate_text(item.get("product_name") or "Item", 35))
            quantity = escape(truncate_text(item.get("quantity", 0), 10))
            unit_price = escape(self._format_currency(float(item.get("unit_price", 0))))
            total_price = escape(self._format_currency(float(item.get("total_price", 0))))
            row_parts.append(
                f'<text x="{table_x + 28}" y="{y}" font-size="40" fill="#0f274b" font-family="Arial">{product_name}</text>'
                f'<text x="{table_x + 640}" y="{y}" font-size="40" fill="#6b87a6" font-family="Arial">Qty {quantity}</text>'
                f'<text x="{table_x + 830}" y="{y}" font-size="40" fill="#6b87a6" font-family="Arial">{unit_price}</text>'
                f'<text x="{table_x + table_w - 165}" y="{y}" font-size="40" fill="#0f274b" font-family="Arial" font-weight="700">{total_price}</text>'
                f'<line x1="{table_x + 16}" y1="{y + 22}" x2="{table_x + table_w - 16}" y2="{y + 22}" stroke="#e3ebf4" stroke-width="2" />'
            )
            y += 56

        hidden_svg = ""
        if hidden_count > 0:
            hidden_svg = (
                f'<text x="{table_x + 24}" y="{table_y + table_h - 18}" font-size="28" fill="#9a3412" font-family="Arial">'
                f'... {hidden_count} more item(s) not shown'
                f'</text>'
            )

        rows_svg = "".join(row_parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="100%" height="100%" fill="#f7fafc"/>'
            f'<rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" fill="none" stroke="#d6e1ee" stroke-width="3"/>'
            f'<text x="{header_left_x}" y="{frame_y + 70}" font-size="62" font-weight="700" fill="#0f274b" font-family="Arial">INVOICE</text>'
            f'<text x="{header_left_x}" y="{frame_y + 130}" font-size="32" fill="#6b87a6" font-family="Arial">Supplier</text>'
            f'<text x="{header_left_x}" y="{frame_y + 178}" font-size="52" font-weight="700" fill="#0f274b" font-family="Arial">{supplier_name}</text>'
            f'<text x="{header_right_x}" y="{frame_y + 130}" font-size="32" fill="#6b87a6" font-family="Arial">Invoice Number</text>'
            f'<text x="{header_right_x}" y="{frame_y + 178}" font-size="52" font-weight="700" fill="#0f274b" font-family="Arial">{invoice_number}</text>'
            f'<text x="{header_left_x}" y="{frame_y + 250}" font-size="32" fill="#6b87a6" font-family="Arial">Invoice Date</text>'
            f'<text x="{header_left_x}" y="{frame_y + 298}" font-size="48" font-weight="700" fill="#0f274b" font-family="Arial">{invoice_date}</text>'
            f'<text x="{header_left_x + 300}" y="{frame_y + 250}" font-size="32" fill="#6b87a6" font-family="Arial">Upload Date</text>'
            f'<text x="{header_left_x + 300}" y="{frame_y + 298}" font-size="48" font-weight="700" fill="#0f274b" font-family="Arial">{upload_date}</text>'
            f'<rect x="{header_right_x + 96}" y="{frame_y + 220}" width="265" height="96" fill="#f7efe4"/>'
            f'<text x="{header_right_x + 114}" y="{frame_y + 262}" font-size="38" fill="#b65a1e" font-family="Arial">Total Amount</text>'
            f'<text x="{header_right_x + 114}" y="{frame_y + 304}" font-size="58" font-weight="700" fill="#f97316" font-family="Arial">{total_amount}</text>'
            f'<rect x="{table_x}" y="{table_y}" width="{table_w}" height="{table_h}" fill="none" stroke="#d6e1ee" stroke-width="3"/>'
            f'<text x="{table_x + 28}" y="{table_y + 40}" font-size="34" fill="#6b87a6" font-family="Arial">PRODUCT</text>'
            f'<text x="{table_x + 640}" y="{table_y + 40}" font-size="34" fill="#6b87a6" font-family="Arial">QTY</text>'
            f'<text x="{table_x + 830}" y="{table_y + 40}" font-size="34" fill="#6b87a6" font-family="Arial">PRICE</text>'
            f'<text x="{table_x + table_w - 165}" y="{table_y + 40}" font-size="34" fill="#6b87a6" font-family="Arial">TOTAL</text>'
            f'<line x1="{table_x + 16}" y1="{header_line_y}" x2="{table_x + table_w - 16}" y2="{header_line_y}" stroke="#d6e1ee" stroke-width="2" />'
            f'{rows_svg}'
            f'{hidden_svg}'
            f'</svg>'
        )

    def _build_home_revenue_chart(
        self,
        daily_records: list[dict],
        *,
        period: str,
        anchor_date: date | None = None,
    ) -> list[ChartPointResponse]:
        if period == 'monthly':
            return self._build_monthly_revenue_chart(daily_records, anchor_date=anchor_date)
        return self._build_weekly_revenue_chart(daily_records, anchor_date=anchor_date)

    def _build_monthly_revenue_chart(self, daily_records: list[dict], *, anchor_date: date | None = None) -> list[ChartPointResponse]:
        target_date = anchor_date or datetime.now(UTC).date()
        start_date = target_date - timedelta(days=29)
        by_day: dict[str, float] = {}
        for item in self.serialize_list(daily_records):
            key = item['business_date']
            by_day[key] = by_day.get(key, 0.0) + self._resolve_home_revenue_amount(item)

        points: list[ChartPointResponse] = []
        for index in range(4):
            segment_start = start_date + timedelta(days=index * 7)
            segment_end = segment_start + timedelta(days=6)
            total = 0.0
            current = segment_start
            while current <= segment_end and current <= target_date:
                total += by_day.get(current.isoformat(), 0.0)
                current += timedelta(days=1)
            points.append(ChartPointResponse(label=f'W{index + 1}', value=round(total, 2)))
        return points

    def _filter_home_daily_records(
        self,
        daily_records: list[dict],
        *,
        period: str,
        from_date: date | None = None,
        to_date: date | None = None,
        anchor_date: date | None = None,
    ) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date, anchor_date=anchor_date)
        records = self.serialize_list(daily_records)
        if start_date is None and end_date is None:
            return records
        return [
            item for item in records
            if (start_date is None or self._safe_parse_date(item.get('business_date')) >= start_date)
            and (end_date is None or self._safe_parse_date(item.get('business_date')) <= end_date)
        ]

    def _filter_home_expenses(
        self,
        expenses: list[dict],
        *,
        period: str,
        from_date: date | None = None,
        to_date: date | None = None,
        anchor_date: date | None = None,
    ) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date, anchor_date=anchor_date)
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

    def _filter_home_cash_deposits(
        self,
        deposits: list[dict],
        *,
        period: str,
        from_date: date | None = None,
        to_date: date | None = None,
        anchor_date: date | None = None,
    ) -> list[dict]:
        start_date, end_date = self._resolve_home_date_range(period, from_date=from_date, to_date=to_date, anchor_date=anchor_date)
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

    def _build_recent_deposit_items(self, *, deposits: list[dict[str, Any]], daily_records: list[dict[str, Any]], limit: int = 10) -> list[CashDepositResponse]:
        serialized_manual = [self._to_cash_deposit_response(item) for item in deposits]
        existing_source_keys = {
            (
                str(item.get("source_kind") or ""),
                str(item.get("source_id") or ""),
                str(item.get("source_subtype") or ""),
            )
            for item in deposits
            if item.get("source_kind") and item.get("source_id") and item.get("source_subtype")
        }
        derived = self._build_derived_cash_management_transactions(daily_records, existing_source_keys=existing_source_keys)
        combined = serialized_manual + derived
        combined.sort(key=lambda item: (item.created_at, item.deposit_date), reverse=True)
        return combined[:limit]

    def _build_derived_cash_management_transactions(
        self,
        daily_records: list[dict[str, Any]],
        *,
        existing_source_keys: set[tuple[str, str, str]] | None = None,
    ) -> list[CashDepositResponse]:
        existing_source_keys = existing_source_keys or set()
        derived: list[CashDepositResponse] = []
        for item in daily_records:
            business_date = str(item.get("business_date") or "")
            created_at = str(item.get("created_at") or datetime.now(UTC).isoformat())
            source_id = str(item.get("id") or item.get("_id") or business_date)
            transaction_configs = [
                ("pos_payments", "pos_payment", "POS Settlement", "Auto-generated from daily POS payments", "auto-pos"),
            ]
            method = str(item.get("method") or "")
            has_method_two_fields = (
                self._safe_float(item.get("cash_payments")) > 0
                or self._safe_float(item.get("bank_transfer_payments")) > 0
            )
            if method == "method_2" or (not method and has_method_two_fields):
                transaction_configs.extend(
                    [
                        ("cash_payments", "cash_in", "Cash Payments", "Auto-generated from daily cash payments", "auto-cash-payments"),
                        (
                            "bank_transfer_payments",
                            "bank_transfer_payment",
                            "Bank Transfer Collection",
                            "Auto-generated from daily bank transfer payments",
                            "auto-transfer",
                        ),
                        ("cash_out", "cash_out", "Register Cash Out", "Auto-generated from daily register cash out", "auto-cash-out"),
                        (
                            "expenses_in_cash",
                            "cash_expense",
                            "Expenses in Cash",
                            "Auto-generated from daily cash expenses",
                            "auto-cash-expense",
                        ),
                    ]
                )
            else:
                transaction_configs.extend(
                    [
                        ("cash_in", "cash_in", "Cash In", "Auto-generated from daily cash in", "auto-cash-in"),
                        (
                            "cash_withdrawals",
                            "cash_withdrawal",
                            "Cash Withdrawals",
                            "Auto-generated from daily cash withdrawals",
                            "auto-withdrawal",
                        ),
                        ("cash_out", "cash_out", "Cash Out", "Auto-generated from daily cash out", "auto-cash-out"),
                        (
                            "expenses_in_cash",
                            "cash_expense",
                            "Expenses in Cash",
                            "Auto-generated from daily cash expenses",
                            "auto-cash-expense",
                        ),
                    ]
                )

            for source_subtype, transaction_type, bank_account, notes, auto_prefix in transaction_configs:
                amount = self._safe_float(item.get(source_subtype))
                if amount <= 0 or ("manual_entry", source_id, source_subtype) in existing_source_keys:
                    continue
                derived.append(
                    CashDepositResponse(
                        id=f"{auto_prefix}-{source_id}",
                        deposit_date=business_date,
                        amount=self._cash_transaction_response_amount(transaction_type, amount),
                        type=transaction_type,
                        bank_account=bank_account,
                        notes=notes,
                        source_kind="manual_entry",
                        source_id=source_id,
                        source_subtype=source_subtype,
                        created_at=created_at,
                    )
                )
        return derived

    def _cash_transaction_response_amount(self, transaction_type: str, amount: float) -> float:
        resolved_amount = round(abs(float(amount or 0)), 2)
        if transaction_type in self.CASH_OUTFLOW_TRANSACTION_TYPES:
            return -resolved_amount
        return resolved_amount

    @staticmethod
    def _resolve_home_date_range(
        period: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        anchor_date: date | None = None,
    ) -> tuple[date | None, date | None]:
        if from_date is not None or to_date is not None:
            return from_date, to_date
        today = anchor_date or datetime.now(UTC).date()
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
    def _parse_optional_date(value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            try:
                return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
            except ValueError:
                try:
                    return date.fromisoformat(candidate[:10])
                except ValueError:
                    return None
        return None

    def _resolve_anchor_date(self, *values: Any) -> date:
        anchor = datetime.now(UTC).date()
        for value in values:
            parsed = self._parse_optional_date(value)
            if parsed is not None and parsed > anchor:
                anchor = parsed
        return anchor

    def _resolve_latest_business_date(self, records: list[dict]) -> date | None:
        latest: date | None = None
        for item in self.serialize_list(records):
            candidate = self._safe_parse_date(item.get("business_date"))
            if latest is None or candidate > latest:
                latest = candidate
        return latest

    def _find_latest_record_with_cover_data(self, records: list[dict]) -> dict[str, Any] | None:
        latest_record: dict[str, Any] | None = None
        latest_date: date | None = None
        for item in self.serialize_list(records):
            lunch_covers = int(item.get("lunch_covers", 0) or 0)
            dinner_covers = int(item.get("dinner_covers", 0) or 0)
            if lunch_covers + dinner_covers <= 0:
                continue
            candidate_date = self._safe_parse_date(item.get("business_date"))
            if latest_date is None or candidate_date > latest_date:
                latest_date = candidate_date
                latest_record = item
        return latest_record

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
        return f"€{value:,.2f}" if value >= 0 else f"-€{abs(value):,.2f}"

    @staticmethod
    def _percent_change(previous: float, current: float) -> float:
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return round(((current - previous) / abs(previous)) * 100, 1)

    def _calculate_vat_balance(self, revenue_total: float, expenses_total: float) -> float:
        return round((revenue_total - expenses_total) * self.VAT_RATE, 2)

    def _build_weekly_revenue_chart(self, daily_records: list[dict], *, anchor_date: date | None = None) -> list[ChartPointResponse]:
        today = anchor_date or datetime.now(UTC).date()
        by_day: dict[str, float] = {}
        for item in self.serialize_list(daily_records):
            by_day[item["business_date"]] = by_day.get(item["business_date"], 0.0) + self._resolve_home_revenue_amount(item)
        points: list[ChartPointResponse] = []
        for offset in range(6, -1, -1):
            target = today - timedelta(days=offset)
            points.append(ChartPointResponse(label=target.strftime("%a").upper(), value=round(by_day.get(target.isoformat(), 0.0), 2)))
        return points

    @staticmethod
    def _resolve_home_revenue_amount(record: dict[str, Any]) -> float:
        explicit_revenue = round(float(record.get("total_revenue", 0) or 0), 2)
        if explicit_revenue > 0:
            return explicit_revenue
        deposit_summary = record.get("deposit_summary") or {}
        return round(
            float(
                deposit_summary.get("deposits_collection_total", record.get("deposits_collection_total", 0)) or 0
            ),
            2,
        )

    def _build_recent_activity(
        self,
        *,
        current_user: dict,
        daily_records: list[dict],
        expenses: list[dict],
        documents: list[dict],
        cash_deposits: list[dict],
        inventory_items: list[dict],
        max_items: int = 6,
        prefer_distinct_kinds: bool = True,
    ) -> list[ActivityItemResponse]:
        activity_language = self._resolve_chat_language(current_user)
        max_items = max(1, min(max_items, 50))
        items: list[ActivityItemResponse] = []
        for item in daily_records[:max_items]:
            formatted_business_date = self._format_activity_date(item.get("business_date"), language=activity_language)
            total_revenue = float(item.get("total_revenue", 0) or 0)
            total_covers = int(item.get("total_covers", 0) or 0)
            average_per_cover = float(item.get("avg_revenue_per_cover", 0) or 0)
            items.append(
                ActivityItemResponse(
                    kind="daily_record",
                    title=formatted_business_date,
                    subtitle=(
                        f"Ricavi €{total_revenue:,.2f} | Coperti {total_covers} | Media €{average_per_cover:,.2f}"
                        if activity_language == "it"
                        else f"Revenue €{total_revenue:,.2f} | Covers {total_covers} | Avg €{average_per_cover:,.2f}"
                    ),
                    timestamp=item["created_at"],
                    entity_id=item["id"],
                    reference_date=item["business_date"],
                    source_kind="daily_record",
                    source_entity_id=item["id"],
                    route=f"/(tabs)/home/daily-record-details?dataId={item['id']}",
                )
            )
        for item in self.serialize_list(documents[:max_items]):
            items.append(
                ActivityItemResponse(
                    kind="invoice",
                    title="Fattura caricata" if activity_language == "it" else "Invoice uploaded",
                    subtitle=str(
                        item.get("counterparty_name")
                        or item.get("supplier_name")
                        or item.get("source_file_name")
                        or ("Documento" if activity_language == "it" else "Document")
                    ),
                    timestamp=item["created_at"],
                    entity_id=item["id"],
                    reference_date=str(item.get("invoice_date") or ""),
                    source_kind="invoice",
                    source_entity_id=item["id"],
                    route=f"/(tabs)/documents/{item['id']}",
                )
            )
        recent_expenses = sorted(
            self.serialize_list(expenses),
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("expense_date") or ""),
            ),
            reverse=True,
        )[:max_items]
        for item in recent_expenses:
            expense_date = self._safe_parse_date(item.get("expense_date"))
            reference_date = expense_date.isoformat() if expense_date else ""
            source_kind = str(item.get("source_kind") or "").lower()
            expense_route = f"/(tabs)/home/expense-details?id={item['id']}"
            expense_title = (
                {
                    "manual_entry": "Spesa dati giornalieri",
                    "document": "Spesa documento",
                    "inventory": "Spesa inventario",
                }.get(source_kind, "Spesa aggiunta")
                if activity_language == "it"
                else {
                    "manual_entry": "Daily data expense",
                    "document": "Document expense",
                    "inventory": "Inventory expense",
                }.get(source_kind, "Expense added")
            )

            items.append(
                ActivityItemResponse(
                    kind="expense",
                    title=expense_title,
                    subtitle=item["category"],
                    timestamp=item["created_at"],
                    entity_id=item["id"],
                    reference_date=reference_date,
                    source_kind="expense",
                    source_entity_id=item["id"],
                    route=expense_route,
                )
            )
        serialized_cash_deposits = sorted(
            self.serialize_list(cash_deposits),
            key=lambda item: (
                str(item.get("created_at") or ""),
                str(item.get("deposit_date") or ""),
            ),
            reverse=True,
        )
        for item in serialized_cash_deposits[:max_items]:
            transaction_type = str(item.get("type") or "bank_deposit")
            cash_title = (
                {
                    "bank_deposit": "Deposito bancario registrato",
                    "cash_deposit": "Deposito cassa registrato",
                    "pos_payment": "Pagamento POS registrato",
                    "cash_in": "Entrata cassa registrata",
                    "bank_transfer_payment": "Bonifico registrato",
                    "cash_withdrawal": "Prelievo cassa registrato",
                    "cash_out": "Uscita cassa registrata",
                    "cash_expense": "Spesa in contanti registrata",
                }.get(transaction_type, "Movimento di cassa registrato")
                if activity_language == "it"
                else {
                    "bank_deposit": "Bank deposit logged",
                    "cash_deposit": "Cash deposit logged",
                    "pos_payment": "POS payment recorded",
                    "cash_in": "Cash in recorded",
                    "bank_transfer_payment": "Bank transfer recorded",
                    "cash_withdrawal": "Cash withdrawal recorded",
                    "cash_out": "Cash out recorded",
                    "cash_expense": "Cash expense recorded",
                }.get(transaction_type, "Cash transaction recorded")
            )
            items.append(
                ActivityItemResponse(
                    kind="cash",
                    title=cash_title,
                    subtitle=str(item.get("bank_account") or item.get("deposit_type") or ""),
                    timestamp=item["created_at"],
                    entity_id=item["id"],
                    reference_date=str(self._safe_parse_date(item.get("deposit_date")) or ""),
                    source_kind="cash",
                    source_entity_id=item["id"],
                    route=f"/(tabs)/home/cash-transaction-details?id={item['id']}",
                )
            )
        for item in self.serialize_list(inventory_items[:max_items]):
            items.append(
                ActivityItemResponse(
                    kind="inventory",
                    title="Articolo inventario aggiunto" if activity_language == "it" else "Inventory item added",
                    subtitle=str(item.get("product_name") or item.get("category") or ("Inventario" if activity_language == "it" else "Inventory")),
                    timestamp=item["created_at"],
                    entity_id=item["id"],
                    reference_date=str(item.get("purchase_date") or ""),
                    source_kind="inventory",
                    source_entity_id=item["id"],
                    route=f"/(tabs)/inventory/{item['id']}",
                )
            )
        for item in items:
            item.timestamp = str(item.timestamp)
        sorted_items = sorted(items, key=lambda value: value.timestamp, reverse=True)
        if not prefer_distinct_kinds:
            return sorted_items[:max_items]
        selected: list[ActivityItemResponse] = []
        selected_ids: set[str] = set()
        selected_kinds: set[str] = set()
        for item in sorted_items:
            if item.kind in selected_kinds:
                continue
            selected.append(item)
            selected_ids.add(item.entity_id)
            selected_kinds.add(item.kind)
            if len(selected) >= max_items:
                return selected
        for item in sorted_items:
            if item.entity_id in selected_ids:
                continue
            selected.append(item)
            if len(selected) >= max_items:
                break
        return selected

    @staticmethod
    def _format_notification_currency(amount: float) -> str:
        return f"€{abs(float(amount or 0)):,.2f}"

    @staticmethod
    def _resolve_push_devices(current_user: dict) -> list[dict[str, Any]]:
        serialized = RestaurantOperationsService.serialize(current_user)
        devices = serialized.get("push_devices") or []
        return [item for item in devices if isinstance(item, dict) and item.get("expo_push_token")]

    async def _send_push_notification(
        self,
        current_user: dict,
        *,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        respect_low_stock_alerts: bool = False,
        respect_daily_summary_alerts: bool = False,
    ) -> None:
        try:
            settings = await self.get_notification_settings(current_user)
            if not settings.push_notifications:
                return
            if respect_low_stock_alerts and not settings.low_stock_alerts:
                return
            if respect_daily_summary_alerts and not settings.daily_summary_notifications:
                return

            devices = self._resolve_push_devices(current_user)
            if not devices:
                return

            messages = [
                {
                    "to": str(device["expo_push_token"]),
                    "title": title,
                    "body": body,
                    "sound": "default",
                    "data": data or {},
                }
                for device in devices
            ]
            await asyncio.to_thread(self._post_expo_push_messages, messages)
        except Exception as exc:
            logger.warning("Push notification delivery failed: %s", exc)

    @staticmethod
    def _post_expo_push_messages(messages: list[dict[str, Any]]) -> None:
        if not messages:
            return
        request = urllib_request.Request(
            "https://exp.host/--/api/v2/push/send",
            data=json.dumps(messages).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=10) as response:
                response.read()
        except urllib_error.URLError as exc:
            raise RuntimeError(f"Expo push request failed: {exc}") from exc

    async def _send_activity_push_for_daily_record(self, current_user: dict, item: dict[str, Any]) -> None:
        business_date = self._safe_parse_date(item.get("business_date"))
        cash_available = float(item.get("cash_available", 0) or 0)
        total_revenue = float(item.get("total_revenue", 0) or 0)
        await self._send_push_notification(
            current_user,
            title=f"Daily cash updated to {self._format_notification_currency(cash_available)}",
            body=(
                f"Revenue {self._format_notification_currency(total_revenue)}"
                f" on {(business_date.strftime('%d %b %Y') if business_date else str(item.get('business_date') or 'today'))}"
            ),
            data={
                "route": f"/(tabs)/home/daily-record-details?dataId={item['id']}",
                "kind": "daily_record",
                "entity_id": str(item.get("id") or ""),
            },
            respect_daily_summary_alerts=True,
        )

    async def _send_activity_push_for_document(self, current_user: dict, item: dict[str, Any]) -> None:
        expense_amount = float(item.get("expense_amount", 0) or 0)
        cash_amount = float(item.get("cash_amount", 0) or 0)
        revenue_amount = float(item.get("revenue_amount", 0) or 0)
        profit_amount = float(item.get("profit_amount", 0) or 0)
        if expense_amount > 0:
            title = f"Expenses increased by {self._format_notification_currency(expense_amount)}"
        elif cash_amount > 0:
            title = f"Cash available increased by {self._format_notification_currency(cash_amount)}"
        elif revenue_amount > 0:
            title = f"Revenue increased by {self._format_notification_currency(revenue_amount)}"
        elif profit_amount != 0:
            direction = "increased" if profit_amount > 0 else "decreased"
            title = f"Profit {direction} by {self._format_notification_currency(profit_amount)}"
        else:
            title = "Document processed"
        await self._send_push_notification(
            current_user,
            title=title,
            body=str(item.get("counterparty_name") or item.get("supplier_name") or item.get("source_file_name") or "Document saved"),
            data={
                "route": f"/(tabs)/documents/{item['id']}",
                "kind": "invoice",
                "entity_id": str(item.get("id") or ""),
            },
        )

    async def _send_activity_push_for_expense(self, current_user: dict, item: dict[str, Any]) -> None:
        amount = float(item.get("amount", 0) or 0)
        section = str(item.get("section") or "cash").lower()
        title = (
            f"Cash available decreased by {self._format_notification_currency(amount)}"
            if section == "cash"
            else f"Expenses increased by {self._format_notification_currency(amount)}"
        )
        await self._send_push_notification(
            current_user,
            title=title,
            body=str(item.get("category") or "Expense"),
            data={
                "route": f"/(tabs)/home/expense-details?id={item['id']}",
                "kind": "expense",
                "entity_id": str(item.get("id") or ""),
            },
        )

    async def _send_activity_push_for_cash_deposit(self, current_user: dict, item: dict[str, Any]) -> None:
        amount = float(item.get("amount", 0) or 0)
        transaction_type = str(item.get("type") or "bank_deposit")
        if transaction_type in {"bank_deposit", "cash_deposit", "cash_withdrawal", "cash_out", "cash_expense"}:
            title = f"Cash available decreased by {self._format_notification_currency(amount)}"
        elif transaction_type == "cash_in":
            title = f"Cash available increased by {self._format_notification_currency(amount)}"
        else:
            title = f"Collections increased by {self._format_notification_currency(amount)}"
        await self._send_push_notification(
            current_user,
            title=title,
            body=str(item.get("bank_account") or item.get("display_title") or "Cash transaction"),
            data={
                "route": f"/(tabs)/home/cash-transaction-details?id={item['id']}",
                "kind": "cash",
                "entity_id": str(item.get("id") or ""),
            },
        )

    async def _send_activity_push_for_inventory(self, current_user: dict, item: dict[str, Any]) -> None:
        stock_quantity = float(item.get("stock_quantity", 0) or 0)
        unit_price = float(item.get("unit_price", 0) or 0)
        total_value = stock_quantity * unit_price
        await self._send_push_notification(
            current_user,
            title=f"Inventory value increased by {self._format_notification_currency(total_value)}",
            body=str(item.get("product_name") or item.get("category") or "Inventory item"),
            data={
                "route": f"/(tabs)/inventory/{item['id']}",
                "kind": "inventory",
                "entity_id": str(item.get("id") or ""),
            },
        )

    async def _send_low_stock_push_if_needed(self, current_user: dict, item: dict[str, Any]) -> None:
        stock_status = str(item.get("stock_status") or "")
        if stock_status not in {"low_stock", "out_of_stock"}:
            return
        quantity = float(item.get("stock_quantity", 0) or 0)
        unit = str(item.get("unit_type") or "units")
        await self._send_push_notification(
            current_user,
            title=f"Low stock alert: {str(item.get('product_name') or 'Inventory item')}",
            body=f"{quantity:g} {unit} remaining. Restock soon.",
            data={
                "route": f"/(tabs)/inventory/{item['id']}",
                "kind": "inventory_low_stock",
                "entity_id": str(item.get("id") or ""),
            },
            respect_low_stock_alerts=True,
        )

    def _build_notification_feed(
        self,
        *,
        daily_records: list[dict],
        expenses: list[dict],
        documents: list[dict],
        cash_deposits: list[dict],
        inventory_items: list[dict],
        limit: int = 25,
    ) -> list[ActivityItemResponse]:
        notifications: list[ActivityItemResponse] = []

        for item in daily_records:
            business_date = self._safe_parse_date(item.get("business_date"))
            cash_available = float(item.get("cash_available", 0) or 0)
            total_revenue = float(item.get("total_revenue", 0) or 0)
            notifications.append(
                ActivityItemResponse(
                    kind="daily_record",
                    title=f"Daily cash updated to {self._format_notification_currency(cash_available)}",
                    subtitle=(
                        f"Revenue {self._format_notification_currency(total_revenue)}"
                        f" on {(business_date.strftime('%d %b %Y') if business_date else str(item.get('business_date') or 'today'))}"
                    ),
                    timestamp=str(item.get("created_at") or ""),
                    entity_id=str(item.get("id") or ""),
                    reference_date=str(item.get("business_date") or ""),
                    source_kind="daily_record",
                    source_entity_id=str(item.get("id") or ""),
                    route=f"/(tabs)/home/daily-record-details?dataId={item['id']}",
                )
            )

        for item in documents:
            expense_amount = float(item.get("expense_amount", 0) or 0)
            cash_amount = float(item.get("cash_amount", 0) or 0)
            revenue_amount = float(item.get("revenue_amount", 0) or 0)
            profit_amount = float(item.get("profit_amount", 0) or 0)
            if expense_amount > 0:
                title = f"Expenses increased by {self._format_notification_currency(expense_amount)}"
            elif cash_amount > 0:
                title = f"Cash available increased by {self._format_notification_currency(cash_amount)}"
            elif revenue_amount > 0:
                title = f"Revenue increased by {self._format_notification_currency(revenue_amount)}"
            elif profit_amount != 0:
                direction = "increased" if profit_amount > 0 else "decreased"
                title = f"Profit {direction} by {self._format_notification_currency(profit_amount)}"
            else:
                title = "Document processed"
            notifications.append(
                ActivityItemResponse(
                    kind="invoice",
                    title=title,
                    subtitle=str(item.get("counterparty_name") or item.get("supplier_name") or item.get("source_file_name") or "Document saved"),
                    timestamp=str(item.get("created_at") or ""),
                    entity_id=str(item.get("id") or ""),
                    reference_date=str(item.get("invoice_date") or ""),
                    source_kind="invoice",
                    source_entity_id=str(item.get("id") or ""),
                    route=f"/(tabs)/documents/{item['id']}",
                )
            )

        for item in expenses:
            amount = float(item.get("amount", 0) or 0)
            section = str(item.get("section") or "cash").lower()
            if section == "cash":
                title = f"Cash available decreased by {self._format_notification_currency(amount)}"
            else:
                title = f"Expenses increased by {self._format_notification_currency(amount)}"
            notifications.append(
                ActivityItemResponse(
                    kind="expense",
                    title=title,
                    subtitle=str(item.get("category") or "Expense"),
                    timestamp=str(item.get("created_at") or ""),
                    entity_id=str(item.get("id") or ""),
                    reference_date=str(item.get("expense_date") or ""),
                    source_kind="expense",
                    source_entity_id=str(item.get("id") or ""),
                    route=f"/(tabs)/home/expense-details?id={item['id']}",
                )
            )

        for item in cash_deposits:
            amount = float(item.get("amount", 0) or 0)
            transaction_type = str(item.get("type") or "bank_deposit")
            if transaction_type in {"bank_deposit", "cash_deposit", "cash_withdrawal", "cash_out", "cash_expense"}:
                title = f"Cash available decreased by {self._format_notification_currency(amount)}"
            elif transaction_type == "cash_in":
                title = f"Cash available increased by {self._format_notification_currency(amount)}"
            else:
                title = f"Collections increased by {self._format_notification_currency(amount)}"
            notifications.append(
                ActivityItemResponse(
                    kind="cash",
                    title=title,
                    subtitle=str(item.get("bank_account") or item.get("display_title") or "Cash transaction"),
                    timestamp=str(item.get("created_at") or ""),
                    entity_id=str(item.get("id") or ""),
                    reference_date=str(item.get("deposit_date") or ""),
                    source_kind="cash",
                    source_entity_id=str(item.get("id") or ""),
                    route=f"/(tabs)/home/cash-transaction-details?id={item['id']}",
                )
            )

        for item in inventory_items:
            stock_quantity = float(item.get("stock_quantity", 0) or 0)
            unit_price = float(item.get("unit_price", 0) or 0)
            total_value = stock_quantity * unit_price
            notifications.append(
                ActivityItemResponse(
                    kind="inventory",
                    title=f"Inventory value increased by {self._format_notification_currency(total_value)}",
                    subtitle=str(item.get("product_name") or item.get("category") or "Inventory item"),
                    timestamp=str(item.get("created_at") or ""),
                    entity_id=str(item.get("id") or ""),
                    reference_date=str(item.get("purchase_date") or ""),
                    source_kind="inventory",
                    source_entity_id=str(item.get("id") or ""),
                    route=f"/(tabs)/inventory/{item['id']}",
                )
            )

        notifications.sort(key=lambda item: item.timestamp, reverse=True)
        return notifications[:limit]

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

    @staticmethod
    def _summarize_daily_bucket_document(document: dict[str, Any]) -> dict[str, float]:
        document_type = str(document.get("document_type") or "").lower()
        expense_amount = float(document.get("expense_amount", 0) or 0)
        if expense_amount <= 0 and document_type == "expense":
            expense_amount = float(document.get("total_amount", 0) or 0)
        return {
            "revenue": round(float(document.get("cash_amount", 0) or 0) + float(document.get("revenue_amount", 0) or 0), 2),
            "invoice_total": round(expense_amount if document_type == "expense" else 0.0, 2),
        }

    def _build_daily_data_buckets(self, records: list[dict[str, Any]], expenses: list[dict[str, Any]], documents: list[dict[str, Any]], *, anchor_date: date) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for record in records:
            bucket_key = f"record:{record['id']}"
            covers = int(record.get("lunch_covers", 0) + record.get("dinner_covers", 0))
            bucket = {
                "id": record["id"],
                "business_date": record["business_date"],
                "total_revenue": float(record.get("total_revenue", 0)),
                "total_expenses": float(record.get("total_expenses", 0)),
                "invoice_document_total": float(record.get("uploaded_document_total", 0.0)),
                "total_covers": covers,
                "avg_revenue_per_cover": float(record.get("avg_revenue_per_cover", 0)),
                "opening_cash": float(record.get("opening_cash", 0) or 0),
                "closing_cash": float(record.get("closing_cash", 0) or 0),
                "cash_payments": float(record.get("cash_payments", 0) or 0),
                "record_id": record["id"],
                "created_at": record["created_at"],
                "data_sources": [],
            }
            bucket["data_sources"].append(
                DailyDataEntrySourceResponse(kind="daily_record", label="Daily data", count=1, endpoint=f"/api/v1/restaurant/daily-data/{record['id']}")
            )
            buckets[bucket_key] = bucket

        expense_groups: dict[str, dict[str, Any]] = {}
        for expense in expenses:
            if str(expense.get("source_kind") or "").lower() in {"manual_entry", "document"}:
                continue
            expense_date = datetime.fromisoformat(expense["expense_date"].replace("Z", "+00:00")).date().isoformat()
            group = expense_groups.setdefault(expense_date, {"uploaded_document": {"count": 0, "total": 0.0, "endpoint": None}, "manual_expense": {"count": 0, "total": 0.0, "endpoint": "/api/v1/restaurant/expenses"}})
            group["manual_expense"]["count"] += 1
            group["manual_expense"]["total"] += float(expense.get("amount", 0))

            bucket = buckets.setdefault(
                expense_date,
                {
                    "id": f"date:{expense_date}",
                    "business_date": expense_date,
                    "total_revenue": 0.0,
                    "total_expenses": 0.0,
                    "invoice_document_total": 0.0,
                    "total_covers": 0,
                    "avg_revenue_per_cover": 0.0,
                    "opening_cash": 0.0,
                    "closing_cash": 0.0,
                    "cash_payments": 0.0,
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
            document_totals = self._summarize_daily_bucket_document(document)
            group = expense_groups.setdefault(invoice_date, {"uploaded_document": {"count": 0, "total": 0.0, "endpoint": None}, "manual_expense": {"count": 0, "total": 0.0, "endpoint": "/api/v1/restaurant/expenses"}})
            if document_totals["invoice_total"] > 0:
                group["uploaded_document"]["count"] += 1
                group["uploaded_document"]["total"] += document_totals["invoice_total"]
                group["uploaded_document"]["endpoint"] = f"/api/v1/restaurant/daily-data/by-date?business_date={invoice_date}"
            bucket = buckets.setdefault(
                invoice_date,
                {
                    "id": f"date:{invoice_date}",
                    "business_date": invoice_date,
                    "total_revenue": 0.0,
                    "total_expenses": 0.0,
                    "invoice_document_total": 0.0,
                    "total_covers": 0,
                    "avg_revenue_per_cover": 0.0,
                    "opening_cash": 0.0,
                    "closing_cash": 0.0,
                    "cash_payments": 0.0,
                    "record_id": None,
                    "created_at": document.get("created_at", datetime.now(UTC).isoformat()),
                    "data_sources": [],
                },
            )
            bucket["total_revenue"] = round(bucket.get("total_revenue", 0.0) + document_totals["revenue"], 2)
            bucket["invoice_document_total"] = round(bucket.get("invoice_document_total", 0.0) + document_totals["invoice_total"], 2)

        for expense_date, grouped in expense_groups.items():
            bucket = buckets[expense_date]
            if grouped["uploaded_document"]["count"]:
                bucket["data_sources"].append(
                    DailyDataEntrySourceResponse(
                        kind="uploaded_document",
                        label="Uploaded documents",
                        count=grouped["uploaded_document"]["count"],
                        total_amount=round(grouped["uploaded_document"]["total"], 2),
                        endpoint=grouped["uploaded_document"]["endpoint"],
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

        return sorted(
            buckets.values(),
            key=lambda item: (item["business_date"], str(item.get("created_at", ""))),
            reverse=True,
        )

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
            currency_symbol = "€" if currency == "EUR" else f"{currency} "
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
        line_item_count = serialized.get("line_item_count")
        return DocumentListItemResponse(
            id=serialized["id"],
            document_type=str(serialized.get("document_type", "unknown")).lower(),
            document_label=serialized.get("document_label"),
            counterparty_name=serialized.get("counterparty_name") or serialized.get("supplier_name"),
            document_number=serialized.get("invoice_number"),
            document_date=invoice_date,
            upload_date=serialized["upload_date"],
            total_amount=float(serialized.get("total_amount", 0.0)),
            status=status,
            line_item_count=int(line_item_count if line_item_count is not None else len(serialized.get("line_items", []))),
            created_by_user_id=serialized.get("created_by_user_id"),
            last_edited_by_user_id=serialized.get("last_edited_by_user_id"),
            confirmed_at=serialized.get("confirmed_at"),
        )

    def _to_document_confirm_save(self, document: dict) -> DocumentConfirmSaveResponse:
        serialized = self.serialize(document)
        return DocumentConfirmSaveResponse(
            id=serialized["id"],
            document_type=str(serialized.get("document_type", "unknown")).lower(),
            document_label=serialized.get("document_label") or str(serialized.get("document_type", "unknown")).title(),
            counterparty_name=serialized.get("counterparty_name"),
            document_number=serialized.get("invoice_number"),
            document_date=serialized.get("invoice_date"),
            total_amount=float(serialized.get("total_amount", 0.0)),
            currency=str(serialized.get("currency", "EUR")),
            expense_amount=float(serialized.get("expense_amount", 0.0)),
            cash_amount=float(serialized.get("cash_amount", 0.0)),
            revenue_amount=float(serialized.get("revenue_amount", 0.0)),
            profit_amount=float(serialized.get("profit_amount", 0.0)),
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
            document_type=str(serialized.get("document_type", "unknown")).lower(),
            document_label=serialized.get("document_label") or str(serialized.get("document_type", "unknown")).title(),
            counterparty_name=serialized.get("counterparty_name"),
            document_number=serialized.get("invoice_number"),
            document_date=invoice_date,
            upload_date=upload_date,
            total_amount=float(serialized.get("total_amount", 0.0)),
            currency=str(serialized.get("currency", "EUR")),
            expense_amount=float(serialized.get("expense_amount", 0.0)),
            cash_amount=float(serialized.get("cash_amount", 0.0)),
            revenue_amount=float(serialized.get("revenue_amount", 0.0)),
            profit_amount=float(serialized.get("profit_amount", 0.0)),
            status=status,
            ai_provider=serialized["ai_provider"],
            ai_summary=serialized.get("ai_summary", ""),
            line_items=[DocumentLineItemSchema(**item) for item in serialized.get("line_items", [])],
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_document_extraction(self, *, extraction: dict[str, Any], file_name: str) -> dict[str, Any]:
        line_items = extraction.get("line_items") or []
        total_amount = extraction.get("total_amount")
        if total_amount is None:
            total_amount = round(sum(self._safe_float(item.get("total_price", 0)) for item in line_items), 2)
        total_amount = round(self._safe_float(total_amount), 2)

        supplier_name = str(
            extraction.get("supplier_name")
            or extraction.get("counterparty_name")
            or "Unknown Supplier"
        ).strip() or "Unknown Supplier"
        counterparty_name = str(extraction.get("counterparty_name") or supplier_name).strip() or supplier_name
        document_type = self._resolve_document_type(extraction=extraction, file_name=file_name)
        expense_amount = round(self._safe_float(extraction.get("expense_amount")), 2)
        cash_amount = round(self._safe_float(extraction.get("cash_amount")), 2)
        revenue_amount = round(self._safe_float(extraction.get("revenue_amount")), 2)
        profit_amount = round(self._safe_float(extraction.get("profit_amount")), 2)

        if expense_amount == cash_amount == revenue_amount == profit_amount == 0.0 and total_amount > 0:
            if document_type == "expense":
                expense_amount = total_amount
            elif document_type == "cash":
                cash_amount = total_amount
            elif document_type == "revenue":
                revenue_amount = total_amount
            elif document_type == "profit":
                profit_amount = total_amount

        if document_type == "profit" and profit_amount == 0.0 and (revenue_amount > 0 or expense_amount > 0):
            profit_amount = round(revenue_amount - expense_amount, 2)

        document_label = str(extraction.get("document_label") or document_type.title()).strip() or document_type.title()
        currency = str(extraction.get("currency") or "EUR").strip() or "EUR"
        invoice_date = extraction.get("invoice_date")
        if invoice_date in ("", None):
            invoice_date = None
        else:
            invoice_date = str(invoice_date)

        return {
            "document_type": document_type,
            "document_label": document_label,
            "counterparty_name": counterparty_name,
            "supplier_name": supplier_name,
            "invoice_number": extraction.get("invoice_number"),
            "invoice_date": invoice_date,
            "total_amount": total_amount,
            "currency": currency,
            "expense_amount": expense_amount,
            "cash_amount": cash_amount,
            "revenue_amount": revenue_amount,
            "profit_amount": profit_amount,
            "ai_summary": str(extraction.get("ai_summary") or "AI extraction completed.").strip(),
            "line_items": line_items,
        }

    def _resolve_document_type(self, *, extraction: dict[str, Any], file_name: str) -> str:
        raw_document_type = str(extraction.get("document_type") or "").strip().lower()
        if raw_document_type in self.SUPPORTED_DOCUMENT_TYPES:
            return raw_document_type

        text_fragments = [
            file_name,
            extraction.get("document_label"),
            extraction.get("ai_summary"),
            extraction.get("invoice_number"),
        ]
        haystack = " ".join(str(value).lower() for value in text_fragments if value)
        if any(token in haystack for token in ("profit", "p&l", "income statement", "margin")):
            return "profit"
        if any(token in haystack for token in ("cash", "deposit", "bank drop", "till", "drawer", "reconciliation")):
            return "cash"
        if any(token in haystack for token in ("revenue", "sales", "turnover", "receipt", "pos", "settlement")):
            return "revenue"
        if any(token in haystack for token in ("invoice", "bill", "supplier", "purchase", "expense")):
            return "expense"
        return "unknown"

    def _to_expense_response(self, expense: dict) -> ExpenseResponse:
        serialized = self.serialize(expense)
        amount = float(serialized["amount"])
        category = str(serialized.get("category") or "Expense")
        return ExpenseResponse(
            id=serialized["id"],
            category=category,
            amount=amount,
            expense_date=serialized["expense_date"],
            section=str(serialized.get("section", "cash")).lower(),
            notes=serialized.get("notes"),
            source_kind=serialized.get("source_kind"),
            source_id=serialized.get("source_id"),
            source_inventory_item_id=serialized.get("source_inventory_item_id"),
            created_at=serialized["created_at"],
        )

    def _to_cash_deposit_response(self, deposit: dict) -> CashDepositResponse:
        serialized = self.serialize(deposit)
        transaction_type = str(serialized.get("type", "bank_deposit"))
        if transaction_type not in self.CASH_TRANSACTION_TYPES:
            transaction_type = "cash_deposit"
        return CashDepositResponse(
            id=serialized["id"],
            deposit_date=serialized["deposit_date"],
            amount=self._cash_transaction_response_amount(transaction_type, self._safe_float(serialized.get("amount"))),
            type=transaction_type,
            bank_account=serialized.get("bank_account") or serialized.get("deposit_type", ""),
            notes=serialized.get("notes"),
            source_kind=serialized.get("source_kind"),
            source_id=serialized.get("source_id"),
            source_subtype=serialized.get("source_subtype"),
            created_at=serialized["created_at"],
        )

    def _to_bank_account_response(self, account: dict, *, deposited_amount: float = 0.0) -> BankAccountResponse:
        serialized = self.serialize(account)
        return BankAccountResponse(
            id=serialized["id"],
            bank_account=serialized["bank_account"],
            deposited_amount=round(float(deposited_amount), 2),
            created_at=serialized["created_at"],
        )

    @staticmethod
    def _normalize_bank_account_name(value: str) -> str:
        return " ".join(value.strip().lower().split())

    @staticmethod
    def _normalize_inventory_metadata_name(value: str | None) -> str:
        return " ".join(str(value or "").strip().lower().split())

    async def _upsert_inventory_category(self, *, current_user: dict, name: str | None) -> dict[str, Any] | None:
        cleaned_name = str(name or "").strip()
        normalized_name = self._normalize_inventory_metadata_name(cleaned_name)
        if not normalized_name:
            return None
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        existing = await self.inventory_category_repository.find_by_normalized_name(
            scope_id=scope_id,
            normalized_name=normalized_name,
        )
        if existing is not None:
            return existing
        return await self.inventory_category_repository.create(
            {
                "tenant_id": scope_id,
                "name": cleaned_name,
                "normalized_name": normalized_name,
                "created_by_user_id": str(current_user["_id"]),
            }
        )

    async def _upsert_inventory_supplier(self, *, current_user: dict, name: str | None) -> dict[str, Any] | None:
        cleaned_name = str(name or "").strip()
        normalized_name = self._normalize_inventory_metadata_name(cleaned_name)
        if not normalized_name:
            return None
        scope_id = ScopedRepository.resolve_scope_id(current_user)
        existing = await self.inventory_supplier_repository.find_by_normalized_name(
            scope_id=scope_id,
            normalized_name=normalized_name,
        )
        if existing is not None:
            return existing
        return await self.inventory_supplier_repository.create(
            {
                "tenant_id": scope_id,
                "name": cleaned_name,
                "normalized_name": normalized_name,
                "created_by_user_id": str(current_user["_id"]),
            }
        )

    @staticmethod
    def _build_register_summary(payload: dict[str, Any]) -> DailyDataRegisterSummaryResponse:
        opening_cash = float(payload.get("opening_cash", 0) or 0)
        closing_cash = float(payload.get("closing_cash", 0) or 0)
        cash_payments = float(payload.get("cash_payments", 0) or 0)
        cash_difference = float(payload.get("cash_difference", 0) or 0)
        return DailyDataRegisterSummaryResponse(
            opening_cash=opening_cash,
            closing_cash=closing_cash,
            cash_payments=cash_payments,
            total_cash_on_hand=round(closing_cash + cash_payments, 2),
            cash_difference=round(cash_difference, 2),
        )

    def _build_daily_data_sections(self, payload: dict[str, Any]) -> list[DailyDataSectionResponse]:
        if payload.get("method") == "method_2":
            return [
                DailyDataSectionResponse(
                    key="deposit_section",
                    title="Deposit Section",
                    fields=[
                        DailyDataSectionFieldResponse(
                            key="pos_payments",
                            label="POS Payments",
                            value=float(payload.get("pos_payments", 0) or 0),
                            value_type="currency",
                        ),
                        DailyDataSectionFieldResponse(
                            key="cash_payments",
                            label="Cash Payments",
                            value=float(payload.get("cash_payments", 0) or 0),
                            value_type="currency",
                        ),
                        DailyDataSectionFieldResponse(
                            key="bank_transfer_payments",
                            label="Bank Transfer Payments",
                            value=float(payload.get("bank_transfer_payments", 0) or 0),
                            value_type="currency",
                        ),
                        DailyDataSectionFieldResponse(
                            key="total_deposits",
                            label="Total Deposits",
                            value=round(
                                float(payload.get("pos_payments", 0) or 0)
                                + float(payload.get("cash_payments", 0) or 0)
                                + float(payload.get("bank_transfer_payments", 0) or 0),
                                2,
                            ),
                            value_type="currency",
                        ),
                    ],
                ),
                DailyDataSectionResponse(
                    key="expense_section",
                    title="Expense Section",
                    fields=[
                        DailyDataSectionFieldResponse(
                            key="expenses_in_cash",
                            label="Expenses in Cash",
                            value=float(payload.get("expenses_in_cash", 0) or 0),
                            value_type="currency",
                        ),
                    ],
                ),
                DailyDataSectionResponse(
                    key="covers_section",
                    title="Coperti Section",
                    fields=[
                        DailyDataSectionFieldResponse(
                            key="lunch_covers",
                            label="Lunch Coperti",
                            value=int(payload.get("lunch_covers", 0) or 0),
                            value_type="integer",
                        ),
                        DailyDataSectionFieldResponse(
                            key="dinner_covers",
                            label="Dinner Coperti",
                            value=int(payload.get("dinner_covers", 0) or 0),
                            value_type="integer",
                        ),
                        DailyDataSectionFieldResponse(
                            key="total_covers",
                            label="Total Coperti",
                            value=int(payload.get("lunch_covers", 0) or 0) + int(payload.get("dinner_covers", 0) or 0),
                            value_type="integer",
                        ),
                    ],
                ),
                DailyDataSectionResponse(
                    key="register_section",
                    title="Register Section",
                    fields=[
                        DailyDataSectionFieldResponse(
                            key="opening_cash",
                            label="Opening Cash",
                            value=float(payload.get("opening_cash", 0) or 0),
                            value_type="currency",
                        ),
                        DailyDataSectionFieldResponse(
                            key="closing_cash",
                            label="Closing Cash",
                            value=float(payload.get("closing_cash", 0) or 0),
                            value_type="currency",
                        ),
                        DailyDataSectionFieldResponse(
                            key="cash_payments",
                            label="Cash Payments in Register",
                            value=float(payload.get("cash_payments", 0) or 0),
                            value_type="currency",
                        ),
                        DailyDataSectionFieldResponse(
                            key="cash_difference",
                            label="Daily Cash Difference",
                            value=float(payload.get("cash_difference", 0) or 0),
                            value_type="currency",
                        ),
                    ],
                ),
            ]

        return [
            DailyDataSectionResponse(
                key="deposit_section",
                title="Deposit Section",
                fields=[
                    DailyDataSectionFieldResponse(
                        key="pos_payments",
                        label="POS Payments",
                        value=float(payload.get("pos_payments", 0) or 0),
                        value_type="currency",
                    ),
                    DailyDataSectionFieldResponse(
                        key="cash_in",
                        label="Cash In",
                        value=float(payload.get("cash_in", 0) or 0),
                        value_type="currency",
                    ),
                    DailyDataSectionFieldResponse(
                        key="total_deposits",
                        label="Total Deposits",
                        value=round(
                            float(payload.get("pos_payments", 0) or 0) + float(payload.get("cash_in", 0) or 0),
                            2,
                        ),
                        value_type="currency",
                    ),
                ],
            ),
            DailyDataSectionResponse(
                key="expense_section",
                title="Expense Section",
                fields=[
                    DailyDataSectionFieldResponse(
                        key="expenses_in_cash",
                        label="Expenses in Cash",
                        value=float(payload.get("expenses_in_cash", 0) or 0),
                        value_type="currency",
                    ),
                ],
            ),
            DailyDataSectionResponse(
                key="cash_movement_section",
                title="Cash Movement Section",
                fields=[
                    DailyDataSectionFieldResponse(
                        key="cash_withdrawals",
                        label="Cash Withdrawals",
                        value=float(payload.get("cash_withdrawals", 0) or 0),
                        value_type="currency",
                    ),
                    DailyDataSectionFieldResponse(
                        key="cash_out",
                        label="Cash Out",
                        value=float(payload.get("cash_out", 0) or 0),
                        value_type="currency",
                    ),
                ],
            ),
            DailyDataSectionResponse(
                key="notes_section",
                title="Notes Section",
                fields=[
                    DailyDataSectionFieldResponse(
                        key="notes",
                        label="Notes",
                        value=str(payload.get("notes", "") or ""),
                        value_type="text",
                    ),
                ],
            )
        ]

    def _build_grouped_daily_data_sections(
        self,
        *,
        records: list[dict[str, Any]],
        expenses: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        bucket: dict[str, Any],
    ) -> list[DailyDataSectionResponse]:
        pos_total = round(sum(float(item.get("pos_payments", 0) or 0) for item in records), 2)
        cash_in_total = round(
            sum(float(item.get("cash_in", 0) or 0) for item in records if item.get("method") != "method_2"),
            2,
        )
        cash_payments_total = round(
            sum(float(item.get("cash_payments", 0) or 0) for item in records if item.get("method") == "method_2"),
            2,
        )
        bank_transfer_total = round(
            sum(float(item.get("bank_transfer_payments", 0) or 0) for item in records if item.get("method") == "method_2"),
            2,
        )
        daily_cash_expense_total = round(sum(float(item.get("expenses_in_cash", 0) or 0) for item in records), 2)
        cash_withdrawals_total = round(sum(float(item.get("cash_withdrawals", 0) or 0) for item in records), 2)
        cash_out_total = round(sum(float(item.get("cash_out", 0) or 0) for item in records), 2)
        opening_cash_total = round(sum(float(item.get("opening_cash", 0) or 0) for item in records), 2)
        closing_cash_total = round(sum(float(item.get("closing_cash", 0) or 0) for item in records), 2)
        cash_difference_total = round(sum(float(item.get("cash_difference", 0) or 0) for item in records), 2)
        lunch_covers_total = sum(int(item.get("lunch_covers", 0) or 0) for item in records)
        dinner_covers_total = sum(int(item.get("dinner_covers", 0) or 0) for item in records)
        additional_manual_expenses_total = round(
            sum(
                float(item.get("amount", 0) or 0)
                for item in expenses
                if str(item.get("source_kind") or "").lower() not in {"manual_entry", "document"}
            ),
            2,
        )
        uploaded_document_total = round(
            sum(self._summarize_daily_bucket_document(item)["invoice_total"] for item in documents),
            2,
        )

        sections = [
            DailyDataSectionResponse(
                key="deposit_section",
                title="Deposit Section",
                fields=[
                    DailyDataSectionFieldResponse(key="pos_payments", label="POS Payments", value=pos_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="cash_payments", label="Cash Payments", value=cash_payments_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="cash_in", label="Cash In", value=cash_in_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="bank_transfer_payments", label="Bank Transfer Payments", value=bank_transfer_total, value_type="currency"),
                    DailyDataSectionFieldResponse(
                        key="total_deposits",
                        label="Total Deposits",
                        value=round(pos_total + cash_payments_total + cash_in_total + bank_transfer_total, 2),
                        value_type="currency",
                    ),
                ],
            ),
            DailyDataSectionResponse(
                key="expense_section",
                title="Expense Section",
                fields=[
                    DailyDataSectionFieldResponse(key="daily_data_expenses", label="Daily Data Cash Expense", value=daily_cash_expense_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="manual_expenses", label="Additional Manual Expenses", value=additional_manual_expenses_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="uploaded_documents", label="Uploaded Documents", value=uploaded_document_total, value_type="currency"),
                    DailyDataSectionFieldResponse(
                        key="total_expense_collection",
                        label="Total Expense Collection",
                        value=round(daily_cash_expense_total + additional_manual_expenses_total + uploaded_document_total, 2),
                        value_type="currency",
                    ),
                ],
            ),
            DailyDataSectionResponse(
                key="cash_movement_section",
                title="Cash Movement Section",
                fields=[
                    DailyDataSectionFieldResponse(key="cash_withdrawals", label="Cash Withdrawals", value=cash_withdrawals_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="cash_out", label="Cash Out", value=cash_out_total, value_type="currency"),
                ],
            ),
            DailyDataSectionResponse(
                key="register_section",
                title="Register Section",
                fields=[
                    DailyDataSectionFieldResponse(key="opening_cash", label="Opening Cash", value=opening_cash_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="closing_cash", label="Closing Cash", value=closing_cash_total, value_type="currency"),
                    DailyDataSectionFieldResponse(key="cash_payments_register", label="Cash Payments in Register", value=float(bucket.get("cash_payments", 0) or 0), value_type="currency"),
                    DailyDataSectionFieldResponse(key="cash_on_hand", label="Total Cash On Hand", value=float(bucket.get("closing_cash", 0) or 0) + float(bucket.get("cash_payments", 0) or 0), value_type="currency"),
                    DailyDataSectionFieldResponse(key="cash_difference", label="Daily Cash Difference", value=cash_difference_total, value_type="currency"),
                ],
            ),
        ]

        if lunch_covers_total or dinner_covers_total:
            sections.append(
                DailyDataSectionResponse(
                    key="covers_section",
                    title="Coperti Section",
                    fields=[
                        DailyDataSectionFieldResponse(key="lunch_covers", label="Lunch Coperti", value=lunch_covers_total, value_type="integer"),
                        DailyDataSectionFieldResponse(key="dinner_covers", label="Dinner Coperti", value=dinner_covers_total, value_type="integer"),
                        DailyDataSectionFieldResponse(key="total_covers", label="Total Coperti", value=lunch_covers_total + dinner_covers_total, value_type="integer"),
                    ],
                )
            )

        return sections

    def _to_daily_data_response(self, record: dict) -> DailyDataResponse:
        serialized = self.serialize(record)
        lunch_covers = int(serialized.get("lunch_covers", 0))
        dinner_covers = int(serialized.get("dinner_covers", 0))
        total_covers = lunch_covers + dinner_covers
        if serialized.get("method") == "method_2":
            revenue_breakdown = [
                DailyDataRevenueBreakdownItemResponse(label="POS Payments", amount=float(serialized.get("pos_payments", 0))),
                DailyDataRevenueBreakdownItemResponse(label="Cash Payments", amount=float(serialized.get("cash_payments", 0))),
                DailyDataRevenueBreakdownItemResponse(label="Bank Transfer", amount=float(serialized.get("bank_transfer_payments", 0))),
            ]
        else:
            revenue_breakdown = [
                DailyDataRevenueBreakdownItemResponse(label="POS Payments", amount=float(serialized.get("pos_payments", 0))),
                DailyDataRevenueBreakdownItemResponse(label="Cash In", amount=float(serialized.get("cash_in", 0))),
            ]
        return DailyDataResponse(
            id=serialized["id"],
            business_date=serialized["business_date"],
            method=serialized["method"],
            total_revenue=serialized["total_revenue"],
            operating_revenue=serialized["total_revenue"],
            total_expenses=serialized["total_expenses"],
            operating_expenses=serialized["total_expenses"],
            invoice_document_total=float(serialized.get("uploaded_document_total", 0.0)),
            profit=serialized["profit"],
            lunch_covers=lunch_covers,
            dinner_covers=dinner_covers,
            total_covers=total_covers,
            avg_revenue_per_cover=serialized.get("avg_revenue_per_cover", 0.0),
            revenue_breakdown=revenue_breakdown,
            covers_summary=DailyDataCoversSummaryResponse(lunch=lunch_covers, dinner=dinner_covers, total=total_covers),
            register_summary=self._build_register_summary(serialized),
            method_sections=self._build_daily_data_sections(serialized),
            created_at=serialized["created_at"],
        )

    def _to_daily_data_bucket_item(self, bucket: dict[str, Any], *, anchor_date: date | None = None) -> DailyDataListItemResponse:
        business_date = datetime.fromisoformat(bucket["business_date"]).date()
        revenue = float(bucket.get("total_revenue", 0.0))
        expenses = float(bucket.get("total_expenses", 0.0))
        avg_value = float(bucket.get("avg_revenue_per_cover", 0.0))
        return DailyDataListItemResponse(
            id=str(bucket["id"]),
            record_id=str(bucket["record_id"]) if bucket.get("record_id") else None,
            business_date=bucket["business_date"],
            total_revenue=revenue,
            operating_revenue=revenue,
            total_expenses=expenses,
            operating_expenses=expenses,
            invoice_document_total=float(bucket.get("invoice_document_total", 0.0)),
            total_covers=int(bucket.get("total_covers", 0)),
            avg_revenue_per_cover=avg_value,
            created_at=str(bucket.get("created_at")),
        )

    def _to_daily_data_list_item_from_snapshot(self, snapshot: dict[str, Any], *, view: str) -> DailyDataListItemResponse:
        business_date = str(
            snapshot.get("business_date")
            or snapshot.get("period_start_date")
            or snapshot.get("week_start_date")
            or snapshot.get("month_start_date")
            or snapshot.get("period_key")
            or ""
        )
        prefix = "date" if view == "date" else view
        snapshot_id = f"{prefix}:{business_date}"
        manual_entry_count = int(snapshot.get("manual_entry_count", 0) or 0)
        manual_entry_id = snapshot.get("manual_entry_id")
        return DailyDataListItemResponse(
            id=snapshot_id,
            record_id=str(manual_entry_id) if manual_entry_id and manual_entry_count == 1 else None,
            business_date=business_date,
            total_revenue=float(snapshot.get("total_revenue", 0.0) or 0.0),
            operating_revenue=float(snapshot.get("total_revenue", 0.0) or 0.0),
            total_expenses=float(snapshot.get("total_expenses", 0.0) or 0.0),
            operating_expenses=float(snapshot.get("total_expenses", 0.0) or 0.0),
            invoice_document_total=float(snapshot.get("uploaded_document_total", 0.0) or 0.0),
            total_covers=int(snapshot.get("total_covers", 0) or 0),
            avg_revenue_per_cover=float(snapshot.get("avg_revenue_per_cover", 0.0) or 0.0),
            created_at=str(snapshot.get("updated_at") or snapshot.get("last_synced_at") or snapshot.get("created_at") or datetime.now(UTC).isoformat()),
        )

    def _to_daily_data_list_item_from_record(self, record: dict[str, Any]) -> DailyDataListItemResponse:
        serialized = self.serialize(record)
        lunch_covers = int(serialized.get("lunch_covers", 0) or 0)
        dinner_covers = int(serialized.get("dinner_covers", 0) or 0)
        total_covers = lunch_covers + dinner_covers
        return DailyDataListItemResponse(
            id=str(serialized["id"]),
            record_id=str(serialized["id"]),
            business_date=str(serialized.get("business_date") or ""),
            total_revenue=float(serialized.get("total_revenue", 0.0) or 0.0),
            operating_revenue=float(serialized.get("total_revenue", 0.0) or 0.0),
            total_expenses=float(serialized.get("total_expenses", 0.0) or 0.0),
            operating_expenses=float(serialized.get("total_expenses", 0.0) or 0.0),
            invoice_document_total=float(serialized.get("uploaded_document_total", 0.0) or 0.0),
            total_covers=total_covers,
            avg_revenue_per_cover=float(serialized.get("avg_revenue_per_cover", 0.0) or 0.0),
            created_at=str(serialized.get("created_at") or datetime.now(UTC).isoformat()),
        )

    def _to_daily_data_detail(
        self,
        bucket: dict[str, Any],
        *,
        records: list[dict[str, Any]],
        expenses: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        anchor_date: date | None = None,
        reference_date: date | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> DailyDataDetailResponse:
        list_item = self._to_daily_data_bucket_item(bucket, anchor_date=anchor_date)
        return DailyDataDetailResponse(
            business_date=list_item.business_date,
            total_revenue=list_item.total_revenue,
            operating_revenue=list_item.operating_revenue,
            total_expenses=list_item.total_expenses,
            operating_expenses=list_item.operating_expenses,
            invoice_document_total=list_item.invoice_document_total,
            total_covers=list_item.total_covers,
            avg_revenue_per_cover=list_item.avg_revenue_per_cover,
            register_summary=self._build_register_summary(bucket),
            method_sections=self._build_grouped_daily_data_sections(
                records=records,
                expenses=expenses,
                documents=documents,
                bucket=bucket,
            ),
            documents=[
                DailyDataDocumentItemResponse(
                    id=item["id"],
                    counterparty_name=item.get("counterparty_name") or item.get("supplier_name"),
                    document_number=item.get("invoice_number"),
                    document_date=item.get("invoice_date"),
                    total_amount=float(item.get("total_amount", 0)),
                    status=item.get("status", "processed"),
                    source_file_name=item.get("source_file_name", ""),
                    upload_date=item.get("upload_date", ""),
                    confirmed_at=item.get("confirmed_at"),
                )
                for item in documents
            ],
            document_count=len(documents),
        )

    def _to_inventory_item_response(self, item: dict) -> InventoryItemResponse:
        serialized = self.serialize(item)
        stock_quantity = float(serialized["stock_quantity"])
        return InventoryItemResponse(
            id=serialized["id"],
            product_name=serialized["product_name"],
            category=serialized["category"],
            stock_quantity=stock_quantity,
            unit_type=serialized["unit_type"],
            supplier_name=serialized.get("supplier_name"),
            unit_price=serialized["unit_price"],
            alert_threshold=serialized["alert_threshold"],
            stock_status=serialized["stock_status"],
            purchase_date=serialized.get("purchase_date"),
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    def _to_inventory_category_response(self, item: dict) -> InventoryCategoryResponse:
        serialized = self.serialize(item)
        return InventoryCategoryResponse(
            id=serialized["id"],
            name=str(serialized.get("name") or ""),
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    def _to_inventory_supplier_response(self, item: dict) -> InventorySupplierResponse:
        serialized = self.serialize(item)
        return InventorySupplierResponse(
            id=serialized["id"],
            name=str(serialized.get("name") or ""),
            created_at=serialized["created_at"],
            updated_at=serialized["updated_at"],
        )

    def _to_inventory_detail_response(self, item: dict) -> InventoryDetailResponse:
        base_item = self._to_inventory_item_response(item)
        serialized = self.serialize(item)
        current_stock = float(serialized.get("stock_quantity", 0))
        return InventoryDetailResponse(
            **base_item.model_dump(),
            current_stock_value=current_stock,
            history=[InventoryHistoryItemResponse(**entry) for entry in serialized.get("history", [])],
        )

    def _build_chat_insight_message(self, metrics_context: dict[str, Any], *, language: str = "en") -> str:
        revenue_total = float(metrics_context.get("revenue_total", 0))
        expense_total = float(metrics_context.get("expenses_total", 0))
        if revenue_total > 0 and expense_total >= 0:
            margin = max(revenue_total - expense_total, 0)
            if margin > 0:
                lift_percent = min(25, max(5, int(round((margin / max(revenue_total, 1)) * 15))))
                if language == "it":
                    return f"I ricavi della cena sono aumentati del {lift_percent}% questa settimana."
                return f"Your dinner revenue increased by {lift_percent}% this week."
        if language == "it":
            return "I ricavi stanno crescendo rispetto alla scorsa settimana."
        return "Your revenue is trending upward compared to last week."

    def _serialize_chat_message_for_context(self, item: dict, *, language: str) -> dict[str, Any]:
        serialized = self.serialize(item)
        message = self._resolve_localized_text(
            serialized.get("message_translations"),
            language=language,
            fallback=str(serialized.get("message") or ""),
        )
        payload = dict(serialized)
        payload["message"] = message
        attachment_summary = self._resolve_localized_text(
            serialized.get("attachment_summary_translations"),
            language=language,
            fallback=str(serialized.get("attachment_summary") or ""),
        )
        if attachment_summary:
            payload["attachment_summary"] = attachment_summary
        return payload

    @staticmethod
    def _format_activity_date(value: Any, *, language: str) -> str:
        parsed = RestaurantOperationsService._safe_parse_date(value)
        if not parsed:
            return "Dati giornalieri" if language == "it" else "Daily data"
        month_names = (
            ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
            if language == "it"
            else ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        )
        return f"{parsed.day:02d} {month_names[parsed.month - 1]} {parsed.year}"

    def _to_chat_message_response(self, item: dict, *, language: str | None = None) -> ChatMessageResponse:
        serialized = self.serialize(item)
        resolved_language = "it" if language == "it" else "en"
        message_translations = serialized.get("message_translations")
        attachment_summary_translations = serialized.get("attachment_summary_translations")
        return ChatMessageResponse(
            id=serialized["id"],
            role=serialized["role"],
            message=self._resolve_localized_text(
                message_translations,
                language=resolved_language,
                fallback=str(serialized.get("message") or ""),
            ),
            message_translations=message_translations,
            created_at=serialized["created_at"],
            updated_at=serialized.get("updated_at"),
            edited_at=serialized.get("edited_at"),
            reply_to_message_id=serialized.get("reply_to_message_id"),
            attachment_name=serialized.get("attachment_name"),
            attachment_source=serialized.get("attachment_source"),
            attachment_summary=self._resolve_localized_text(
                attachment_summary_translations,
                language=resolved_language,
                fallback=str(serialized.get("attachment_summary") or ""),
            )
            or None,
            attachment_summary_translations=attachment_summary_translations,
        )

    async def _upload_profile_image(self, current_user: dict, file: UploadFile) -> str:
        if not self.image_storage_service:
            raise ValidationException("Image upload service is not configured")
        uploaded: UploadedImage = await self.image_storage_service.upload_file(
            file=file,
            prefix=f"restaurant/profile/{current_user['_id']}",
        )
        return uploaded.url

    def _resolve_profile_image_url(self, value: str | None) -> str | None:
        if not value:
            return None
        if not self.image_storage_service:
            return value
        return self.image_storage_service.resolve_public_url(value)
