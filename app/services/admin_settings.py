from __future__ import annotations

from datetime import datetime

from fastapi import UploadFile

from app.core.exceptions import ValidationException
from app.repositories.admin_settings import AdminSettingsRepository
from app.repositories.user import UserRepository
from app.schemas.admin_settings import (
    AdminLegalContentEditorResponse,
    AdminLegalContentUpdateRequest,
    AdminLegalTabResponse,
    AdminSettingsActionResponse,
    AdminSettingsGeneralResponse,
    AdminSettingsLanguageOptionResponse,
    AdminSettingsLegalPageItemResponse,
    AdminSettingsOverviewResponse,
    AdminSettingsUpdateRequest,
    PublicLegalDocumentResponse,
)
from app.services.base import BaseService
from app.services.image_storage import ImageStorageService, UploadedImage


class AdminSettingsService(BaseService):
    LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
        ("en-US", "English (United States)"),
        ("es", "Espanol"),
        ("fr", "Francais"),
        ("it", "Italiano"),
    )

    def __init__(
        self,
        admin_settings_repository: AdminSettingsRepository,
        user_repository: UserRepository,
        image_storage_service: ImageStorageService | None = None,
    ) -> None:
        self.admin_settings_repository = admin_settings_repository
        self.user_repository = user_repository
        self.image_storage_service = image_storage_service

    async def get_general(self, current_user: dict) -> AdminSettingsGeneralResponse:
        document = self.serialize(await self.admin_settings_repository.get_settings_document())
        return self._build_general_response(document, current_user)

    async def get_overview(self, current_user: dict) -> AdminSettingsOverviewResponse:
        document = self.serialize(await self.admin_settings_repository.get_settings_document())
        legal_documents = document.get("legal_documents", {})
        general = self._build_general_response(document, current_user)
        return AdminSettingsOverviewResponse(
            profile_image_url=general.profile_image_url,
            platform_name=general.platform_name,
            support_email=general.support_email,
            default_language=general.default_language,
            legal_pages=[
                self._legal_page_item(
                    "terms_of_service",
                    "Terms & Conditions",
                    "terms",
                    legal_documents.get("terms_of_service", {}),
                    "terms",
                ),
                self._legal_page_item(
                    "privacy_policy",
                    "Privacy Policy",
                    "privacy",
                    legal_documents.get("privacy_policy", {}),
                    "privacy",
                ),
            ],
        )

    async def update_overview(
        self,
        current_user: dict,
        payload: AdminSettingsUpdateRequest,
        *,
        profile_image: UploadFile | None = None,
    ) -> AdminSettingsActionResponse:
        general = await self._update_general_settings(current_user, payload, profile_image=profile_image)
        settings = await self.get_overview(await self.user_repository.get_by_id(current_user["_id"]))
        return AdminSettingsActionResponse(
            message="Admin settings updated successfully",
            general=general,
            settings=settings,
        )

    async def update_general(
        self,
        current_user: dict,
        payload: AdminSettingsUpdateRequest,
        *,
        profile_image: UploadFile | None = None,
    ) -> AdminSettingsActionResponse:
        general = await self._update_general_settings(current_user, payload, profile_image=profile_image)
        return AdminSettingsActionResponse(
            message="Admin general settings updated successfully",
            general=general,
        )

    async def _update_general_settings(
        self,
        current_user: dict,
        payload: AdminSettingsUpdateRequest,
        *,
        profile_image: UploadFile | None = None,
    ) -> AdminSettingsGeneralResponse:
        normalized_payload = payload.model_copy(
            update={"default_language": self._normalize_language(payload.default_language)}
        )
        await self.admin_settings_repository.update_settings_fields(normalized_payload.model_dump(mode="json"))
        refreshed_user = current_user
        if profile_image:
            avatar_url = await self._upload_profile_image(current_user, profile_image)
            refreshed_user = await self.user_repository.update(current_user["_id"], {"avatar_url": avatar_url})
        return await self.get_general(refreshed_user)

    async def get_legal_editor(self, tab: str = "terms") -> AdminLegalContentEditorResponse:
        document_key = self._resolve_tab(tab)
        document = self.serialize(await self.admin_settings_repository.get_settings_document())
        legal_document = document.get("legal_documents", {}).get(document_key, {})
        return AdminLegalContentEditorResponse(
            active_tab=tab,
            last_updated_value=self._format_legal_updated(legal_document.get("updated_at")),
            tabs=[
                AdminLegalTabResponse(key="terms", label="Terms of Service", active=tab == "terms"),
                AdminLegalTabResponse(key="privacy", label="Privacy Policy", active=tab == "privacy"),
            ],
            content=legal_document.get("content", ""),
            save_endpoint=f"/api/v1/settings/legal-content/{document_key}",
        )

    async def update_legal_editor(
        self,
        document_key: str,
        current_user: dict,
        payload: AdminLegalContentUpdateRequest,
    ) -> AdminSettingsActionResponse:
        if document_key not in {"terms_of_service", "privacy_policy"}:
            raise ValidationException("Unsupported legal document key")
        updated = await self.admin_settings_repository.update_legal_document(
            document_key, payload.content, current_user["full_name"]
        )
        serialized = self.serialize(updated)
        tab = "terms" if document_key == "terms_of_service" else "privacy"
        editor = await self.get_legal_editor(tab)
        editor.last_updated_value = self._format_legal_updated(
            serialized["legal_documents"][document_key]["updated_at"]
        )
        return AdminSettingsActionResponse(message="Legal content updated successfully", editor=editor)

    async def get_public_legal_document(self, document_key: str) -> PublicLegalDocumentResponse:
        if document_key not in {"terms_of_service", "privacy_policy"}:
            raise ValidationException("Unsupported legal document key")
        document = self.serialize(await self.admin_settings_repository.get_settings_document())
        legal_document = document.get("legal_documents", {}).get(document_key, {})
        return PublicLegalDocumentResponse(
            key=document_key,
            title=legal_document.get("title", document_key.replace("_", " ").title()),
            content=legal_document.get("content", ""),
            updated_at=legal_document.get("updated_at"),
            updated_by=legal_document.get("updated_by"),
        )

    @staticmethod
    def _resolve_tab(tab: str) -> str:
        if tab == "terms":
            return "terms_of_service"
        if tab == "privacy":
            return "privacy_policy"
        raise ValidationException("Unsupported legal editor tab")

    @staticmethod
    def _format_legal_updated(value: str | None) -> str:
        if not value:
            return "Jan 15, 2025 at 2:30 PM"
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ")

    def _legal_page_item(
        self,
        key: str,
        title: str,
        tab: str,
        payload: dict,
        icon_key: str,
    ) -> AdminSettingsLegalPageItemResponse:
        return AdminSettingsLegalPageItemResponse(
            key=key,
            title=title,
            last_updated_value=self._format_settings_legal_date(payload.get("updated_at")),
            icon_key=icon_key,
            edit_endpoint=f"/api/v1/settings/legal-content?tab={tab}",
        )

    @staticmethod
    def _format_settings_legal_date(value: str | None) -> str:
        if not value:
            return "Jan 15, 2025"
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")

    async def _upload_profile_image(self, current_user: dict, file: UploadFile) -> str:
        if not self.image_storage_service:
            raise ValidationException("Image upload service is not configured")
        uploaded: UploadedImage = await self.image_storage_service.upload_file(
            file=file,
            prefix=f"admin-settings/{current_user['_id']}/profile-image",
        )
        return uploaded.url

    def _resolve_profile_image_url(self, value: str | None) -> str | None:
        if not self.image_storage_service:
            return value
        return self.image_storage_service.resolve_public_url(value)

    def _build_general_response(self, document: dict, current_user: dict) -> AdminSettingsGeneralResponse:
        default_language = self._normalize_language(document["default_language"])
        return AdminSettingsGeneralResponse(
            profile_image_url=self._resolve_profile_image_url(current_user.get("avatar_url")),
            platform_name=document["platform_name"],
            support_email=document["support_email"],
            default_language=default_language,
            language_options=[
                AdminSettingsLanguageOptionResponse(
                    key=key,
                    label=label,
                    active=key == default_language,
                )
                for key, label in self.LANGUAGE_OPTIONS
            ],
            save_endpoint="/api/v1/settings/general",
        )

    def _normalize_language(self, value: str) -> str:
        normalized = value.strip()
        language_map = {key.lower(): key for key, _ in self.LANGUAGE_OPTIONS}
        label_map = {label.lower(): key for key, label in self.LANGUAGE_OPTIONS}

        if normalized.lower() in language_map:
            return language_map[normalized.lower()]
        if normalized.lower() in label_map:
            return label_map[normalized.lower()]
        return normalized
