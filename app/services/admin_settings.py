from __future__ import annotations

from datetime import datetime

from app.core.exceptions import ValidationException
from app.repositories.admin_settings import AdminSettingsRepository
from app.schemas.admin_settings import (
    AdminLegalContentEditorResponse,
    AdminLegalContentUpdateRequest,
    AdminLegalTabResponse,
    AdminSettingsActionResponse,
    AdminSettingsLegalPageItemResponse,
    AdminSettingsOverviewResponse,
    AdminSettingsUpdateRequest,
)
from app.services.base import BaseService


class AdminSettingsService(BaseService):
    def __init__(self, admin_settings_repository: AdminSettingsRepository) -> None:
        self.admin_settings_repository = admin_settings_repository

    async def get_overview(self, current_user: dict) -> AdminSettingsOverviewResponse:
        document = self.serialize(await self.admin_settings_repository.get_settings_document())
        legal_documents = document.get('legal_documents', {})
        return AdminSettingsOverviewResponse(
            profile_image_url=current_user.get('avatar_url'),
            platform_name=document['platform_name'],
            support_email=document['support_email'],
            default_language=document['default_language'],
            legal_pages=[
                self._legal_page_item('terms_of_service', 'Terms & Conditions', 'terms', legal_documents.get('terms_of_service', {}), 'terms'),
                self._legal_page_item('privacy_policy', 'Privacy Policy', 'privacy', legal_documents.get('privacy_policy', {}), 'privacy'),
            ],
        )

    async def update_overview(self, current_user: dict, payload: AdminSettingsUpdateRequest) -> AdminSettingsActionResponse:
        del current_user
        await self.admin_settings_repository.update_settings_fields(payload.model_dump(mode='json'))
        settings = await self.get_overview({'avatar_url': None})
        return AdminSettingsActionResponse(message='Admin settings updated successfully', settings=settings)

    async def get_legal_editor(self, tab: str = 'terms') -> AdminLegalContentEditorResponse:
        document_key = self._resolve_tab(tab)
        document = self.serialize(await self.admin_settings_repository.get_settings_document())
        legal_document = document.get('legal_documents', {}).get(document_key, {})
        return AdminLegalContentEditorResponse(
            active_tab=tab,
            last_updated_value=self._format_legal_updated(legal_document.get('updated_at')),
            tabs=[
                AdminLegalTabResponse(key='terms', label='Terms of Service', active=tab == 'terms'),
                AdminLegalTabResponse(key='privacy', label='Privacy Policy', active=tab == 'privacy'),
            ],
            content=legal_document.get('content', ''),
            save_endpoint=f'/api/v1/settings/legal-content/{document_key}',
        )

    async def update_legal_editor(self, document_key: str, current_user: dict, payload: AdminLegalContentUpdateRequest) -> AdminSettingsActionResponse:
        if document_key not in {'terms_of_service', 'privacy_policy'}:
            raise ValidationException('Unsupported legal document key')
        updated = await self.admin_settings_repository.update_legal_document(document_key, payload.content, current_user['full_name'])
        serialized = self.serialize(updated)
        tab = 'terms' if document_key == 'terms_of_service' else 'privacy'
        editor = await self.get_legal_editor(tab)
        editor.last_updated_value = self._format_legal_updated(serialized['legal_documents'][document_key]['updated_at'])
        return AdminSettingsActionResponse(message='Legal content updated successfully', editor=editor)

    @staticmethod
    def _resolve_tab(tab: str) -> str:
        if tab == 'terms':
            return 'terms_of_service'
        if tab == 'privacy':
            return 'privacy_policy'
        raise ValidationException('Unsupported legal editor tab')

    @staticmethod
    def _format_legal_updated(value: str | None) -> str:
        if not value:
            return 'Jan 15, 2025 at 2:30 PM'
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.strftime('%B %d, %Y at %I:%M %p').replace(' 0', ' ')

    def _legal_page_item(self, key: str, title: str, tab: str, payload: dict, icon_key: str) -> AdminSettingsLegalPageItemResponse:
        return AdminSettingsLegalPageItemResponse(
            key=key,
            title=title,
            last_updated_value=self._format_settings_legal_date(payload.get('updated_at')),
            icon_key=icon_key,
            edit_endpoint=f'/api/v1/settings/legal-content?tab={tab}',
        )

    @staticmethod
    def _format_settings_legal_date(value: str | None) -> str:
        if not value:
            return 'Jan 15, 2025'
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.strftime('%b %d, %Y')
