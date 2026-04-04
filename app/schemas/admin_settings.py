from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class AdminSettingsLanguageOptionResponse(BaseSchema):
    key: str
    label: str
    active: bool = False


class AdminSettingsLegalPageItemResponse(BaseSchema):
    key: str
    title: str
    last_updated_value: str
    icon_key: str
    edit_endpoint: str


class AdminSettingsOverviewResponse(BaseSchema):
    profile_image_url: str | None = None
    platform_name: str
    support_email: EmailStr
    default_language: str
    legal_pages: list[AdminSettingsLegalPageItemResponse] = Field(default_factory=list)


class AdminSettingsUpdateRequest(BaseSchema):
    platform_name: str = Field(min_length=2, max_length=120)
    support_email: EmailStr
    default_language: str = Field(min_length=2, max_length=80)


class AdminLegalTabResponse(BaseSchema):
    key: str
    label: str
    active: bool = False


class AdminLegalToolbarActionResponse(BaseSchema):
    key: str
    label: str


class AdminLegalContentEditorResponse(BaseSchema):
    active_tab: str
    last_updated_value: str
    tabs: list[AdminLegalTabResponse] = Field(default_factory=list)
    content: str
    save_endpoint: str


class AdminLegalContentUpdateRequest(BaseSchema):
    content: str = Field(min_length=1)


class AdminSettingsActionResponse(BaseSchema):
    message: str
    settings: AdminSettingsOverviewResponse | None = None
    editor: AdminLegalContentEditorResponse | None = None
