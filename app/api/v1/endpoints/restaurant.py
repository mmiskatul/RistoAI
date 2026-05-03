from __future__ import annotations

from datetime import date
import logging
from mimetypes import guess_type
from typing import Awaitable, Callable, TypeVar

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile, status

from app.core.exceptions import AppException, ValidationException
from app.dependencies.auth import get_current_user, get_current_user_allow_inactive
from app.dependencies.services import get_restaurant_operations_service, get_support_service
from app.schemas.restaurant import (
    AnalyticsActivityCostResponse,
    AnalyticsCostBreakdownResponse,
    AnalyticsCoversActivityResponse,
    AnalyticsInsightBannerResponse,
    AnalyticsMetricTilesResponse,
    AnalyticsOverviewResponse,
    AnalyticsRevenueComparisonResponse,
    AnalyticsRevenueTrendResponse,
    AnalyticsSupplierAlertsResponse,
    AnalyticsSummaryStatsResponse,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashDepositUpdateRequest,
    CashManagementSummaryResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
    ChatMessageUpdateRequest,
    DailyDataCollectionResponse,
    DailyDataCreateRequest,
    DailyDataDetailResponse,
    DailyDataListResponse,
    DailyDataResponse,
    DocumentConfirmRequest,
    DocumentConfirmSaveResponse,
    DocumentDetailResponse,
    DocumentExtractionResponse,
    DocumentListResponse,
    DocumentSaveRequest,
    ExpenseCreateRequest,
    ExpenseListResponse,
    ExpenseResponse,
    InsightDetailResponse,
    InsightSummaryResponse,
    InventoryCreateRequest,
    InventoryDetailResponse,
    InventoryItemResponse,
    InventoryListResponse,
    InventoryStockUpdateRequest,
    InventoryUpdateRequest,
    InventoryValueResponse,
    RestaurantHomeResponse,
    RestaurantHomeMetricsResponse,
    RestaurantHomeCashManagementResponse,
    RestaurantHomeRevenueResponse,
    RestaurantHomeInsightResponse,
    RestaurantHomeRecentActivityResponse,
    RestaurantHomeVatBalanceResponse,
    RestaurantNotificationFeedResponse,
    RestaurantNotificationSettingsResponse,
    RestaurantNotificationSettingsUpdateRequest,
    PushDeviceRegistrationRequest,
    PushDeviceUnregisterRequest,
    RestaurantChangePasswordRequest,
    RestaurantProfileResponse,
    RestaurantProfileUpdateRequest,
    RestaurantSettingsSubscriptionResponse,
    VatOverviewResponse,
)
from app.schemas.support import (
    RestaurantHelpCenterResponse,
    SupportTicketActionResponse,
    SupportTicketCreateRequest,
    SupportTicketDetailResponse,
    SupportTicketQuery,
    UserSupportTicketListResponse,
)
from app.schemas.common import MessageResponse
from app.services.restaurant import RestaurantOperationsService
from app.services.support import SupportService

router = APIRouter()
logger = logging.getLogger(__name__)
T = TypeVar('T')


async def _run_endpoint(endpoint_name: str, action: Callable[[], Awaitable[T]]) -> T:
    try:
        return await action()
    except AppException:
        raise
    except OSError as exc:
        logger.exception('Restaurant endpoint failed to read request payload: %s', endpoint_name, exc_info=exc)
        raise ValidationException('Unable to read request payload')
    except Exception as exc:
        logger.exception('Restaurant endpoint failed: %s', endpoint_name, exc_info=exc)
        raise


