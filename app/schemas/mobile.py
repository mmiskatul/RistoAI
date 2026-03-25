from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import BaseSchema


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


class MobileHomeResponse(BaseSchema):
    greeting_name: str
    restaurant_name: str | None = None
    preferred_language: str
    metrics: list[MetricCardResponse]
    cash_management: list[CashManagementItemResponse]
    quick_actions: list[QuickActionResponse]
    vat_balance: float
    weekly_revenue: list[ChartPointResponse]
    featured_insight: InsightSummaryResponse | None = None
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
    page_title: str = "AI Business Insights"
    subtitle: str
    badge_label: str
    title: str
    priority: str
    metric_value: str
    metric_caption: str
    trend: list[ChartPointResponse]
    root_causes: list[str]
    recommended_actions: list[InsightActionResponse]
    other_related_insights: list[InsightRelatedItemResponse]
    export_label: str = "Export"


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
    ai_provider: str
    ai_summary: str
    source_file_name: str
    line_items: list[DocumentLineItemSchema]


class DocumentConfirmRequest(BaseSchema):
    supplier_name: str | None = Field(default=None, min_length=2, max_length=120)
    invoice_number: str | None = Field(default=None, min_length=2, max_length=80)
    invoice_date: date | None = None
    total_amount: float | None = Field(default=None, ge=0)
    line_items: list[DocumentLineItemSchema] | None = None


class DocumentSaveRequest(BaseSchema):
    supplier_name: str = Field(min_length=2, max_length=120)
    invoice_number: str | None = Field(default=None, min_length=2, max_length=80)
    invoice_date: date | None = None
    total_amount: float = Field(ge=0)
    line_items: list[DocumentLineItemSchema] = Field(default_factory=list)
    source_file_name: str = Field(min_length=1, max_length=255)
    ai_provider: str = Field(min_length=2, max_length=50)
    ai_summary: str = Field(default='', max_length=2000)


class DocumentListItemResponse(BaseSchema):
    id: str
    supplier_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    upload_date: str
    total_amount: float
    status: str
    line_item_count: int
    source_file_name: str
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
    source_file_name: str
    line_items: list[DocumentLineItemSchema]
    created_at: str
    updated_at: str
    created_by_user_id: str | None = None
    last_edited_by_user_id: str | None = None
    last_edited_at: str | None = None
    confirmed_by_user_id: str | None = None
    confirmed_at: str | None = None


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


class ExpenseListResponse(BaseSchema):
    summary: ExpenseSummaryResponse
    total: int
    page: int
    page_size: int
    pages: int
    items: list[ExpenseResponse]


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


class CashManagementSummaryResponse(BaseSchema):
    total_collected: float
    cash_available: float
    withdrawals_total: float
    bank_deposits_total: float
    recent_deposits: list[CashDepositResponse]


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


class DailyDataResponse(BaseSchema):
    id: str
    business_date: str
    method: str
    total_revenue: float
    total_expenses: float
    profit: float
    lunch_covers: int
    dinner_covers: int
    avg_revenue_per_cover: float
    created_at: str


class DailyDataListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[DailyDataResponse]


class InventoryCreateRequest(BaseSchema):
    product_name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    stock_quantity: float = Field(ge=0)
    unit_type: str = Field(min_length=1, max_length=30)
    supplier_name: str | None = Field(default=None, max_length=120)
    unit_price: float = Field(default=0, ge=0)
    alert_threshold: float = Field(default=0, ge=0)
    purchase_date: date | None = None


class InventoryStockUpdateRequest(BaseSchema):
    add_stock: float = Field(default=0, ge=0)
    remove_stock: float = Field(default=0, ge=0)


class InventoryHistoryItemResponse(BaseSchema):
    kind: str
    quantity_delta: float
    occurred_at: str


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
    history: list[InventoryHistoryItemResponse]


class InventoryListResponse(BaseSchema):
    total_inventory_value: float
    total: int
    page: int
    page_size: int
    pages: int
    items: list[InventoryItemResponse]


class AnalyticsOverviewResponse(BaseSchema):
    estimated_profit: float
    peak_hour_label: str
    revenue_total: float
    revenue_change_percent: float
    covers_total: int
    avg_revenue_per_cover: float
    weekly_revenue: list[ChartPointResponse]


class ChatMessageCreateRequest(BaseSchema):
    message: str = Field(min_length=2, max_length=1000)


class ChatMessageResponse(BaseSchema):
    id: str
    role: Literal["user", "assistant"]
    message: str
    created_at: str


class ChatConversationResponse(BaseSchema):
    messages: list[ChatMessageResponse]


class MobileProfileResponse(BaseSchema):
    full_name: str
    email: str
    phone: str | None = None
    restaurant_name: str | None = None
    location: str | None = None
    preferred_language: str


class MobileProfileUpdateRequest(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    restaurant_name: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)

