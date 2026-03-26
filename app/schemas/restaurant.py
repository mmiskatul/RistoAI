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


class RestaurantHomeResponse(BaseSchema):
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
    line_items: list[DocumentLineItemSchema]
    source_file_name: str
    ai_provider: str
    ai_summary: str


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
    invoice_number_display: str | None = None
    invoice_date: str | None = None
    invoice_date_formatted: str | None = None
    upload_date: str
    total_amount: float
    total_amount_formatted: str | None = None
    status: str
    status_label: str | None = None
    status_note: str | None = None
    line_item_count: int
    line_item_count_label: str | None = None
    source_file_name: str
    primary_action_label: str | None = None
    secondary_action_label: str | None = None
    primary_action_endpoint: str | None = None
    secondary_action_endpoint: str | None = None
    created_by_user_id: str | None = None
    last_edited_by_user_id: str | None = None
    confirmed_at: str | None = None


class DocumentDetailResponse(BaseSchema):
    page_title: str = "Document Details"
    preview_title: str = "Document Preview"
    preview_image_url: str | None = None
    document_information_title: str = "Document Information"
    extracted_data_title: str = "Extracted Data"
    supplier_name_label: str = "Supplier Name"
    total_amount_label: str = "Total Amount"
    invoice_date_label: str = "Invoice Date"
    upload_date_label: str = "Upload Date"
    edit_button_label: str = "Edit Data"
    download_button_label: str = "Download"
    delete_button_label: str = "Delete Document"
    id: str
    supplier_name: str
    invoice_number: str | None = None
    invoice_number_display: str | None = None
    invoice_date: str | None = None
    invoice_date_formatted: str | None = None
    upload_date: str
    upload_date_formatted: str | None = None
    total_amount: float
    total_amount_formatted: str | None = None
    status: str
    status_label: str | None = None
    ai_provider: str
    ai_summary: str
    source_file_name: str
    source_label: str | None = None
    line_items: list[DocumentLineItemSchema]
    edit_endpoint: str | None = None
    download_endpoint: str | None = None
    delete_endpoint: str | None = None
    created_at: str
    updated_at: str
    created_by_user_id: str | None = None
    last_edited_by_user_id: str | None = None
    last_edited_at: str | None = None
    confirmed_by_user_id: str | None = None
    confirmed_at: str | None = None


class DocumentListResponse(BaseSchema):
    page_title: str = "Documents"
    search_placeholder: str = "Search invoices, suppliers..."
    filter_labels: list[str] = Field(default_factory=lambda: ["Date", "Supplier", "Status"])
    upload_button_label: str = "Upload Invoice"
    upload_endpoint: str = "/api/v1/restaurant/documents/upload-extract"
    ai_banner_title: str = "AI Data Extraction Active"
    ai_banner_subtitle: str = "Risto AI automatically extracts supplier, date, line items, quantities, and unit prices from your uploads."
    recent_documents_title: str = "Recent Documents"
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
    amount_formatted: str | None = None
    expense_date: str
    expense_date_formatted: str | None = None
    notes: str | None = None
    subtitle: str | None = None
    created_at: str


class ExpenseSummaryResponse(BaseSchema):
    today_total: float
    today_total_formatted: str | None = None
    week_total: float
    week_total_formatted: str | None = None
    month_total: float
    month_total_formatted: str | None = None
    top_category: str | None = None


class ExpenseDistributionItemResponse(BaseSchema):
    label: str
    percentage: float
    percentage_label: str


class ExpenseListResponse(BaseSchema):
    page_title: str = "Expenses"
    subtitle: str = "Track and manage all restaurant operational costs"
    add_button_label: str = "Add Expense"
    add_button_endpoint: str = "/api/v1/restaurant/expenses"
    period_filters: list[str] = Field(default_factory=lambda: ["Today", "This Week", "This Month", "This Year"])
    active_period: str = "Today"
    quick_summary_title: str = "Quick Summary"
    expense_distribution_title: str = "Expense Distribution"
    recent_transactions_title: str = "Recent Transactions"
    summary: ExpenseSummaryResponse
    distribution_total_label: str | None = None
    expense_distribution: list[ExpenseDistributionItemResponse] = Field(default_factory=list)
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
    deposit_date_formatted: str | None = None
    amount: float
    amount_formatted: str | None = None
    deposit_type: str
    display_title: str | None = None
    display_subtitle: str | None = None
    notes: str | None = None
    created_at: str


