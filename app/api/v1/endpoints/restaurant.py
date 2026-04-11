from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.exceptions import ValidationException
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_restaurant_operations_service
from app.schemas.restaurant import (
    AnalyticsInsightBannerResponse,
    AnalyticsOverviewResponse,
    BankAccountCreateRequest,
    BankAccountListResponse,
    BankAccountResponse,
    BankAccountUpdateRequest,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashDepositUpdateRequest,
    CashManagementSummaryResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
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
    RestaurantHomeResponse,
    RestaurantProfileResponse,
    RestaurantProfileUpdateRequest,
    VatOverviewResponse,
)
from app.services.restaurant import RestaurantOperationsService

router = APIRouter()


@router.get('/home', response_model=RestaurantHomeResponse, tags=['Restaurant Home'], summary='Home Overview', description='Restaurant dashboard home data for the mobile app home screen.')
async def get_home(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> RestaurantHomeResponse:
    return await service.get_home(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/home/export', tags=['Restaurant Home'], summary='Export Home Report', description='Exports home dashboard data in PDF or Excel format for weekly or monthly period.')
async def export_home_report(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    format: str = Query(default='pdf', pattern='^(pdf|excel)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> Response:
    file_name, media_type, content = await service.export_home_report(
        current_user,
        period=period,
        export_format=format,
        from_date=from_date,
        to_date=to_date,
    )
    return Response(content=content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{file_name}"'})


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
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/webp',
}


ALLOWED_CHAT_ATTACHMENT_CONTENT_TYPES = ALLOWED_DOCUMENT_CONTENT_TYPES | {'text/plain'}


@router.post('/documents/upload-extract', response_model=DocumentExtractionResponse, status_code=status.HTTP_200_OK, tags=['Restaurant Invoice AI'], summary='Upload And Extract Invoice', description='Uploads an invoice file and returns extracted preview JSON without saving to the database.')
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
    return await service.list_documents(current_user, page=page, page_size=page_size, status=status_filter, search=search)


@router.get('/documents/{document_id}', response_model=DocumentDetailResponse, tags=['Restaurant Invoice AI'], summary='Invoice Detail', description='Returns one saved invoice record.')
async def get_document_detail(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.get_document_detail(current_user, document_id)


@router.get('/documents/{document_id}/download', tags=['Restaurant Invoice AI'], summary='Download Invoice PDF', description='Generates a downloadable A4 invoice PDF from the saved document data.')
async def download_document(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    filename, content = await service.download_document_file(current_user, document_id)
    return Response(content=content, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.get('/documents/{document_id}/download-image', tags=['Restaurant Invoice AI'], summary='Download Invoice Image', description='Generates a downloadable invoice image in SVG or PNG format.')
async def download_document_image(
    document_id: str,
    format: str = Query(default='svg', pattern='^(svg|png)$'),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> Response:
    filename, media_type, content = await service.download_document_image(current_user, document_id, image_format=format)
    return Response(content=content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.patch('/documents/{document_id}', response_model=DocumentDetailResponse, tags=['Restaurant Invoice AI'], summary='Update Invoice', description='Updates an existing saved invoice record.')
async def update_document(document_id: str, payload: DocumentConfirmRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.update_document(current_user, document_id, payload)


@router.delete('/documents/{document_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Invoice AI'], summary='Delete Invoice', description='Deletes a saved invoice record.')
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_document(current_user, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/expenses', response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Expenses'], summary='Create Expense', description='Creates a manual expense record.')
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseResponse:
    return await service.create_expense(current_user, payload)


@router.get('/expenses', response_model=ExpenseListResponse, tags=['Restaurant Expenses'], summary='List Expenses', description='Lists expenses and expense summary cards for the expenses screen.')
async def list_expenses(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseListResponse:
    return await service.list_expenses(current_user, page=page, page_size=page_size)


@router.post('/cash/deposits', response_model=CashDepositResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Cash Management'], summary='Create Bank Deposit', description='Creates a cash deposit or bank drop record.')
async def create_cash_deposit(payload: CashDepositCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.create_cash_deposit(current_user, payload)


@router.patch('/cash/deposits/{deposit_id}', response_model=CashDepositResponse, tags=['Restaurant Cash Management'], summary='Update Bank Deposit', description='Updates a saved cash deposit or bank drop record.')
async def update_cash_deposit(deposit_id: str, payload: CashDepositUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.update_cash_deposit(current_user, deposit_id, payload)


@router.delete('/cash/deposits/{deposit_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Cash Management'], summary='Delete Bank Deposit', description='Deletes a saved cash deposit or bank drop record.')
async def delete_cash_deposit(deposit_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> None:
    await service.delete_cash_deposit(current_user, deposit_id)


@router.post('/cash/bank-accounts', response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Cash Management'], summary='Create Bank Account', description='Creates a bank account option for the cash deposit dropdown.')
async def create_bank_account(payload: BankAccountCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> BankAccountResponse:
    return await service.create_bank_account(current_user, payload)


@router.get('/cash/bank-accounts', response_model=BankAccountListResponse, tags=['Restaurant Cash Management'], summary='List Bank Accounts', description='Returns saved bank accounts and the total account count for dropdowns.')
async def list_bank_accounts(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> BankAccountListResponse:
    return await service.list_bank_accounts(current_user)


@router.patch('/cash/bank-accounts/{account_id}', response_model=BankAccountResponse, tags=['Restaurant Cash Management'], summary='Update Bank Account', description='Updates a saved bank account option for the cash deposit dropdown.')
async def update_bank_account(account_id: str, payload: BankAccountUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> BankAccountResponse:
    return await service.update_bank_account(current_user, account_id, payload)


@router.delete('/cash/bank-accounts/{account_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Cash Management'], summary='Delete Bank Account', description='Deletes a saved bank account option from the cash deposit dropdown.')
async def delete_bank_account(account_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> None:
    await service.delete_bank_account(current_user, account_id)


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
    return await service.list_inventory(current_user, page=page, page_size=page_size, search=search, status=status_filter, category=category)


@router.get('/inventory/{item_id}', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'], summary='Inventory Detail', description='Returns the inventory detail screen payload for one product.', include_in_schema=False)
async def get_inventory_item(item_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.get_inventory_item(current_user, item_id)


@router.patch('/inventory/{item_id}', response_model=InventoryDetailResponse, tags=['Restaurant Inventory'], summary='Update Inventory Item', description='Updates inventory item fields such as supplier, threshold, or stock metadata.', include_in_schema=False)
async def update_inventory_item(item_id: str, payload: InventoryUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.update_inventory_item(current_user, item_id, payload)


@router.delete('/inventory/{item_id}', status_code=status.HTTP_204_NO_CONTENT, tags=['Restaurant Inventory'], summary='Delete Inventory Item', description='Deletes one inventory item.', include_in_schema=False)
async def delete_inventory_item(item_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_inventory_item(current_user, item_id)
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
    return await service.get_analytics(current_user, period=period, from_date=from_date, to_date=to_date)


@router.get('/analytics/export', tags=['Restaurant Analytics'], summary='Export Analytics Report', description='Exports analytics data in PDF or Excel format for weekly or monthly period.')
async def export_analytics_report(
    period: str = Query(default='weekly', pattern='^(weekly|monthly)$'),
    format: str = Query(default='pdf', pattern='^(pdf|excel)$'),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> Response:
    file_name, media_type, content = await service.export_analytics_report(
        current_user,
        period=period,
        export_format=format,
        from_date=from_date,
        to_date=to_date,
    )
    return Response(content=content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="{file_name}"'})


@router.get('/analytics/business-insight', response_model=AnalyticsInsightBannerResponse, tags=['Restaurant Analytics'], summary='Analytics Business Insight', description='Returns the top analytics insight banner generated from restaurant data.')
async def get_analytics_business_insight(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> AnalyticsInsightBannerResponse:
    return await service.get_analytics_business_insight(current_user)


@router.get('/chat/messages', response_model=ChatConversationResponse, tags=['Restaurant Chat'], summary='List Chat Messages', description='Returns the current restaurant AI chat conversation.')
async def list_chat_messages(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await service.list_chat_messages(current_user)


@router.post('/chat/messages', response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Chat'], summary='Create Chat Message', description='Sends a user message and returns the updated AI chat conversation.')
async def create_chat_message(payload: ChatMessageCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await service.create_chat_message(current_user, payload)


@router.post('/chat/messages/attachments', response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED, tags=['Restaurant Chat'], summary='Create Chat Message With Attachment', description='Sends a user message with a shared document and returns the updated personalized AI chat conversation.')
async def create_chat_message_with_attachment(
    message: str = Form(...),
    attachment_source: str | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> ChatConversationResponse:
    content_type = (file.content_type or '').lower()
    if content_type not in ALLOWED_CHAT_ATTACHMENT_CONTENT_TYPES:
        raise ValidationException('Only PDF, CSV, TXT, PNG, JPG, JPEG, and WEBP files are supported for chat attachments')
    file_bytes = await file.read()
    return await service.create_chat_message_with_attachment(
        current_user,
        payload=ChatMessageCreateRequest(message=message, attachment_source=attachment_source),
        file_name=file.filename or 'chat-attachment',
        content_type=content_type,
        file_bytes=file_bytes,
    )


@router.get('/settings/profile', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'], summary='Profile Detail', description='Returns the restaurant profile and settings data.')
async def get_profile(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantProfileResponse:
    return await service.get_profile(current_user)


@router.put('/settings/profile', response_model=RestaurantProfileResponse, tags=['Restaurant Settings'], summary='Update Profile', description='Updates restaurant profile and settings fields.')
async def update_profile(
    full_name: str | None = Form(default=None, min_length=2, max_length=120),
    phone: str | None = Form(default=None, max_length=30),
    restaurant_name: str | None = Form(default=None, max_length=120),
    restaurant_type: str | None = Form(default=None, max_length=80),
    location: str | None = Form(default=None, max_length=120),
    city_location: str | None = Form(default=None, max_length=120),
    number_of_seats: int | None = Form(default=None, ge=0),
    profile_image: UploadFile | None = File(default=None),
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
    )
    return await service.update_profile_with_image(current_user, payload, profile_image=profile_image)

