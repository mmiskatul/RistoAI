from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator

from app.core.enums import SubscriptionPlan, SubscriptionStatus
from app.schemas.auth import validate_password_strength
from app.schemas.common import BaseSchema


CashTransactionType = Literal[
    "bank_deposit",
    "cash_deposit",
    "pos_payment",
    "cash_in",
    "bank_transfer_payment",
    "cash_withdrawal",
    "cash_out",
    "cash_expense",
]


def _parse_flexible_date(value: object) -> object:
    if value is None or isinstance(value, date):
        return value
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not candidate:
        return None
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return value


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class MetricCardResponse(BaseSchema):
    label: str
    value: float
    change_percent: float = 0.0
    currency: str = "EUR"


class CashManagementItemResponse(BaseSchema):
    label: str
    amount: float
    subtitle: str


class QuickActionResponse(BaseSchema):
    key: str
    label: str


class ChartPointResponse(BaseSchema):
    label: str
    value: float


class LocalizedTextResponse(BaseSchema):
    en: str
    it: str


class LocalizedTextListResponse(BaseSchema):
    en: list[str] = Field(default_factory=list)
    it: list[str] = Field(default_factory=list)


class LocalizedActionListResponse(BaseSchema):
    en: list[dict[str, str]] = Field(default_factory=list)
    it: list[dict[str, str]] = Field(default_factory=list)


class ActivityItemResponse(BaseSchema):
    kind: str
    title: str
    subtitle: str
    timestamp: str
    entity_id: str | None = None
    reference_date: str | None = None
    source_kind: str | None = None
    source_entity_id: str | None = None
    route: str | None = None


class InsightSummaryResponse(BaseSchema):
    id: str
    title: str
    summary: str
    priority: str
    metric_value: str
    metric_caption: str
    title_translations: LocalizedTextResponse | None = None
    summary_translations: LocalizedTextResponse | None = None
    metric_caption_translations: LocalizedTextResponse | None = None


class RestaurantHomePeriodResponse(BaseSchema):
    metrics: list[MetricCardResponse]
    cash_management: list[CashManagementItemResponse]
    vat_balance: float
    revenue: list[ChartPointResponse]
    operating_revenue_total: float = 0.0
    invoice_document_total: float = 0.0
    featured_insight: InsightSummaryResponse | None = None


class RestaurantHomeResponse(BaseSchema):
    greeting_name: str
    restaurant_name: str | None = None
    preferred_language: str
    available_periods: list[str] = Field(default_factory=lambda: ["weekly", "monthly"])
    weekly: RestaurantHomePeriodResponse
    monthly: RestaurantHomePeriodResponse
    quick_actions: list[QuickActionResponse]
    recent_activity: list[ActivityItemResponse]


class RestaurantHomeMetricsResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[MetricCardResponse] = Field(default_factory=list)


class RestaurantHomeCashManagementResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[CashManagementItemResponse] = Field(default_factory=list)


class RestaurantHomeRevenueResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[ChartPointResponse] = Field(default_factory=list)


class RestaurantHomeInsightResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    insight: InsightSummaryResponse | None = None


class RestaurantHomeRecentActivityResponse(BaseSchema):
    items: list[ActivityItemResponse] = Field(default_factory=list)


class RestaurantNotificationFeedResponse(BaseSchema):
    items: list[ActivityItemResponse] = Field(default_factory=list)


class RestaurantHomeVatBalanceResponse(BaseSchema):
    balance: float


class VatOverviewResponse(BaseSchema):
    estimated_vat_balance: float
    vat_payable: float
    vat_receivable: float
    filing_deadline: str | None = None
    report_ready: bool


class InsightActionResponse(BaseSchema):
    title: str
    description: str
    action_label: str = "Apply"


class InsightRelatedItemResponse(BaseSchema):
    label: str
    value: str
    subtitle: str | None = None


