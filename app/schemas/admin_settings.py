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
    last_updated_label: str = 'Last updated:'
    last_updated_value: str
    icon_key: str
    edit_button_label: str = 'Edit'
    edit_endpoint: str


class AdminSettingsOverviewResponse(BaseSchema):
    page_title: str = 'Settings'
    page_subtitle: str = 'Manage platform configuration and legal information.'
    general_settings_title: str = 'General Settings'
    platform_name_label: str = 'Platform Name'
    support_email_label: str = 'Support Email'
    default_language_label: str = 'Default Language'
    legal_pages_title: str = 'Legal Pages'
    discard_button_label: str = 'Discard Changes'
    save_button_label: str = 'Save Changes'
    save_endpoint: str = '/api/v1/settings/overview'
    profile_image_url: str | None = None
    platform_name: str
    support_email: EmailStr
    default_language: str
    default_language_options: list[AdminSettingsLanguageOptionResponse] = Field(default_factory=list)
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
    page_title: str = 'Legal Content Editor'
    last_updated_label: str = 'Last updated:'
    auto_save_label: str = 'Auto-save enabled'
    draft_saved_label: str = 'Draft saved'
    save_button_label: str = 'Save Changes'
    active_tab: str
    last_updated_value: str
    tabs: list[AdminLegalTabResponse] = Field(default_factory=list)
    toolbar_actions: list[AdminLegalToolbarActionResponse] = Field(default_factory=list)
    content: str
    save_endpoint: str


class AdminLegalContentUpdateRequest(BaseSchema):
    content: str = Field(min_length=1)


class AdminSettingsActionResponse(BaseSchema):
    message: str
    settings: AdminSettingsOverviewResponse | None = None
    editor: AdminLegalContentEditorResponse | None = None