class CashManagementSummaryResponse(BaseSchema):
    page_title: str = "Cash Management"
    subtitle: str = "Track and manage your restaurant's physical cash flow and bank deposits."
    add_button_label: str = "Add Bank Deposit"
    add_button_endpoint: str = "/api/v1/restaurant/cash/deposits"
    period_filters: list[str] = Field(default_factory=lambda: ["Today", "This Week", "This Month", "This Year"])
    active_period: str = "Today"
    total_collected: float
    total_collected_formatted: str | None = None
    total_collected_status: str = "TODAY"
    cash_available: float
    cash_available_formatted: str | None = None
    cash_available_status: str = "IN SAFE"
    withdrawals_total: float
    withdrawals_total_formatted: str | None = None
    withdrawals_status: str = "TODAY"
    bank_deposits_total: float
    bank_deposits_total_formatted: str | None = None
    bank_deposits_status: str = "TODAY"
    recent_deposits_title: str = "Recent Deposits"
    recent_deposits_view_all_label: str = "View All"
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
    page_title: str = "Add Daily Business Data"
    subtitle: str = "Enter today's revenue and expenses to track your restaurant performance."
    save_button_label: str = "Save Daily Data"
    methods: list[DailyDataManualMethodResponse] = Field(default_factory=list)


class DailyDataRevenueBreakdownItemResponse(BaseSchema):
    label: str
    amount: float
    amount_formatted: str


class DailyDataCoversSummaryResponse(BaseSchema):
    lunch: int = 0
    dinner: int = 0
    total: int = 0


class DailyDataRegisterSummaryResponse(BaseSchema):
    opening_cash: float = 0.0
    opening_cash_formatted: str = "$0.00"
    closing_cash: float = 0.0
    closing_cash_formatted: str = "$0.00"


class DailyDataResponse(BaseSchema):
    id: str
    page_title: str = "Daily Record Details"
    report_for_label: str = "Reports For"
    business_date: str
    method: str
    status_label: str = "CLOSED"
    total_revenue: float
    total_expenses: float
    profit: float
    net_profit_formatted: str = "$0.00"
    total_revenue_formatted: str = "$0.00"
    total_expenses_formatted: str = "$0.00"
    lunch_covers: int
    dinner_covers: int
    total_covers: int
    avg_revenue_per_cover: float
    revenue_breakdown: list[DailyDataRevenueBreakdownItemResponse] = Field(default_factory=list)
    covers_summary: DailyDataCoversSummaryResponse = Field(default_factory=DailyDataCoversSummaryResponse)
    register_summary: DailyDataRegisterSummaryResponse = Field(default_factory=DailyDataRegisterSummaryResponse)
    edit_endpoint: str | None = None
    export_endpoint: str | None = None
    export_label: str = "Export"
    created_at: str


class DailyDataSummaryCardResponse(BaseSchema):
    label: str
    value: float
    value_prefix: str | None = None
    value_formatted: str
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
    business_date_formatted: str
    day_label: str
    total_revenue: float
    total_revenue_formatted: str
    total_expenses: float = 0.0
    total_expenses_formatted: str = "$0.00"
    total_covers: int
    avg_revenue_per_cover: float
    avg_revenue_per_cover_formatted: str
    data_sources: list[DailyDataEntrySourceResponse] = Field(default_factory=list)
    actions: DailyDataListItemActionResponse
    created_at: str


class DailyDataAddButtonResponse(BaseSchema):
    label: str = "Add Daily Data"
    endpoint: str
    method: str = "POST"


class DailyDataListResponse(BaseSchema):
    page_title: str = "Daily Data Management"
    subtitle: str = "Track and manage your restaurant performance"
    view_options: list[str] = Field(default_factory=lambda: ["date", "week", "month"])
    active_view: Literal["date", "week", "month"] = "date"
    summary_cards: list[DailyDataSummaryCardResponse]
    add_button: DailyDataAddButtonResponse
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
    page_title: str = "Daily Data Details"
    active_view: Literal["date", "week", "month"] = "date"
    reference_date: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    business_date: str
    business_date_formatted: str
    day_label: str
    summary_cards: list[DailyDataSummaryCardResponse] = Field(default_factory=list)
    total_revenue: float
    total_revenue_formatted: str
    total_expenses: float
    total_expenses_formatted: str
    total_covers: int
    avg_revenue_per_cover: float
    avg_revenue_per_cover_formatted: str
    invoices: list[DailyDataDocumentItemResponse] = Field(default_factory=list)
    invoice_count: int = 0
    data_sources: list[DailyDataEntrySourceResponse] = Field(default_factory=list)


