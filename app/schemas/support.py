from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.enums import SupportTicketPriority, SupportTicketStatus, UserRole
from app.schemas.common import BaseSchema


class SupportTicketCreateRequest(BaseSchema):
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=5, max_length=4000)
    priority: SupportTicketPriority = SupportTicketPriority.NORMAL
    attachment_name: str | None = Field(default=None, max_length=255)
    attachment_url: str | None = Field(default=None, max_length=2000)


class SupportTicketReplyRequest(BaseSchema):
    message: str = Field(min_length=1, max_length=4000)
    is_internal: bool = False


class SupportTicketQuery(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    search: str | None = None
    status: SupportTicketStatus | None = None


class SupportTicketMessageResponse(BaseSchema):
    author_name: str
    author_role: str
    body: str
    is_internal: bool
    attachment_name: str | None = None
    attachment_url: str | None = None
    created_at: datetime


class SupportTicketDetailBadgeResponse(BaseSchema):
    label: str
    variant: str


class SupportTicketReplyComposerResponse(BaseSchema):
    title: str = "Send a Reply"
    placeholder: str = "Type your response..."
    internal_note_label: str = "Post as internal note (hidden from customer)"
    resolve_button_label: str = "Mark as Resolved"
    send_button_label: str = "Send Reply"
    reply_endpoint: str | None = None
    resolve_endpoint: str | None = None


class SupportManagementFilterChipResponse(BaseSchema):
    key: str
    label: str
    is_active: bool = False


class SupportManagementSummaryCardResponse(BaseSchema):
    key: str
    label: str
    value: int
    value_formatted: str
    icon_key: str | None = None


class SupportManagementTableColumnResponse(BaseSchema):
    key: str
    label: str


class SupportManagementRowActionResponse(BaseSchema):
    key: str
    label: str
    method: str
    endpoint: str
    variant: str | None = None


class SupportTicketListItemResponse(BaseSchema):
    id: str
    ticket_number: str
    user_name: str
    restaurant_name: str | None = None
    issue_subject: str
    status: SupportTicketStatus
    priority: SupportTicketPriority
    date: datetime
    view_endpoint: str | None = None


class SupportTicketSummaryResponse(BaseSchema):
    open_tickets: int
    resolved_tickets: int


class SupportTicketManagementResponse(BaseSchema):
    summary: SupportTicketSummaryResponse
    total: int
    page: int
    page_size: int
    pages: int
    items: list[SupportTicketListItemResponse]


class UserSupportTicketListResponse(BaseSchema):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[SupportTicketListItemResponse]


class SupportTicketCustomerResponse(BaseSchema):
    user_name: str
    email: EmailStr
    phone: str | None = None
    location: str | None = None
    restaurant_name: str | None = None


class SupportTicketDetailResponse(BaseSchema):
    id: str
    ticket_number: str
    subject: str
    status: SupportTicketStatus
    priority: SupportTicketPriority
    submitted_at: datetime
    resolved_at: datetime | None = None
    badges: list[SupportTicketDetailBadgeResponse] = Field(default_factory=list)
    customer: SupportTicketCustomerResponse
    messages: list[SupportTicketMessageResponse]
    reply_composer: SupportTicketReplyComposerResponse | None = None


class SupportTicketActionResponse(BaseSchema):
    message: str
    ticket: SupportTicketDetailResponse


class HelpCenterArticleResponse(BaseSchema):
    key: str
    title: str
    summary: str


class RestaurantHelpCenterResponse(BaseSchema):
    title: str = "Help Center"
    subtitle: str = "Get help, submit a request, and track your support tickets."
    create_ticket_endpoint: str = "/api/v1/restaurant/help-center/tickets"
    list_tickets_endpoint: str = "/api/v1/restaurant/help-center/tickets"
    articles: list[HelpCenterArticleResponse] = Field(default_factory=list)
