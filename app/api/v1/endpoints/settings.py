from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_admin_settings_service
from app.schemas.admin_settings import (
    AdminLegalContentEditorResponse,
    AdminLegalContentUpdateRequest,
    AdminSettingsActionResponse,
    AdminSettingsOverviewResponse,
    AdminSettingsUpdateRequest,
)
from app.services.admin_settings import AdminSettingsService

router = APIRouter()


@router.get('/overview', response_model=AdminSettingsOverviewResponse, tags=['Settings'], summary='Admin Settings Overview', description='Returns the admin settings page payload including general settings and connected legal page links.')
async def get_settings_overview(
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsOverviewResponse:
    return await service.get_overview(current_user)


@router.put('/overview', response_model=AdminSettingsActionResponse, tags=['Settings'], summary='Update Admin Settings', description='Updates the platform-level admin settings fields shown on the settings page.')
async def update_settings_overview(
    payload: AdminSettingsUpdateRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsActionResponse:
    return await service.update_overview(current_user, payload)


@router.get('/legal-content', response_model=AdminLegalContentEditorResponse, tags=['Settings'], summary='Legal Content Editor', description='Returns the connected legal editor page for Terms of Service or Privacy Policy.')
async def get_legal_content_editor(
    tab: str = Query('terms'),
    _: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminLegalContentEditorResponse:
    return await service.get_legal_editor(tab)


@router.put('/legal-content/{document_key}', response_model=AdminSettingsActionResponse, tags=['Settings'], summary='Update Legal Content', description='Saves the edited Terms of Service or Privacy Policy content from the legal editor.')
async def update_legal_content(
    document_key: str,
    payload: AdminLegalContentUpdateRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsActionResponse:
    return await service.update_legal_editor(document_key, current_user, payload)