class InsightDetailResponse(BaseSchema):
    id: str
    title: str
    priority: str
    metric_value: str
    metric_caption: str
    trend: list[ChartPointResponse]
    root_causes: list[str]
    recommended_actions: list[InsightActionResponse]
    other_related_insights: list[InsightRelatedItemResponse]
    title_translations: LocalizedTextResponse | None = None
    metric_caption_translations: LocalizedTextResponse | None = None
    root_causes_translations: LocalizedTextListResponse | None = None
    recommended_actions_translations: LocalizedActionListResponse | None = None


class DocumentLineItemSchema(BaseSchema):
    product_name: str
    quantity: float = Field(ge=0)
    unit_price: float = Field(ge=0)
    total_price: float = Field(ge=0)


class DocumentUploadExtractRequest(BaseSchema):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    file_base64: str = Field(min_length=8)


class DocumentExtractionResponse(BaseSchema):
    document_type: Literal["expense", "cash", "revenue", "profit", "unknown"] = "unknown"
    document_label: str
    counterparty_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    total_amount: float
    currency: str = "EUR"
    expense_amount: float = 0
    cash_amount: float = 0
    revenue_amount: float = 0
    profit_amount: float = 0
    line_items: list[DocumentLineItemSchema]
    source_file_name: str
    ai_provider: str
    ai_summary: str


class DocumentConfirmSaveResponse(BaseSchema):
    id: str
    document_type: Literal["expense", "cash", "revenue", "profit", "unknown"] = "unknown"
    document_label: str
    counterparty_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    total_amount: float
    currency: str = "EUR"
    expense_amount: float = 0
    cash_amount: float = 0
    revenue_amount: float = 0
    profit_amount: float = 0
    line_items: list[DocumentLineItemSchema]
    source_file_name: str
    ai_provider: str
    ai_summary: str
    upload_date: str
    status: str
    created_by_user_id: str | None = None
    last_edited_by_user_id: str | None = None
    confirmed_by_user_id: str | None = None
    confirmed_at: str | None = None