class DailyDataCollectionResponse(BaseSchema):
    page_title: str = "Daily Data Collections"
    active_view: Literal["date", "week", "month"]
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
    stock_quantity_label: str | None = None
    unit_type: str
    supplier_name: str | None = None
    supplier_subtitle: str | None = None
    unit_price: float
    alert_threshold: float
    stock_status: str
    stock_status_label: str | None = None
    purchase_date: str | None = None
    last_purchase_label: str | None = None
    actions: InventoryListItemActionResponse | None = None
    created_at: str
    updated_at: str


class InventoryDetailResponse(InventoryItemResponse):
    page_title: str = "View Inventory Product"
    current_stock_label: str = "Current Stock"
    current_stock_value: float = 0.0
    current_stock_display: str = "0"
    stock_update_endpoint: str | None = None
    stock_update_button_label: str = "Update Stock Level"
    supplier_card: InventorySupplierCardResponse = Field(default_factory=InventorySupplierCardResponse)
    edit_endpoint: str | None = None
    delete_endpoint: str | None = None
    delete_label: str = "Delete"
    history: list[InventoryHistoryItemResponse]


class InventoryListResponse(BaseSchema):
    page_title: str = "Inventory"
    subtitle: str = "Track and manage your restaurant ingredients and stock."
    search_placeholder: str = "Search products"
    add_button_endpoint: str = "/api/v1/restaurant/inventory"
    total_inventory_value: float
    total_inventory_value_formatted: str = "$0.00"
    inventory_growth_percent: float = 0.0
    total: int
    page: int
    page_size: int
    pages: int
    items: list[InventoryItemResponse]


class AnalyticsInsightBannerResponse(BaseSchema):
    label: str = "AI Business Insight"
    title: str
    subtitle: str


class AnalyticsMetricTileResponse(BaseSchema):
    label: str
    value: float | str
    value_formatted: str
    change_percent: float | None = None
    subtitle: str | None = None


class AnalyticsSummaryStatResponse(BaseSchema):
    label: str
    value: float | int
    value_formatted: str


class AnalyticsComparisonRowResponse(BaseSchema):
    label: str
    value: float
    value_formatted: str


class AnalyticsSupplierAlertResponse(BaseSchema):
    title: str
    subtitle: str


class AnalyticsOverviewResponse(BaseSchema):
    page_title: str = "Analytics"
    export_label: str = "Export Data"
    active_filter: str = "Weekly"
    insight_banner: AnalyticsInsightBannerResponse
    estimated_profit: float
    estimated_profit_formatted: str
    peak_hour_label: str
    peak_hour_subtitle: str
    revenue_total: float
    revenue_total_formatted: str
    revenue_change_percent: float
    weekly_revenue: list[ChartPointResponse]
    metric_tiles: list[AnalyticsMetricTileResponse] = Field(default_factory=list)
    summary_stats: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    revenue_comparison: list[AnalyticsComparisonRowResponse] = Field(default_factory=list)
    covers_total: int
    covers_activity: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    avg_revenue_per_cover: float
    avg_revenue_per_cover_formatted: str
    cost_breakdown: list[AnalyticsSummaryStatResponse] = Field(default_factory=list)
    supplier_price_alerts: list[AnalyticsSupplierAlertResponse] = Field(default_factory=list)


class ChatMessageCreateRequest(BaseSchema):
    message: str = Field(min_length=2, max_length=1000)


class ChatMessageResponse(BaseSchema):
    id: str
    role: Literal["user", "assistant"]
    message: str
    created_at: str


class ChatConversationResponse(BaseSchema):
    messages: list[ChatMessageResponse]


class RestaurantProfileResponse(BaseSchema):
    full_name: str
    email: str
    phone: str | None = None
    restaurant_name: str | None = None
    location: str | None = None
    preferred_language: str


class RestaurantProfileUpdateRequest(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    restaurant_name: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)

