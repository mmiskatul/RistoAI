from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_ai_chat_service
from app.schemas.ai_chat import AIChatMessageRequest, AIChatMessageResponse
from app.services.ai_chat import AIChatService

router = APIRouter()


@router.post("/message", response_model=AIChatMessageResponse)
async def send_message(
    payload: AIChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    service: AIChatService = Depends(get_ai_chat_service),
) -> AIChatMessageResponse:
    return await service.message(current_user, payload)