class DocumentConfirmRequest(BaseSchema):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=120)
    invoice_number: str | None = Field(default=None, min_length=1, max_length=80)
    invoice_date: date | None = None
    total_amount: float | None = Field(default=None, ge=0)
    line_items: list[DocumentLineItemSchema] | None = None

    @field_validator("supplier_name", "invoice_number", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_invoice_date(cls, value: object) -> object:
        return _parse_flexible_date(value)


class DocumentSaveRequest(BaseSchema):
    document_type: Literal["expense", "cash", "revenue", "profit", "unknown"] = "unknown"
    document_label: str | None = Field(default=None, min_length=1, max_length=80)
    counterparty_name: str | None = Field(default=None, min_length=1, max_length=120)
    supplier_name: str | None = Field(default=None, min_length=1, max_length=120)
    invoice_number: str | None = Field(default=None, min_length=1, max_length=80)
    invoice_date: date | None = None
    total_amount: float = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=10)
    expense_amount: float = Field(default=0, ge=0)
    cash_amount: float = Field(default=0, ge=0)
    revenue_amount: float = Field(default=0, ge=0)
    profit_amount: float = 0
    line_items: list[DocumentLineItemSchema] = Field(default_factory=list)
    source_file_name: str = Field(min_length=1, max_length=255)
    ai_provider: str = Field(min_length=2, max_length=50)
    ai_summary: str = Field(default='', max_length=2000)

    @field_validator("document_label", "counterparty_name", "supplier_name", "invoice_number", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _blank_to_none(value)

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_invoice_date(cls, value: object) -> object:
        return _parse_flexible_date(value)


class DocumentListItemResponse(BaseSchema):
    id: str
    document_type: Literal["expense", "cash", "revenue", "profit", "unknown"] = "unknown"
    document_label: str | None = None
    counterparty_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    upload_date: str
    total_amount: float
    status: str
    line_item_count: int
    created_by_user_id: str | None = None
    last_edited_by_user_id: str | None = None
    confirmed_at: str | None = None


class DocumentDetailResponse(BaseSchema):
    id: str
    document_type: Literal["expense", "cash", "revenue", "profit", "unknown"] = "unknown"
    document_label: str | None = None
    counterparty_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    upload_date: str
    total_amount: float
    currency: str = "EUR"
    expense_amount: float = 0
    cash_amount: float = 0
    revenue_amount: float = 0
    profit_amount: float = 0
    status: str
    ai_provider: str
    ai_summary: str
    line_items: list[DocumentLineItemSchema]
    created_at: str
    updated_at: str


class DocumentListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[DocumentListItemResponse]


class ExpenseCreateRequest(BaseSchema):
    category: str = Field(min_length=2, max_length=120)
    amount: float = Field(ge=0)
    expense_date: date
    section: Literal["cash", "bank"] = "cash"
    notes: str | None = Field(default=None, max_length=500)


class ExpenseResponse(BaseSchema):
    id: str
    category: str
    amount: float
    expense_date: str
    section: Literal["cash", "bank"] = "cash"
    notes: str | None = None
    source_kind: str | None = None
    source_id: str | None = None
    source_inventory_item_id: str | None = None
    created_at: str


class ExpenseSummaryResponse(BaseSchema):
    today_total: float
    week_total: float
    month_total: float
    top_category: str | None = None


class ExpenseDistributionItemResponse(BaseSchema):
    label: str
    percentage: float


class ExpensePeriodResponse(BaseSchema):
    total: float
    top_category: str | None = None
    distribution: list[ExpenseDistributionItemResponse] = Field(default_factory=list)
    items: list[ExpenseResponse]


class ExpenseListResponse(BaseSchema):
    today: ExpensePeriodResponse
    this_week: ExpensePeriodResponse
    this_month: ExpensePeriodResponse
    this_year: ExpensePeriodResponse


class BankAccountCreateRequest(BaseSchema):
    bank_account: str = Field(
        min_length=2,
        max_length=80,
        validation_alias=AliasChoices("bank_account", "bank account", "bank account "),
    )


class BankAccountUpdateRequest(BaseSchema):
    bank_account: str = Field(
        min_length=2,
        max_length=80,
        validation_alias=AliasChoices("bank_account", "bank account", "bank account "),
    )


class BankAccountResponse(BaseSchema):
    id: str
    bank_account: str
    deposited_amount: float = 0.0
    created_at: str


class BankAccountListResponse(BaseSchema):
    total_accounts: int
    items: list[BankAccountResponse] = Field(default_factory=list)


class CashDepositCreateRequest(BaseSchema):
    deposit_date: date
    amount: float = Field(ge=0)
    type: Literal["bank_deposit", "cash_deposit"] = Field(default="bank_deposit", validation_alias=AliasChoices("type", "deposit_type"))
    bank_account: str = Field(
        min_length=2,
        max_length=80,
        validation_alias=AliasChoices("bank_account", "bank account", "bank account "),
    )
    notes: str | None = Field(default=None, max_length=500)


class CashDepositUpdateRequest(BaseSchema):
    deposit_date: date
    amount: float = Field(ge=0)
    type: Literal["bank_deposit", "cash_deposit"] = Field(default="bank_deposit", validation_alias=AliasChoices("type", "deposit_type"))
    bank_account: str = Field(
        min_length=2,
        max_length=80,
        validation_alias=AliasChoices("bank_account", "bank account", "bank account "),
    )
    notes: str | None = Field(default=None, max_length=500)


class CashDepositResponse(BaseSchema):
    id: str
    deposit_date: str
    amount: float
    type: CashTransactionType = "bank_deposit"
    bank_account: str
    notes: str | None = None
    source_kind: str | None = None
    source_id: str | None = None
    source_subtype: str | None = None
    created_at: str

    @computed_field
    @property
    def amount_formatted(self) -> str:
        return f"€{self.amount:,.2f}" if self.amount >= 0 else f"-€{abs(self.amount):,.2f}"

    @computed_field
    @property
    def deposit_date_formatted(self) -> str:
        parsed = _parse_flexible_date(self.deposit_date)
        if isinstance(parsed, date):
            return parsed.strftime("%b %d, %Y")
        if isinstance(self.deposit_date, str):
            try:
                return datetime.fromisoformat(self.deposit_date.replace("Z", "+00:00")).strftime("%b %d, %Y")
            except ValueError:
                pass
        return self.deposit_date

    @computed_field
    @property
    def display_title(self) -> str:
        return self.bank_account


class CashPeriodSummaryResponse(BaseSchema):
    total_collected: float
    cash_available: float
    pos_payments: float
    withdrawals_total: float
    bank_deposits: float


class CashPeriodStatusResponse(BaseSchema):
    total_collected: str
    cash_available: str
    pos_payments: str
    withdrawals: str
    bank_deposits: str
    cash_deposits: str
    deposits_collection: str


class CashPeriodOverviewResponse(BaseSchema):
    summary: CashPeriodSummaryResponse
    status: CashPeriodStatusResponse
    recent_deposits: list[CashDepositResponse] = Field(default_factory=list)


class CashOverviewPeriodsResponse(BaseSchema):
    today: CashPeriodOverviewResponse
    this_week: CashPeriodOverviewResponse
    this_month: CashPeriodOverviewResponse


class CashManagementSummaryResponse(BaseSchema):
    active_period: str = "today"
    periods: CashOverviewPeriodsResponse


class DailyDataMethodOneRequest(BaseSchema):
    business_date: date
    pos_payments: float = Field(default=0, ge=0)
    cash_withdrawals: float = Field(default=0, ge=0)
    cash_in: float = Field(default=0, ge=0)
    cash_out: float = Field(default=0, ge=0)
    expenses_in_cash: float = Field(default=0, ge=0)
    lunch_covers: int = Field(default=0, ge=0)
    dinner_covers: int = Field(default=0, ge=0)
    opening_cash: float = Field(default=0, ge=0)
    closing_cash: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class DailyDataMethodTwoRequest(BaseSchema):
    business_date: date
    pos_payments: float = Field(default=0, ge=0)
    cash_payments: float = Field(default=0, ge=0)
    bank_transfer_payments: float = Field(default=0, ge=0)
    expenses_in_cash: float = Field(default=0, ge=0)
    lunch_covers: int = Field(default=0, ge=0)
    dinner_covers: int = Field(default=0, ge=0)
    opening_cash: float = Field(default=0, ge=0)
    closing_cash: float = Field(default=0, ge=0)


class DailyDataInventoryUsageRequest(BaseSchema):
    inventory_item_id: str = Field(min_length=1)
    quantity_used: float = Field(gt=0)


class DailyDataCreateRequest(BaseSchema):
    method: Literal["method_1", "method_2"]
    method_one: DailyDataMethodOneRequest | None = None
    method_two: DailyDataMethodTwoRequest | None = None
    inventory_usage: list[DailyDataInventoryUsageRequest] = Field(default_factory=list)



class DailyDataFormFieldResponse(BaseSchema):
    key: str
    label: str
    value_type: Literal["number", "integer", "string", "date"]
    placeholder: str | None = None
    section: str | None = None
    required: bool = False


class DailyDataManualMethodResponse(BaseSchema):
    key: Literal["method_1", "method_2"]
    label: str
    description: str
    fields: list[DailyDataFormFieldResponse] = Field(default_factory=list)


class DailyDataManualEntryResponse(BaseSchema):
    methods: list[DailyDataManualMethodResponse] = Field(default_factory=list)


class DailyDataRevenueBreakdownItemResponse(BaseSchema):
    label: str
    amount: float


class DailyDataCoversSummaryResponse(BaseSchema):
    lunch: int = 0
    dinner: int = 0
    total: int = 0


class DailyDataRegisterSummaryResponse(BaseSchema):
    opening_cash: float = 0.0
    closing_cash: float = 0.0
    cash_payments: float = 0.0
    total_cash_on_hand: float = 0.0
    cash_difference: float = 0.0


class DailyDataSectionFieldResponse(BaseSchema):
    key: str
    label: str
    value: float | int | str | None = None
    value_type: Literal["currency", "integer", "text"] = "text"


class DailyDataSectionResponse(BaseSchema):
    key: str
    title: str
    fields: list[DailyDataSectionFieldResponse] = Field(default_factory=list)


class DailyDataResponse(BaseSchema):
    id: str
    business_date: str
    method: str
    total_revenue: float
    operating_revenue: float
    total_expenses: float
    operating_expenses: float
    invoice_document_total: float = 0.0
    profit: float
    lunch_covers: int
    dinner_covers: int
    total_covers: int
    avg_revenue_per_cover: float
    revenue_breakdown: list[DailyDataRevenueBreakdownItemResponse] = Field(default_factory=list)
    covers_summary: DailyDataCoversSummaryResponse = Field(default_factory=DailyDataCoversSummaryResponse)
    register_summary: DailyDataRegisterSummaryResponse = Field(default_factory=DailyDataRegisterSummaryResponse)
    method_sections: list[DailyDataSectionResponse] = Field(default_factory=list)
    created_at: str


class DailyDataSummaryCardResponse(BaseSchema):
    label: str
    value: float
    value_prefix: str | None = None
    value_formatted: str | None = None
    icon_key: str | None = None


class DailyDataListItemActionResponse(BaseSchema):
    view_endpoint: str | None = None
    delete_endpoint: str | None = None


class DailyDataEntrySourceResponse(BaseSchema):
    kind: Literal["daily_record", "uploaded_document", "manual_expense"]
    label: str
    count: int = 0
    total_amount: float | None = None
    endpoint: str | None = None


class DailyDataListItemResponse(BaseSchema):
    id: str
    record_id: str | None = None
    business_date: str
    total_revenue: float
    operating_revenue: float
    total_expenses: float = 0.0
    operating_expenses: float = 0.0
    invoice_document_total: float = 0.0
    total_covers: int
    avg_revenue_per_cover: float
    created_at: str


class DailyDataListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[DailyDataListItemResponse]



class DailyDataDocumentItemResponse(BaseSchema):
    id: str
    counterparty_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    total_amount: float
    status: str
    source_file_name: str
    upload_date: str
    confirmed_at: str | None = None


class DailyDataDetailResponse(BaseSchema):
    business_date: str
    total_revenue: float
    operating_revenue: float
    total_expenses: float
    operating_expenses: float
    invoice_document_total: float = 0.0
    total_covers: int
    avg_revenue_per_cover: float
    register_summary: DailyDataRegisterSummaryResponse = Field(default_factory=DailyDataRegisterSummaryResponse)
    method_sections: list[DailyDataSectionResponse] = Field(default_factory=list)
    documents: list[DailyDataDocumentItemResponse] = Field(default_factory=list)
    document_count: int = 0


class DailyDataCollectionResponse(BaseSchema):
    total: int
    items: list[DailyDataDetailResponse] = Field(default_factory=list)


class InventoryCreateRequest(BaseSchema):
    product_name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    stock_quantity: float = Field(ge=0)
    unit_type: str = Field(min_length=1, max_length=30)
    supplier_name: str | None = Field(default=None, max_length=120)
    unit_price: float = Field(default=0, ge=0)
    alert_threshold: float = Field(default=0, ge=0)
    purchase_date: date | None = None


class InventoryUpdateRequest(BaseSchema):
    product_name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    stock_quantity: float | None = Field(default=None, ge=0)
    unit_type: str | None = Field(default=None, min_length=1, max_length=30)
    supplier_name: str | None = Field(default=None, max_length=120)
    unit_price: float | None = Field(default=None, ge=0)
    alert_threshold: float | None = Field(default=None, ge=0)
    purchase_date: date | None = None


class InventoryCategoryCreateRequest(BaseSchema):
    name: str = Field(min_length=2, max_length=80)


class InventoryCategoryResponse(BaseSchema):
    id: str
    name: str
    created_at: str
    updated_at: str


class InventoryCategoryListResponse(BaseSchema):
    items: list[InventoryCategoryResponse] = Field(default_factory=list)


class InventorySupplierCreateRequest(BaseSchema):
    name: str = Field(min_length=2, max_length=120)


class InventorySupplierResponse(BaseSchema):
    id: str
    name: str
    created_at: str
    updated_at: str


class InventorySupplierListResponse(BaseSchema):
    items: list[InventorySupplierResponse] = Field(default_factory=list)


class InventoryStockUpdateRequest(BaseSchema):
    add_stock: float = Field(default=0, ge=0)
    remove_stock: float = Field(default=0, ge=0)


class InventoryHistoryItemResponse(BaseSchema):
    kind: str
    quantity_delta: float
    occurred_at: str


class InventoryListItemActionResponse(BaseSchema):
    view_endpoint: str | None = None
    stock_update_endpoint: str | None = None


class InventorySupplierCardResponse(BaseSchema):
    supplier_name: str | None = None
    supplier_role: str = "Primary Distributor"
    last_purchase: str | None = None
    price_per_unit: str | None = None


class InventoryItemResponse(BaseSchema):
    id: str
    product_name: str
    category: str
    stock_quantity: float
    unit_type: str
    supplier_name: str | None = None
    unit_price: float
    alert_threshold: float
    stock_status: str
    purchase_date: str | None = None
    created_at: str
    updated_at: str


class InventoryDetailResponse(InventoryItemResponse):
    current_stock_value: float = 0.0
    history: list[InventoryHistoryItemResponse]


class InventoryValueResponse(BaseSchema):
    total_inventory_value: float


class InventoryListResponse(BaseSchema):
    total_inventory_value: float
    total: int
    page: int
    page_size: int
    pages: int
    items: list[InventoryItemResponse]


class AnalyticsInsightBannerResponse(BaseSchema):
    title: str
    subtitle: str
    ai_provider: str = "fallback"
    title_translations: LocalizedTextResponse | None = None
    subtitle_translations: LocalizedTextResponse | None = None


class AnalyticsMetricTileResponse(BaseSchema):
    label: str
    value: float | str
    change_percent: float | None = None
    subtitle: str | None = None


class AnalyticsSummaryStatResponse(BaseSchema):
    label: str
    value: float | int


class AnalyticsComparisonRowResponse(BaseSchema):
    label: str
    value: float


class AnalyticsSupplierAlertResponse(BaseSchema):
    title: str
    subtitle: str
    ai_provider: str = "fallback"
    title_translations: LocalizedTextResponse | None = None
    subtitle_translations: LocalizedTextResponse | None = None


class AnalyticsOverviewResponse(BaseSchema):
    insight_banner: AnalyticsInsightBannerResponse | None = None
    revenue_total: float
    operating_revenue_total: float
    invoice_document_total: float = 0.0
    revenue_change_percent: float
    weekly_revenue: list[ChartPointResponse]
    metric_tiles: list[AnalyticsMetricTileResponse] = Field(default_factory=list)
    summary_stats: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    revenue_comparison: list[AnalyticsComparisonRowResponse] = Field(default_factory=list)
    covers_total: int
    covers_activity: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    avg_revenue_per_cover: float
    cost_breakdown: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    supplier_price_alerts: list[AnalyticsSupplierAlertResponse] = Field(default_factory=list)


class AnalyticsMetricTilesResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[AnalyticsMetricTileResponse] = Field(default_factory=list)


class AnalyticsRevenueTrendResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    revenue_total: float
    change_percent: float
    points: list[ChartPointResponse] = Field(default_factory=list)


class AnalyticsSummaryStatsResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)


class AnalyticsRevenueComparisonResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[AnalyticsComparisonRowResponse] = Field(default_factory=list)


class AnalyticsActivityCostResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    covers_activity: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    cost_breakdown: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)


class AnalyticsCoversActivityResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)


class AnalyticsCostBreakdownResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)


class AnalyticsSupplierAlertsResponse(BaseSchema):
    period: Literal["weekly", "monthly"]
    items: list[AnalyticsSupplierAlertResponse] = Field(default_factory=list)


class ChatMessageCreateRequest(BaseSchema):
    message: str = Field(min_length=2, max_length=1000)
    attachment_source: str | None = Field(default=None, max_length=40)
    language: str | None = Field(default=None, max_length=20)


class ChatMessageUpdateRequest(BaseSchema):
    message: str = Field(min_length=2, max_length=1000)
    language: str | None = Field(default=None, max_length=20)


class ChatAttachmentOptionResponse(BaseSchema):
    key: str
    label: str


class ChatQuickPromptResponse(BaseSchema):
    label: str


class ChatMessageResponse(BaseSchema):
    id: str
    role: Literal["user", "assistant", "insight"]
    message: str
    message_translations: LocalizedTextResponse | None = None
    created_at: str | None = None
    updated_at: str | None = None
    edited_at: str | None = None
    reply_to_message_id: str | None = None
    attachment_name: str | None = None
    attachment_source: str | None = None
    attachment_summary: str | None = None
    attachment_summary_translations: LocalizedTextResponse | None = None