@router.get('/home', response_model=RestaurantHomeResponse, tags=['Restaurant Home'], summary='Home Overview', description='Restaurant dashboard home data for the mobile app home screen.')
async def get_home(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    include_metrics: bool = Query(default=True),
    include_cash_management: bool = Query(default=True),
    include_revenue: bool = Query(default=True),
    include_featured_insight: bool = Query(default=True),
    include_recent_activity: bool = Query(default=True),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeResponse:
    return await service.get_home(
        current_user,
        period=period,
        from_date=from_date,
        to_date=to_date,
        include_metrics=include_metrics,
        include_cash_management=include_cash_management,
        include_revenue=include_revenue,
        include_featured_insight=include_featured_insight,
        include_recent_activity=include_recent_activity,
    )


@router.get('/home/metrics', response_model=RestaurantHomeMetricsResponse, tags=['Restaurant Home'], summary='Home Metrics Section', description='Restaurant dashboard KPI card section for the mobile home screen.')
async def get_home_metrics(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeMetricsResponse:
    return await service.get_home_metrics(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/home/cash-management', response_model=RestaurantHomeCashManagementResponse, tags=['Restaurant Home'], summary='Home Cash Management Section', description='Restaurant dashboard cash management section for the mobile home screen.')
async def get_home_cash_management(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeCashManagementResponse:
    return await service.get_home_cash_management(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/home/revenue', response_model=RestaurantHomeRevenueResponse, tags=['Restaurant Home'], summary='Home Revenue Section', description='Restaurant dashboard revenue chart section for the mobile home screen.')
async def get_home_revenue(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeRevenueResponse:
    return await service.get_home_revenue(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/home/insight', response_model=RestaurantHomeInsightResponse, tags=['Restaurant Home'], summary='Home Insight Section', description='Restaurant dashboard featured insight section for the mobile home screen.')
async def get_home_insight(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeInsightResponse:
    return await service.get_home_insight(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/home/recent-activity', response_model=RestaurantHomeRecentActivityResponse, tags=['Restaurant Home'], summary='Home Recent Activity Section', description='Restaurant dashboard recent activity section for the mobile home screen.')
async def get_home_recent_activity(
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeRecentActivityResponse:
    return await service.get_home_recent_activity(current_user)


@router.get('/notifications/feed', response_model=RestaurantNotificationFeedResponse, tags=['Restaurant Notifications'], summary='Business Notification Feed', description='Recent business notifications for restaurant cash, expenses, documents, daily data, and inventory changes.')
async def get_notification_feed(
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantNotificationFeedResponse:
    return await _run_endpoint('get_notification_feed', lambda: service.get_notification_feed(current_user))


@router.get('/home/vat-balance', response_model=RestaurantHomeVatBalanceResponse, tags=['Restaurant Home'], summary='Home VAT Balance Section', description='Restaurant dashboard estimated VAT balance card for the mobile home screen.')
async def get_home_vat_balance(
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeVatBalanceResponse:
    return await service.get_home_vat_balance(current_user)


@router.get('/vat/overview', response_model=VatOverviewResponse, tags=['Restaurant VAT'], summary='VAT Overview', description='VAT balance, payable, receivable, and filing summary for the VAT screen.')
async def get_vat_overview(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> VatOverviewResponse:
    return await service.get_vat_overview(current_user)


@router.get('/insights', response_model=InsightDetailResponse, tags=['Restaurant Insights'], summary='Latest Insight', description='Primary restaurant insight detail for the insights screen.')
async def list_insights(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InsightDetailResponse:
    return await service.list_insights(current_user)


@router.get('/insights/{insight_id}', response_model=InsightDetailResponse, tags=['Restaurant Insights'], summary='Insight Detail', description='Detailed insight record with causes and recommended actions.')
async def get_insight_detail(insight_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InsightDetailResponse:
    return await service.get_insight_detail(current_user, insight_id)


ALLOWED_DOCUMENT_CONTENT_TYPES = {
    'application/pdf',
    'text/csv',
    'application/csv',
}


ALLOWED_CHAT_ATTACHMENT_CONTENT_TYPES = ALLOWED_DOCUMENT_CONTENT_TYPES | {'text/plain'}


UPLOAD_CONTENT_TYPE_ALIASES = {
    'application/x-pdf': 'application/pdf',
    'image/jpg': 'image/jpeg',
    'image/pjpeg': 'image/jpeg',
    'text/comma-separated-values': 'text/csv',
    'text/x-csv': 'text/csv',
}


def _resolve_supported_upload_content_type(file: UploadFile, *, allow_text: bool = False) -> str:
    content_type = UPLOAD_CONTENT_TYPE_ALIASES.get((file.content_type or '').lower(), (file.content_type or '').lower())
    if not content_type or content_type == 'application/octet-stream':
        guessed_content_type = guess_type(file.filename or '')[0] or ''
        content_type = UPLOAD_CONTENT_TYPE_ALIASES.get(guessed_content_type.lower(), guessed_content_type.lower())

    allowed_content_types = ALLOWED_CHAT_ATTACHMENT_CONTENT_TYPES if allow_text else ALLOWED_DOCUMENT_CONTENT_TYPES
    if content_type in allowed_content_types or content_type.startswith('image/'):
        return content_type

    supported_label = 'PDF, CSV, TXT, and image files' if allow_text else 'PDF, CSV, and image files'
    raise ValidationException(f'Only {supported_label} are supported')


@router.post('/documents/upload-extract', response_model=DocumentExtractionResponse, status_code=status.HTTP_200_OK, tags=['Restaurant Invoice AI'], summary='Upload And Extract Invoice', description='Uploads an invoice file and returns extracted preview JSON without saving to the database.')
async def upload_and_extract_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DocumentExtractionResponse:
    content_type = _resolve_supported_upload_content_type(file)
    file_bytes = await file.read()
    return await service.upload_and_extract_document(
        current_user,
        file_name=file.filename or 'upload-file',
        content_type=content_type,
        file_bytes=file_bytes,
        raw_file=file,
    )


@router.post('/documents/confirm-save', response_model=DocumentConfirmSaveResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Invoice AI'], summary='Confirm And Save Invoice', description='Stores the edited invoice preview as a restaurant invoice record.')
async def confirm_and_save_document(payload: DocumentSaveRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentConfirmSaveResponse:
    return await service.create_document_from_confirmation(current_user, payload)


@router.get('/documents', response_model=DocumentListResponse, tags=['Restaurant Invoice AI'], summary='List Invoices', description='Lists saved restaurant invoices for the documents screen.')
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias='status'),
    search: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DocumentListResponse:
    return await _run_endpoint(
        'list_documents',
        lambda: service.list_documents(current_user, page=page, page_size=page_size, status=status_filter, search=search),
    )


@router.get('/documents/{document_id}', response_model=DocumentDetailResponse, tags=['Restaurant Invoice AI'], summary='Invoice Detail', description='Returns one saved invoice record.')
async def get_document_detail(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await _run_endpoint('get_document_detail', lambda: service.get_document_detail(current_user, document_id))


@router.get('/documents/{document_id}/download', tags=['Restaurant Invoice AI'], summary='Download Invoice PDF', description='Generates a downloadable A4 invoice PDF from the saved document data.')
async def download_document(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    filename, content = await _run_endpoint(
        'download_document',
        lambda: service.download_document_file(current_user, document_id),
    )
    return Response(content=content, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.get('/documents/{document_id}/download-image', tags=['Restaurant Invoice AI'], summary='Download Invoice Image', description='Generates a downloadable invoice image in SVG or PNG format.')
async def download_document_image(
    document_id: str,
    format: str = Query(default='svg', pattern='^(svg|png)$'),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> Response:
    filename, media_type, content = await _run_endpoint(
        'download_document_image',
        lambda: service.download_document_image(current_user, document_id, image_format=format),
    )
    return Response(content=content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.patch('/documents/{document_id}', response_model=DocumentDetailResponse, tags=['Restaurant Invoice AI'], summary='Update Invoice', description='Updates an existing saved invoice record.')
async def update_document(document_id: str, payload: DocumentConfirmRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await _run_endpoint('update_document', lambda: service.update_document(current_user, document_id, payload))


@router.delete('/documents/{document_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Invoice AI'], summary='Delete Invoice', description='Deletes a saved invoice record.')
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await _run_endpoint('delete_document', lambda: service.delete_document(current_user, document_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/expenses', response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Expenses'], summary='Create Expense', description='Creates a manual expense record.')
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseResponse:
    return await service.create_expense(current_user, payload)


@router.get('/expenses', response_model=ExpenseListResponse, tags=['Restaurant Expenses'], summary='List Expenses', description='Lists expenses and expense summary cards for the expenses screen.')
async def list_expenses(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseListResponse:
    return await service.list_expenses(current_user, page=page, page_size=page_size)


@router.get('/expenses/{expense_id}', response_model=ExpenseResponse, tags=['Restaurant Expenses'], summary='Expense Detail', description='Returns one saved manual expense record.')
async def get_expense_detail(expense_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseResponse:
    return await service.get_expense_detail(current_user, expense_id)


@router.delete('/expenses/{expense_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Expenses'], summary='Delete Expense', description='Deletes a direct manual expense. Source-generated expenses must be deleted from their source record.')
async def delete_expense(expense_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_expense(current_user, expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/cash/deposits', response_model=CashDepositResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Cash Management'], summary='Create Bank Deposit', description='Creates a cash deposit or bank drop record.')
async def create_cash_deposit(payload: CashDepositCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.create_cash_deposit(current_user, payload)


@router.get('/cash/deposits/{deposit_id}', response_model=CashDepositResponse, tags=['Restaurant Cash Management'], summary='Bank Deposit Detail', description='Returns one saved cash deposit or bank drop record.')
async def get_cash_deposit(deposit_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.get_cash_deposit(current_user, deposit_id)


@router.patch('/cash/deposits/{deposit_id}', response_model=CashDepositResponse, tags=['Restaurant Cash Management'], summary='Update Bank Deposit', description='Updates a saved cash deposit or bank drop record.')
async def update_cash_deposit(deposit_id: str, payload: CashDepositUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.update_cash_deposit(current_user, deposit_id, payload)


@router.delete('/cash/deposits/{deposit_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Cash Management'], summary='Delete Bank Deposit', description='Deletes a saved cash deposit or bank drop record.')
async def delete_cash_deposit(deposit_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> None:
    await service.delete_cash_deposit(current_user, deposit_id)


@router.get('/cash/overview', response_model=CashManagementSummaryResponse, tags=['Restaurant Cash Management'], summary='Cash Overview', description='Returns cash management summary cards and recent deposits.')
async def get_cash_management(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashManagementSummaryResponse:
    return await service.get_cash_management(current_user)


@router.post('/manual-entry', response_model=DailyDataResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Invoice Manual Entry'], summary='Create Manual Entry', description='Creates a manual invoice-style business entry using method 1 or method 2 input flow.')
async def create_daily_data(payload: DailyDataCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.create_daily_data(current_user, payload)


@router.patch('/manual-entry/{record_id}', response_model=DailyDataResponse, tags=['Restaurant Invoice Manual Entry'], summary='Update Manual Entry', description='Updates an existing manual invoice-style business entry.')
async def update_daily_data(record_id: str, payload: DailyDataCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.update_daily_data(current_user, record_id, payload)


@router.get('/daily-data', response_model=DailyDataListResponse, tags=['Restaurant Data Management'], summary='Data Management List', description='Lists date, week, or month grouped daily business records for the data management screen.')
async def list_daily_data(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view: str = Query(default='date', pattern='^(date|week|month)$'),
    reference_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataListResponse:
    return await service.list_daily_data(current_user, page=page, page_size=page_size, view=view, reference_date=reference_date)


@router.get('/daily-data/by-date', response_model=DailyDataDetailResponse | DailyDataCollectionResponse, tags=['Restaurant Data Management'], summary='Date Drilldown', description='Returns all date groups or a single date drilldown with invoices and summary cards.')
async def get_daily_data_by_date_detail(
    business_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse | DailyDataCollectionResponse:
    return await service.get_daily_data_by_date_detail(current_user, business_date=business_date)


@router.get('/daily-data/by-date-reference', response_model=DailyDataDetailResponse, tags=['Restaurant Data Management'], include_in_schema=False)
async def get_daily_data_by_date_reference_detail(
    reference_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse:
    return await service.get_daily_data_by_date_detail(current_user, business_date=reference_date)


@router.get('/daily-data/by-week', response_model=DailyDataDetailResponse | DailyDataCollectionResponse, tags=['Restaurant Data Management'], summary='Week Drilldown', description='Returns all week groups or a single week drilldown with invoices and summary cards.')
async def get_daily_data_by_week_detail(
    reference_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse | DailyDataCollectionResponse:
    return await service.get_daily_data_by_week_detail(current_user, reference_date=reference_date)


@router.get('/daily-data/by-week-business-date', response_model=DailyDataDetailResponse, tags=['Restaurant Data Management'], include_in_schema=False)
async def get_daily_data_by_week_business_date_detail(
    business_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse:
    return await service.get_daily_data_by_week_detail(current_user, reference_date=business_date)


@router.get('/daily-data/by-month', response_model=DailyDataDetailResponse | DailyDataCollectionResponse, tags=['Restaurant Data Management'], summary='Month Drilldown', description='Returns all month groups or a single month drilldown with invoices and summary cards.')
async def get_daily_data_by_month_detail(
    reference_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse | DailyDataCollectionResponse:
    return await service.get_daily_data_by_month_detail(current_user, reference_date=reference_date)


@router.get('/daily-data/by-month-business-date', response_model=DailyDataDetailResponse, tags=['Restaurant Data Management'], include_in_schema=False)
async def get_daily_data_by_month_business_date_detail(
    business_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse:
    return await service.get_daily_data_by_month_detail(current_user, reference_date=business_date)


@router.delete('/daily-data/by-date', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Data Management'], summary='Delete Date Collection', description='Deletes all deletable source records collected under one business date.')
async def delete_daily_data_by_date(
    business_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> Response:
    await service.delete_daily_data_collection_by_date(current_user, business_date)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/daily-data/{record_id}', response_model=DailyDataResponse, tags=['Restaurant Data Management'], summary='Daily Record Detail', description='Returns one saved manual daily record in detail-screen shape.')
async def get_daily_data_detail(record_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.get_daily_data_detail(current_user, record_id)


@router.delete('/daily-data/{record_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Data Management'], summary='Delete Daily Record', description='Deletes one manual daily record.')
async def delete_daily_data(record_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_daily_data(current_user, record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/inventory', response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Inventory'], summary='Create Inventory Item', description='Creates a new inventory item for the add inventory screen.', include_in_schema=False)
async def create_inventory_item(payload: InventoryCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryItemResponse:
    return await service.create_inventory_item(current_user, payload)


@router.post('/inventory/add-item', response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Inventory'], summary='Add Inventory Item', description='Dedicated endpoint for the mobile add-item inventory screen.')
async def add_inventory_item(payload: InventoryCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryItemResponse:
    return await service.create_inventory_item(current_user, payload)


@router.get('/inventory', response_model=InventoryListResponse, tags=['Restaurant Inventory'], summary='Inventory List', description='Lists inventory items and summary card data for the inventory screen.', include_in_schema=False)
async def list_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias='status'),
    category: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> InventoryListResponse:
    return await _run_endpoint(
        'list_inventory',
        lambda: service.list_inventory(current_user, page=page, page_size=page_size, search=search, status=status_filter, category=category),
    )


@router.get('/inventory/value', response_model=InventoryValueResponse, tags=['Restaurant Inventory'], summary='Inventory Value', description='Returns only the total inventory value for the inventory summary card.')
async def get_inventory_value(
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> InventoryValueResponse:
    return await service.get_inventory_value(current_user)


@router.get('/inventory/{item_id}', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'], summary='Inventory Detail', description='Returns the inventory detail screen payload for one product.', include_in_schema=False)
async def get_inventory_item(item_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await _run_endpoint('get_inventory_item', lambda: service.get_inventory_item(current_user, item_id))


@router.patch('/inventory/{item_id}', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'], summary='Update Inventory Item', description='Updates inventory item fields such as supplier, threshold, or stock metadata.', include_in_schema=False)
async def update_inventory_item(item_id: str, payload: InventoryUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await _run_endpoint('update_inventory_item', lambda: service.update_inventory_item(current_user, item_id, payload))


@router.delete('/inventory/{item_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Inventory'], summary='Delete Inventory Item', description='Deletes one inventory item.', include_in_schema=False)
async def delete_inventory_item(item_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await _run_endpoint('delete_inventory_item', lambda: service.delete_inventory_item(current_user, item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/inventory/{item_id}/stock-update', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'], summary='Update Inventory Stock', description='Adds or removes stock and appends inventory history entries.', include_in_schema=False)
async def update_inventory_stock(item_id: str, payload: InventoryStockUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.update_inventory_stock(current_user, item_id, payload)


@router.get('/analytics/overview', response_model=AnalyticsOverviewResponse, response_model_exclude_none=True, tags=['Restaurant Analytics'], summary='Analytics Overview', description='Returns the analytics screen payload including cards, trend, comparisons, and alerts.')
async def get_analytics(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsOverviewResponse:
    return await _run_endpoint(
        'get_analytics',
        lambda: service.get_analytics(current_user, period=period, from_date=from_date, to_date=to_date),
    )


@router.get('/analytics/business-insight', response_model=AnalyticsInsightBannerResponse, tags=['Restaurant Analytics'], summary='Analytics Business Insight', description='Returns the top analytics insight banner generated from restaurant data.')
async def get_analytics_business_insight(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> AnalyticsInsightBannerResponse:
    return await service.get_analytics_business_insight(current_user)


@router.get('/analytics/metric-tiles', response_model=AnalyticsMetricTilesResponse, tags=['Restaurant Analytics'], summary='Analytics Metric Tiles', description='Returns the top analytics metric cards section.')
async def get_analytics_metric_tiles(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsMetricTilesResponse:
    return await service.get_analytics_metric_tiles(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/revenue-trend', response_model=AnalyticsRevenueTrendResponse, tags=['Restaurant Analytics'], summary='Analytics Revenue Trend', description='Returns the analytics revenue trend section.')
async def get_analytics_revenue_trend(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsRevenueTrendResponse:
    return await service.get_analytics_revenue_trend(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/summary-stats', response_model=AnalyticsSummaryStatsResponse, tags=['Restaurant Analytics'], summary='Analytics Summary Stats', description='Returns the analytics revenue, covers, and average revenue section.')
async def get_analytics_summary_stats(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsSummaryStatsResponse:
    return await service.get_analytics_summary_stats(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/revenue-comparison', response_model=AnalyticsRevenueComparisonResponse, tags=['Restaurant Analytics'], summary='Analytics Revenue Comparison', description='Returns the analytics revenue comparison section.')
async def get_analytics_revenue_comparison(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsRevenueComparisonResponse:
    return await service.get_analytics_revenue_comparison(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/activity-cost', response_model=AnalyticsActivityCostResponse, tags=['Restaurant Analytics'], summary='Analytics Activity And Cost', description='Returns the analytics covers activity and cost breakdown section.')
async def get_analytics_activity_cost(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsActivityCostResponse:
    return await service.get_analytics_activity_cost(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/covers-activity', response_model=AnalyticsCoversActivityResponse, tags=['Restaurant Analytics'], summary='Analytics Covers Activity', description='Returns the analytics covers activity section.')
async def get_analytics_covers_activity(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsCoversActivityResponse:
    return await service.get_analytics_covers_activity(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/cost-breakdown', response_model=AnalyticsCostBreakdownResponse, tags=['Restaurant Analytics'], summary='Analytics Cost Breakdown', description='Returns the analytics cost breakdown section.')
async def get_analytics_cost_breakdown(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsCostBreakdownResponse:
    return await service.get_analytics_cost_breakdown(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/supplier-alerts', response_model=AnalyticsSupplierAlertsResponse, tags=['Restaurant Analytics'], summary='Analytics Supplier Alerts', description='Returns the analytics supplier alert section.')
async def get_analytics_supplier_alerts(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> AnalyticsSupplierAlertsResponse:
    return await service.get_analytics_supplier_alerts(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/chat/messages', response_model=ChatConversationResponse, tags=['Restaurant Chat'], summary='List Chat Messages', description='Returns the current restaurant AI chat conversation.')
async def list_chat_messages(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await _run_endpoint('list_chat_messages', lambda: service.list_chat_messages(current_user))


@router.post('/chat/messages', response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Chat'], summary='Create Chat Message', description='Sends a user message and returns the updated AI chat conversation.')
async def create_chat_message(payload: ChatMessageCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await _run_endpoint('create_chat_message', lambda: service.create_chat_message(current_user, payload))


@router.patch('/chat/messages/{message_id}', response_model=ChatConversationResponse, tags=['Restaurant Chat'], summary='Edit Chat Message', description='Updates a user message and stores a regenerated AI response linked to the edited message.')
async def update_chat_message(message_id: str, payload: ChatMessageUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await _run_endpoint('update_chat_message', lambda: service.update_chat_message(current_user, message_id, payload))


@router.post('/chat/messages/attachments', response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Chat'], summary='Create Chat Message With Attachment', description='Sends a user message with a shared document and returns the updated personalized AI chat conversation.')
async def create_chat_message_with_attachment(
    message: str = Form(...),
    attachment_source: str | None = Form(default=None),
    language: str | None = Form(default=None),
    accept_language: str | None = Header(default=None, alias='Accept-Language'),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> ChatConversationResponse:
    async def _execute() -> ChatConversationResponse:
        content_type = _resolve_supported_upload_content_type(file, allow_text=True)
        file_bytes = await file.read()
        return await service.create_chat_message_with_attachment(
            current_user,
            payload=ChatMessageCreateRequest(
                message=message,
                attachment_source=attachment_source,
                language=language or accept_language,
            ),
            file_name=file.filename or 'chat-attachment',
            content_type=content_type,
            file_bytes=file_bytes,
            raw_file=file,
        )

    return await _run_endpoint('create_chat_message_with_attachment', _execute)


@router.get('/settings/profile', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'], summary='Profile Detail', description='Returns the restaurant profile and settings data.')
async def get_profile(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantProfileResponse:
    return await _run_endpoint('get_profile', lambda: service.get_profile(current_user))


@router.put('/settings/profile', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'], summary='Update Profile', description='Updates restaurant profile and settings fields.')
async def update_profile(
    full_name: str | None = Form(default=None, min_length=2, max_length=120),
    phone: str | None = Form(default=None, max_length=30),
    restaurant_name: str | None = Form(default=None, max_length=120),
    restaurant_type: str | None = Form(default=None, max_length=80),
    location: str | None = Form(default=None, max_length=120),
    city_location: str | None = Form(default=None, max_length=120),
    number_of_seats: int | None = Form(default=None, ge=0),
    average_spend_per_customer: float | None = Form(default=None, ge=0),
    main_business_goal: str | None = Form(default=None, max_length=120),
    biggest_problem: str | None = Form(default=None, max_length=1000),
    improvement_focus: str | None = Form(default=None, max_length=1000),
    profile_image: UploadFile | None = File(default=None),
    profile_image_url: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantProfileResponse:
    payload = RestaurantProfileUpdateRequest(
        full_name=full_name,
        phone=phone,
        restaurant_name=restaurant_name,
        restaurant_type=restaurant_type,
        location=location,
        city_location=city_location,
        number_of_seats=number_of_seats,
        average_spend_per_customer=average_spend_per_customer,
        main_business_goal=main_business_goal,
        biggest_problem=biggest_problem,
        improvement_focus=improvement_focus,
        profile_image_url=profile_image_url,
    )
    return await _run_endpoint(
        'update_profile',
        lambda: service.update_profile_with_image(current_user, payload, profile_image=profile_image),
    )


@router.delete('/settings/profile/image', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'], summary='Remove Profile Image', description='Removes the saved restaurant profile image.')
async def remove_profile_image(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantProfileResponse:
    return await _run_endpoint('remove_profile_image', lambda: service.remove_profile_image(current_user))


@router.get('/settings/subscription', response_model=RestaurantSettingsSubscriptionResponse, tags=['Restaurant Settings'], summary='Subscription Settings', description='Returns the current restaurant subscription state and management endpoints.')
async def get_settings_subscription(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantSettingsSubscriptionResponse:
    return await service.get_settings_subscription(current_user)


@router.get('/settings/notifications', response_model=RestaurantNotificationSettingsResponse, tags=['Restaurant Settings'], summary='Notification Settings', description='Returns restaurant notification preferences.')
async def get_notification_settings(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantNotificationSettingsResponse:
    return await service.get_notification_settings(current_user)


@router.put('/settings/notifications', response_model=RestaurantNotificationSettingsResponse, tags=['Restaurant Settings'], summary='Update Notification Settings', description='Updates restaurant notification preferences.')
async def update_notification_settings(
    payload: RestaurantNotificationSettingsUpdateRequest,
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantNotificationSettingsResponse:
    return await service.update_notification_settings(current_user, payload)


@router.post('/settings/push-devices/register', response_model=MessageResponse, tags=['Restaurant Settings'], summary='Register Push Device', description='Registers the current mobile device Expo push token for restaurant push notifications.')
async def register_push_device(
    payload: PushDeviceRegistrationRequest,
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> MessageResponse:
    return await service.register_push_device(current_user, payload)


@router.post('/settings/push-devices/unregister', response_model=MessageResponse, tags=['Restaurant Settings'], summary='Unregister Push Device', description='Removes the current mobile device from restaurant push notifications.')
async def unregister_push_device(
    payload: PushDeviceUnregisterRequest,
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> MessageResponse:
    return await service.unregister_push_device(current_user, payload)


@router.post('/settings/change-password', response_model=MessageResponse, tags=['Restaurant Settings'], summary='Change Password', description='Changes the current authenticated restaurant user password.')
async def change_password(
    payload: RestaurantChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> MessageResponse:
    return await service.change_password(current_user, payload)


@router.get('/help-center', response_model=RestaurantHelpCenterResponse, tags=['Restaurant Help Center'], summary='Help Center Overview', description='Returns the restaurant help center overview and ticket action endpoints.')
async def get_help_center(
    _: dict = Depends(get_current_user_allow_inactive),
    service: SupportService = Depends(get_support_service),
) -> RestaurantHelpCenterResponse:
    return await service.get_help_center()


@router.post('/help-center/tickets', response_model=SupportTicketActionResponse, tags=['Restaurant Help Center'], summary='Create Help Center Ticket', description='Creates a support ticket from the restaurant help center and stores it in the admin support section.')
async def create_help_center_ticket(
    payload: SupportTicketCreateRequest,
    current_user: dict = Depends(get_current_user_allow_inactive),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketActionResponse:
    return await service.create_ticket(current_user, payload)


@router.get('/help-center/tickets', response_model=UserSupportTicketListResponse, tags=['Restaurant Help Center'], summary='List Help Center Tickets', description='Lists help center tickets created by the current restaurant user.')
async def list_help_center_tickets(
    query: SupportTicketQuery = Depends(),
    current_user: dict = Depends(get_current_user_allow_inactive),
    service: SupportService = Depends(get_support_service),
) -> UserSupportTicketListResponse:
    return await service.get_user_tickets(current_user, query)


@router.get('/help-center/tickets/{ticket_id}', response_model=SupportTicketDetailResponse, tags=['Restaurant Help Center'], summary='Help Center Ticket Detail', description='Returns the detail for one help center ticket owned by the current restaurant user.')
async def get_help_center_ticket_detail(
    ticket_id: str,
    current_user: dict = Depends(get_current_user_allow_inactive),
    service: SupportService = Depends(get_support_service),
) -> SupportTicketDetailResponse:
    return await service.get_user_ticket_detail(current_user, ticket_id)

