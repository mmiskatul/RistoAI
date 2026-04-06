from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


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


class ActivityItemResponse(BaseSchema):
    kind: str
    title: str
    subtitle: str
    timestamp: str


class InsightSummaryResponse(BaseSchema):
    id: str
    title: str
    summary: str
    priority: str
    metric_value: str
    metric_caption: str


class RestaurantHomePeriodResponse(BaseSchema):
    metrics: list[MetricCardResponse]
    cash_management: list[CashManagementItemResponse]
    vat_balance: float
    revenue: list[ChartPointResponse]
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
    supplier_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: float
    line_items: list[DocumentLineItemSchema]
    source_file_name: str
    ai_provider: str
    ai_summary: str


class DocumentConfirmSaveResponse(BaseSchema):
    id: str
    supplier_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: float
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
    supplier_name: str | None = Field(default=None, min_length=2, max_length=120)
    invoice_number: str | None = Field(default=None, min_length=2, max_length=80)
    invoice_date: date | None = None
    total_amount: float | None = Field(default=None, ge=0)
    line_items: list[DocumentLineItemSchema] | None = None

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_invoice_date(cls, value: object) -> object:
        return _parse_flexible_date(value)


class DocumentSaveRequest(BaseSchema):
    supplier_name: str = Field(min_length=2, max_length=120)
    invoice_number: str | None = Field(default=None, min_length=2, max_length=80)
    invoice_date: date | None = None
    total_amount: float = Field(ge=0)
    line_items: list[DocumentLineItemSchema] = Field(default_factory=list)
    source_file_name: str = Field(min_length=1, max_length=255)
    ai_provider: str = Field(min_length=2, max_length=50)
    ai_summary: str = Field(default='', max_length=2000)

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_invoice_date(cls, value: object) -> object:
        return _parse_flexible_date(value)


class DocumentListItemResponse(BaseSchema):
    id: str
    supplier_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    upload_date: str
    total_amount: float
    status: str
    line_item_count: int
    created_by_user_id: str | None = None
    last_edited_by_user_id: str | None = None
    confirmed_at: str | None = None


class DocumentDetailResponse(BaseSchema):
    id: str
    supplier_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    upload_date: str
    total_amount: float
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
    notes: str | None = Field(default=None, max_length=500)


class ExpenseResponse(BaseSchema):
    id: str
    category: str
    amount: float
    expense_date: str
    notes: str | None = None
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


class CashDepositCreateRequest(BaseSchema):
    deposit_date: date
    amount: float = Field(ge=0)
    deposit_type: str = Field(min_length=2, max_length=80)
    notes: str | None = Field(default=None, max_length=500)


class CashDepositResponse(BaseSchema):
    id: str
    deposit_date: str
    amount: float
    deposit_type: str
    notes: str | None = None
    created_at: str


class CashPeriodSummaryResponse(BaseSchema):
    total_collected: float
    cash_available: float
    withdrawals_total: float
    bank_deposits_total: float


class CashPeriodStatusResponse(BaseSchema):
    total_collected: str
    cash_available: str
    withdrawals: str
    bank_deposits: str


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
    notes: str | None = Field(default=None, max_length=500)


class DailyDataMethodTwoRequest(BaseSchema):
    business_date: date
    pos_payments: float = Field(default=0, ge=0)
    cash_payments: float = Field(default=0, ge=0)
    bank_transfer_payments: float = Field(default=0, ge=0)
    lunch_covers: int = Field(default=0, ge=0)
    dinner_covers: int = Field(default=0, ge=0)
    opening_cash: float = Field(default=0, ge=0)
    closing_cash: float = Field(default=0, ge=0)


class DailyDataCreateRequest(BaseSchema):
    method: Literal["method_1", "method_2"]
    method_one: DailyDataMethodOneRequest | None = None
    method_two: DailyDataMethodTwoRequest | None = None



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


class DailyDataResponse(BaseSchema):
    id: str
    business_date: str
    method: str
    total_revenue: float
    total_expenses: float
    profit: float
    lunch_covers: int
    dinner_covers: int
    total_covers: int
    avg_revenue_per_cover: float
    revenue_breakdown: list[DailyDataRevenueBreakdownItemResponse] = Field(default_factory=list)
    covers_summary: DailyDataCoversSummaryResponse = Field(default_factory=DailyDataCoversSummaryResponse)
    register_summary: DailyDataRegisterSummaryResponse = Field(default_factory=DailyDataRegisterSummaryResponse)
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
    kind: Literal["daily_record", "uploaded_invoice", "manual_expense"]
    label: str
    count: int = 0
    total_amount: float | None = None
    endpoint: str | None = None


class DailyDataListItemResponse(BaseSchema):
    id: str
    business_date: str
    total_revenue: float
    total_expenses: float = 0.0
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
    supplier_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: float
    status: str
    source_file_name: str
    upload_date: str
    confirmed_at: str | None = None


class DailyDataDetailResponse(BaseSchema):
    business_date: str
    total_revenue: float
    total_expenses: float
    total_covers: int
    avg_revenue_per_cover: float
    invoices: list[DailyDataDocumentItemResponse] = Field(default_factory=list)
    invoice_count: int = 0


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


class AnalyticsOverviewResponse(BaseSchema):
    insight_banner: AnalyticsInsightBannerResponse
    revenue_total: float
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


class ChatMessageCreateRequest(BaseSchema):
    message: str = Field(min_length=2, max_length=1000)
    attachment_source: str | None = Field(default=None, max_length=40)


class ChatAttachmentOptionResponse(BaseSchema):
    key: str
    label: str


class ChatQuickPromptResponse(BaseSchema):
    label: str


class ChatMessageResponse(BaseSchema):
    id: str
    role: Literal["user", "assistant", "insight"]
    message: str
    created_at: str
    attachment_name: str | None = None
    attachment_source: str | None = None
    attachment_summary: str | None = None


class ChatRealtimeConfigResponse(BaseSchema):
    enabled: bool = False
    provider: str = "socket.io"
    path: str = "/socket.io"
    namespace: str = "/restaurant-chat"
    transports: list[str] = Field(default_factory=lambda: ["websocket", "polling"])
    auth_type: str = "bearer_or_auth_token"


class ChatConversationResponse(BaseSchema):
    messages: list[ChatMessageResponse]


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
    preferred_language: str
    profile_image_url: str | None = None


class RestaurantProfileUpdateRequest(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    restaurant_name: str | None = Field(default=None, max_length=120)
    restaurant_type: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    city_location: str | None = Field(default=None, max_length=120)
    number_of_seats: int | None = Field(default=None, ge=0)

