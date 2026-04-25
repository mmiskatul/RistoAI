from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.dependencies.services import get_admin_settings_service
from app.schemas.admin_settings import (
    AdminLegalContentEditorResponse,
    AdminLegalContentUpdateRequest,
    AdminSettingsActionResponse,
    AdminSettingsOverviewResponse,
    AdminSettingsUpdateRequest,
    PublicLegalDocumentResponse,
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
    platform_name: str = Form(..., min_length=2, max_length=120),
    support_email: str = Form(...),
    default_language: str = Form(..., min_length=2, max_length=80),
    profile_image: UploadFile | None = File(default=None),
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsActionResponse:
    payload = AdminSettingsUpdateRequest(
        platform_name=platform_name,
        support_email=support_email,
        default_language=default_language,
    )
    return await service.update_overview(current_user, payload, profile_image=profile_image)


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


@router.get('/terms-and-conditions', response_model=PublicLegalDocumentResponse, tags=['Settings'], summary='Public Terms And Conditions', description='Returns the Terms and Conditions content managed by the admin settings page.')
async def get_terms_and_conditions(
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> PublicLegalDocumentResponse:
    return await service.get_public_legal_document('terms_of_service')


@router.get('/terms-of-service', response_model=PublicLegalDocumentResponse, tags=['Settings'], summary='Public Terms Of Service', description='Returns the Terms of Service content managed by the admin settings page.')
async def get_terms_of_service(
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> PublicLegalDocumentResponse:
    return await service.get_public_legal_document('terms_of_service')


@router.put('/terms-of-service', response_model=AdminSettingsActionResponse, tags=['Settings'], summary='Update Terms Of Service', description='Updates the Terms of Service content managed by the admin settings page.')
async def update_terms_of_service(
    payload: AdminLegalContentUpdateRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsActionResponse:
    return await service.update_legal_editor('terms_of_service', current_user, payload)


@router.get('/privacy-policy', response_model=PublicLegalDocumentResponse, tags=['Settings'], summary='Public Privacy Policy', description='Returns the Privacy Policy content managed by the admin settings page.')
async def get_privacy_policy(
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> PublicLegalDocumentResponse:
    return await service.get_public_legal_document('privacy_policy')


@router.get('/privacy', response_model=PublicLegalDocumentResponse, tags=['Settings'], summary='Public Privacy Policy Alias', description='Returns the Privacy Policy content managed by the admin settings page.')
async def get_privacy_policy_alias(
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> PublicLegalDocumentResponse:
    return await service.get_public_legal_document('privacy_policy')


@router.put('/privacy-policy', response_model=AdminSettingsActionResponse, tags=['Settings'], summary='Update Privacy Policy', description='Updates the Privacy Policy content managed by the admin settings page.')
async def update_privacy_policy(
    payload: AdminLegalContentUpdateRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsActionResponse:
    return await service.update_legal_editor('privacy_policy', current_user, payload)


@router.put('/privacy', response_model=AdminSettingsActionResponse, tags=['Settings'], summary='Update Privacy Policy Alias', description='Updates the Privacy Policy content managed by the admin settings page.')
async def update_privacy_policy_alias(
    payload: AdminLegalContentUpdateRequest,
    current_user: dict = Depends(require_roles(UserRole.SUPER_ADMIN)),
    service: AdminSettingsService = Depends(get_admin_settings_service),
) -> AdminSettingsActionResponse:
    return await service.update_legal_editor('privacy_policy', current_user, payload)