class ChatRealtimeConfigResponse(BaseSchema):
    enabled: bool = False
    provider: str = "socket.io"
    path: str = "/socket.io"
    namespace: str = "/restaurant-chat"
    transports: list[str] = Field(default_factory=lambda: ["websocket", "polling"])
    auth_type: str = "bearer_or_auth_token"


class ChatConversationResponse(BaseSchema):
    messages: list[ChatMessageResponse]


class ChatVoiceTranscriptionResponse(BaseSchema):
    text: str


class SettingsLanguageOptionResponse(BaseSchema):
    code: str
    label: str
    active: bool = False


class SettingsActionItemResponse(BaseSchema):
    label: str
    endpoint: str


class RestaurantProfileResponse(BaseSchema):
    full_name: str
    email: str
    phone: str | None = None
    restaurant_name: str | None = None
    restaurant_type: str | None = None
    location: str | None = None
    city_location: str | None = None
    number_of_seats: int | None = None
    average_spend_per_customer: float | None = None
    main_business_goal: str | None = None
    biggest_problem: str | None = None
    improvement_focus: str | None = None
    preferred_language: str
    profile_image_url: str | None = None
    interior_photo_url: str | None = None
    exterior_photo_url: str | None = None


class RestaurantProfileUpdateRequest(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    restaurant_name: str | None = Field(default=None, max_length=120)
    restaurant_type: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    city_location: str | None = Field(default=None, max_length=120)
    number_of_seats: int | None = Field(default=None, ge=0)
    average_spend_per_customer: float | None = Field(default=None, ge=0)
    main_business_goal: str | None = Field(default=None, max_length=120)
    biggest_problem: str | None = Field(default=None, max_length=1000)
    improvement_focus: str | None = Field(default=None, max_length=1000)
    profile_image_url: str | None = None


class RestaurantSettingsSubscriptionResponse(BaseSchema):
    selection_required: bool
    plan_name: str | None = None
    billing_cycle: SubscriptionPlan | None = None
    status: SubscriptionStatus | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    plans_endpoint: str = "/api/v1/subscriptions/user/plans"
    checkout_endpoint: str = "/api/v1/subscriptions/user/checkout-session"
    customer_portal_endpoint: str = "/api/v1/subscriptions/user/customer-portal"
    cancel_endpoint: str = "/api/v1/subscriptions/user/cancel"


class RestaurantNotificationSettingsResponse(BaseSchema):
    email_notifications: bool = True
    push_notifications: bool = True
    marketing_notifications: bool = False
    low_stock_alerts: bool = True
    daily_summary_notifications: bool = True


class RestaurantNotificationSettingsUpdateRequest(BaseSchema):
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    marketing_notifications: bool | None = None
    low_stock_alerts: bool | None = None
    daily_summary_notifications: bool | None = None


class PushDeviceRegistrationRequest(BaseSchema):
    expo_push_token: str = Field(min_length=8, max_length=255)
    device_id: str = Field(min_length=8, max_length=120)
    platform: Literal["ios", "android", "web", "unknown"] = "unknown"
    device_name: str | None = Field(default=None, max_length=120)


class PushDeviceUnregisterRequest(BaseSchema):
    device_id: str = Field(min_length=8, max_length=120)


class RestaurantChangePasswordRequest(BaseSchema):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "RestaurantChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm password must match")
        return self

