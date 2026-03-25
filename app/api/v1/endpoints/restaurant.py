from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_restaurant_operations_service
from app.schemas.restaurant import (
    AnalyticsOverviewResponse,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashManagementSummaryResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
    DailyDataCollectionResponse,
    DailyDataCreateRequest,
    DailyDataDetailResponse,
    DailyDataListResponse,
    DailyDataResponse,
    DocumentConfirmRequest,
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
    RestaurantHomeResponse,
    RestaurantProfileResponse,
    RestaurantProfileUpdateRequest,
    VatOverviewResponse,
)
from app.services.restaurant import RestaurantOperationsService

router = APIRouter()


@router.get('/home', response_model=RestaurantHomeResponse, tags=['Restaurant Home'])
async def get_home(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantHomeResponse:
    return await service.get_home(current_user)


@router.get('/vat/overview', response_model=VatOverviewResponse, tags=['Restaurant VAT'])
async def get_vat_overview(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> VatOverviewResponse:
    return await service.get_vat_overview(current_user)


@router.get('/insights', response_model=InsightDetailResponse, tags=['Restaurant Insights'])
async def list_insights(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InsightDetailResponse:
    return await service.list_insights(current_user)


@router.get('/insights/{insight_id}', response_model=InsightDetailResponse, tags=['Restaurant Insights'])
async def get_insight_detail(insight_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InsightDetailResponse:
    return await service.get_insight_detail(current_user, insight_id)


ALLOWED_DOCUMENT_CONTENT_TYPES = {
    'application/pdf',
    'text/csv',
    'application/csv',
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
}


@router.post('/documents/upload-extract', response_model=DocumentExtractionResponse, status_code=status.HTTP_200_OK, tags=['Restaurant Documents'])
async def upload_and_extract_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DocumentExtractionResponse:
    content_type = (file.content_type or '').lower()
    if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
        raise ValidationException('Only PDF, CSV, PNG, JPG, JPEG, and WEBP files are supported')
    file_bytes = await file.read()
    return await service.upload_and_extract_document(
        current_user,
        file_name=file.filename or 'upload-file',
        content_type=content_type,
        file_bytes=file_bytes,
    )


@router.post('/documents/confirm-save', response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Documents'])
async def confirm_and_save_document(payload: DocumentSaveRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.create_document_from_confirmation(current_user, payload)


@router.get('/documents', response_model=DocumentListResponse, tags=['Restaurant Documents'])
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias='status'),
    search: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DocumentListResponse:
    return await service.list_documents(current_user, page=page, page_size=page_size, status=status_filter, search=search)


@router.get('/documents/{document_id}', response_model=DocumentDetailResponse, tags=['Restaurant Documents'])
async def get_document_detail(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.get_document_detail(current_user, document_id)


@router.patch('/documents/{document_id}', response_model=DocumentDetailResponse, tags=['Restaurant Documents'])
async def update_document(document_id: str, payload: DocumentConfirmRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.update_document(current_user, document_id, payload)


@router.delete('/documents/{document_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Documents'])
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_document(current_user, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/expenses', response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Expenses'])
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseResponse:
    return await service.create_expense(current_user, payload)


@router.get('/expenses', response_model=ExpenseListResponse, tags=['Restaurant Expenses'])
async def list_expenses(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseListResponse:
    return await service.list_expenses(current_user, page=page, page_size=page_size)


@router.post('/cash/deposits', response_model=CashDepositResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Cash Management'])
async def create_cash_deposit(payload: CashDepositCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.create_cash_deposit(current_user, payload)


@router.get('/cash/overview', response_model=CashManagementSummaryResponse, tags=['Restaurant Cash Management'])
async def get_cash_management(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashManagementSummaryResponse:
    return await service.get_cash_management(current_user)


@router.post('/daily-data', response_model=DailyDataResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Data Management'])
async def create_daily_data(payload: DailyDataCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.create_daily_data(current_user, payload)


@router.get('/daily-data', response_model=DailyDataListResponse, tags=['Restaurant Data Management'])
async def list_daily_data(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    view: str = Query(default='date', pattern='^(date|week|month)$'),
    reference_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataListResponse:
    return await service.list_daily_data(current_user, page=page, page_size=page_size, view=view, reference_date=reference_date)


@router.get('/daily-data/by-date', response_model=DailyDataDetailResponse | DailyDataCollectionResponse, tags=['Restaurant Data Management'])
async def get_daily_data_by_date_detail(
    business_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse | DailyDataCollectionResponse:
    return await service.get_daily_data_by_date_detail(current_user, business_date=business_date)


@router.get('/daily-data/by-date-reference', response_model=DailyDataDetailResponse, tags=['Restaurant Data Management'])
async def get_daily_data_by_date_reference_detail(
    reference_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse:
    return await service.get_daily_data_by_date_detail(current_user, business_date=reference_date)


@router.get('/daily-data/by-week', response_model=DailyDataDetailResponse | DailyDataCollectionResponse, tags=['Restaurant Data Management'])
async def get_daily_data_by_week_detail(
    reference_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse | DailyDataCollectionResponse:
    return await service.get_daily_data_by_week_detail(current_user, reference_date=reference_date)


@router.get('/daily-data/by-week-business-date', response_model=DailyDataDetailResponse, tags=['Restaurant Data Management'])
async def get_daily_data_by_week_business_date_detail(
    business_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse:
    return await service.get_daily_data_by_week_detail(current_user, reference_date=business_date)


@router.get('/daily-data/by-month', response_model=DailyDataDetailResponse | DailyDataCollectionResponse, tags=['Restaurant Data Management'])
async def get_daily_data_by_month_detail(
    reference_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse | DailyDataCollectionResponse:
    return await service.get_daily_data_by_month_detail(current_user, reference_date=reference_date)


@router.get('/daily-data/by-month-business-date', response_model=DailyDataDetailResponse, tags=['Restaurant Data Management'])
async def get_daily_data_by_month_business_date_detail(
    business_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DailyDataDetailResponse:
    return await service.get_daily_data_by_month_detail(current_user, reference_date=business_date)


@router.get('/daily-data/{record_id}', response_model=DailyDataResponse, tags=['Restaurant Data Management'])
async def get_daily_data_detail(record_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.get_daily_data_detail(current_user, record_id)


@router.delete('/daily-data/{record_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Data Management'])
async def delete_daily_data(record_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_daily_data(current_user, record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/inventory', response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Inventory'])
async def create_inventory_item(payload: InventoryCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryItemResponse:
    return await service.create_inventory_item(current_user, payload)


@router.get('/inventory', response_model=InventoryListResponse, tags=['Restaurant Inventory'])
async def list_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias='status'),
    category: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> InventoryListResponse:
    return await service.list_inventory(current_user, page=page, page_size=page_size, search=search, status=status_filter, category=category)


@router.get('/inventory/{item_id}', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'])
async def get_inventory_item(item_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.get_inventory_item(current_user, item_id)


@router.post('/inventory/{item_id}/stock-update', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'])
async def update_inventory_stock(item_id: str, payload: InventoryStockUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.update_inventory_stock(current_user, item_id, payload)


@router.get('/analytics/overview', response_model=AnalyticsOverviewResponse, tags=['Restaurant Analytics'])
async def get_analytics(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> AnalyticsOverviewResponse:
    return await service.get_analytics(current_user)


@router.get('/chat/messages', response_model=ChatConversationResponse, tags=['Restaurant Chat'])
async def list_chat_messages(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await service.list_chat_messages(current_user)


@router.post('/chat/messages', response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Chat'])
async def create_chat_message(payload: ChatMessageCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await service.create_chat_message(current_user, payload)


@router.get('/settings/profile', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'])
async def get_profile(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantProfileResponse:
    return await service.get_profile(current_user)


@router.put('/settings/profile', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'])
async def update_profile(payload: RestaurantProfileUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantProfileResponse:
    return await service.update_profile(current_user, payload)

