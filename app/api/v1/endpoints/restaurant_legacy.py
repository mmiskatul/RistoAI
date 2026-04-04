from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_restaurant_operations_service
from app.schemas.restaurant import (
    AnalyticsOverviewResponse,
    CashDepositCreateRequest,
    CashDepositResponse,
    CashManagementSummaryResponse,
    ChatConversationResponse,
    ChatMessageCreateRequest,
    DailyDataCreateRequest,
    DailyDataListResponse,
    DailyDataResponse,
    DocumentConfirmRequest,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadExtractRequest,
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


@router.get("/home", response_model=RestaurantHomeResponse)
async def get_home(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantHomeResponse:
    return await service.get_home(current_user)


@router.get("/vat/overview", response_model=VatOverviewResponse)
async def get_vat_overview(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> VatOverviewResponse:
    return await service.get_vat_overview(current_user)


@router.get("/insights", response_model=list[InsightSummaryResponse])
async def list_insights(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> list[InsightSummaryResponse]:
    return await service.list_insights(current_user)


@router.get("/insights/{insight_id}", response_model=InsightDetailResponse)
async def get_insight_detail(insight_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InsightDetailResponse:
    return await service.get_insight_detail(current_user, insight_id)


@router.post("/documents/upload-extract", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED)
async def upload_and_extract_document(payload: DocumentUploadExtractRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.upload_and_extract_document(current_user, payload)


@router.post("/documents/{document_id}/confirm", response_model=DocumentDetailResponse)
async def confirm_document(document_id: str, payload: DocumentConfirmRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.confirm_document(current_user, document_id, payload)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> DocumentListResponse:
    return await service.list_documents(current_user, page=page, page_size=page_size, status=status_filter, search=search)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.get_document_detail(current_user, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentDetailResponse)
async def update_document(document_id: str, payload: DocumentConfirmRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DocumentDetailResponse:
    return await service.update_document(current_user, document_id, payload)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> Response:
    await service.delete_document(current_user, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseResponse:
    return await service.create_expense(current_user, payload)


@router.get("/expenses", response_model=ExpenseListResponse)
async def list_expenses(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ExpenseListResponse:
    return await service.list_expenses(current_user, page=page, page_size=page_size)


@router.post("/cash/deposits", response_model=CashDepositResponse, status_code=status.HTTP_201_CREATED)
async def create_cash_deposit(payload: CashDepositCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashDepositResponse:
    return await service.create_cash_deposit(current_user, payload)


@router.get("/cash/overview", response_model=CashManagementSummaryResponse)
async def get_cash_management(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> CashManagementSummaryResponse:
    return await service.get_cash_management(current_user)


@router.post("/daily-data", response_model=DailyDataResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_data(payload: DailyDataCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.create_daily_data(current_user, payload)


@router.get("/daily-data", response_model=DailyDataListResponse)
async def list_daily_data(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataListResponse:
    return await service.list_daily_data(current_user, page=page, page_size=page_size)


@router.get("/daily-data/{record_id}", response_model=DailyDataResponse)
async def get_daily_data_detail(record_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> DailyDataResponse:
    return await service.get_daily_data_detail(current_user, record_id)


@router.post("/inventory", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(payload: InventoryCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryItemResponse:
    return await service.create_inventory_item(current_user, payload)


@router.get("/inventory", response_model=InventoryListResponse)
async def list_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    service: RestaurantOperationsService = Depends(get_restaurant_operations_service),
) -> InventoryListResponse:
    return await service.list_inventory(current_user, page=page, page_size=page_size, search=search, status=status_filter, category=category)


@router.get("/inventory/{item_id}", response_model=InventoryDetailResponse)
async def get_inventory_item(item_id: str, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.get_inventory_item(current_user, item_id)


@router.post("/inventory/{item_id}/stock-update", response_model=InventoryDetailResponse)
async def update_inventory_stock(item_id: str, payload: InventoryStockUpdateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> InventoryDetailResponse:
    return await service.update_inventory_stock(current_user, item_id, payload)


@router.get("/analytics/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> AnalyticsOverviewResponse:
    return await service.get_analytics(current_user)


@router.get("/chat/messages", response_model=ChatConversationResponse)
async def list_chat_messages(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await service.list_chat_messages(current_user)


@router.post("/chat/messages", response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_message(payload: ChatMessageCreateRequest, current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> ChatConversationResponse:
    return await service.create_chat_message(current_user, payload)


@router.get("/settings/profile", response_model=RestaurantProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user), service: RestaurantOperationsService = Depends(get_restaurant_operations_service)) -> RestaurantProfileResponse:
    return await service.get_profile(current_user)


@router.put("/settings/profile", response_model=RestaurantProfileResponse)
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
