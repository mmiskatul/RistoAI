from __future__ import annotations

from datetime import UTC, datetime

from bson import ObjectId

from app.core.enums import SupportTicketStatus
from app.core.exceptions import NotFoundException
from app.repositories.support_ticket import SupportTicketRepository
from app.schemas.support import (
    SupportManagementFilterChipResponse,
    SupportManagementRowActionResponse,
    SupportManagementSummaryCardResponse,
    SupportManagementTableColumnResponse,
    SupportTicketActionResponse,
    SupportTicketCreateRequest,
    SupportTicketCustomerResponse,
    SupportTicketDetailResponse,
    SupportTicketListItemResponse,
    SupportTicketManagementResponse,
    UserSupportTicketListResponse,
    SupportTicketMessageResponse,
    SupportTicketQuery,
    SupportTicketReplyRequest,
    SupportTicketSummaryResponse,
)
from app.services.base import BaseService
from app.utils.pagination import build_pagination_meta


class SupportService(BaseService):
    def __init__(self, support_ticket_repository: SupportTicketRepository) -> None:
        self.support_ticket_repository = support_ticket_repository

    async def create_ticket(self, current_user: dict, payload: SupportTicketCreateRequest) -> SupportTicketActionResponse:
        ticket = await self.support_ticket_repository.create(
            {
                'ticket_number': self._build_ticket_number(),
                'user_id': current_user['_id'],
                'user_name': current_user['full_name'],
                'email': current_user['email'],
                'phone': current_user.get('phone'),
                'restaurant_name': current_user.get('restaurant_name'),
                'location': current_user.get('location'),
                'subject': payload.subject,
                'status': SupportTicketStatus.OPEN,
                'priority': payload.priority,
                'messages': [
                    {
                        'author_name': current_user['full_name'],
                        'author_role': 'user',
                        'body': payload.message,
                        'is_internal': False,
                        'attachment_name': payload.attachment_name,
                        'attachment_url': payload.attachment_url,
                        'created_at': datetime.now(UTC),
                    }
                ],
                'resolved_at': None,
            }
        )
        return SupportTicketActionResponse(message='Support ticket created successfully', ticket=self._to_ticket_detail(ticket))

    async def get_management_page(self, query: SupportTicketQuery) -> SupportTicketManagementResponse:
        tickets, total = await self.support_ticket_repository.get_filtered_tickets(
            search=query.search,
            status=query.status,
            page=query.page,
            page_size=query.page_size,
        )
        pagination = build_pagination_meta(total=total, page=query.page, page_size=query.page_size)
        summary = SupportTicketSummaryResponse(
            open_tickets=await self.support_ticket_repository.count_by_status(SupportTicketStatus.OPEN),
            resolved_tickets=await self.support_ticket_repository.count_by_status(SupportTicketStatus.RESOLVED),
        )
        start = ((query.page - 1) * query.page_size) + 1 if total else 0
        end = min(query.page * query.page_size, total) if total else 0
        active_filter = str(query.status) if query.status else 'open'
        return SupportTicketManagementResponse(
            filter_chips=[
                SupportManagementFilterChipResponse(key='open', label='Open', is_active=active_filter == 'open'),
                SupportManagementFilterChipResponse(key='resolved', label='Resolved', is_active=active_filter == 'resolved'),
                SupportManagementFilterChipResponse(key='all', label='All Tickets', is_active=active_filter == 'all'),
            ],
            summary_cards=[
                SupportManagementSummaryCardResponse(key='active_tickets', label='Active Tickets', value=summary.open_tickets, value_formatted=str(summary.open_tickets), subtitle='Active tickets', icon_key='support_open'),
                SupportManagementSummaryCardResponse(key='tickets_resolved', label='Tickets Resolved', value=summary.resolved_tickets, value_formatted=str(summary.resolved_tickets), subtitle='Tickets resolved', icon_key='support_resolved'),
            ],
            table_columns=[
                SupportManagementTableColumnResponse(key='user_name', label='User Name'),
                SupportManagementTableColumnResponse(key='restaurant', label='Restaurant'),
                SupportManagementTableColumnResponse(key='issue_subject', label='Issue/Subject'),
                SupportManagementTableColumnResponse(key='status', label='Status'),
                SupportManagementTableColumnResponse(key='date', label='Date'),
                SupportManagementTableColumnResponse(key='actions', label='Actions'),
            ],
            pagination_label=f"Showing {start}-{end} of {total} tickets" if total else 'Showing 0-0 of 0 tickets',
            summary=summary,
            items=[self._to_ticket_list_item(ticket) for ticket in tickets],
            **pagination,
        )

    async def get_user_tickets(self, current_user: dict, query: SupportTicketQuery) -> UserSupportTicketListResponse:
        tickets, total = await self.support_ticket_repository.get_filtered_user_tickets(
            str(current_user['_id']),
            search=query.search,
            status=query.status,
            page=query.page,
            page_size=query.page_size,
        )
        pagination = build_pagination_meta(total=total, page=query.page, page_size=query.page_size)
        return UserSupportTicketListResponse(items=[self._to_ticket_list_item(ticket) for ticket in tickets], **pagination)

    async def get_user_ticket_detail(self, current_user: dict, ticket_id: str) -> SupportTicketDetailResponse:
        ticket = await self.support_ticket_repository.get_by_id(ticket_id)
        if str(ticket['user_id']) != str(current_user['_id']):
            raise NotFoundException('Support ticket not found')
        return self._to_ticket_detail(ticket)

    async def get_ticket_detail(self, ticket_id: str) -> SupportTicketDetailResponse:
        ticket = await self.support_ticket_repository.get_by_id(ticket_id)
        return self._to_ticket_detail(ticket)

    async def reply_to_ticket(self, ticket_id: str, current_user: dict, payload: SupportTicketReplyRequest) -> SupportTicketActionResponse:
        ticket = await self.support_ticket_repository.add_message(
            ticket_id,
            {
                'author_name': current_user['full_name'],
                'author_role': 'admin',
                'body': payload.message,
                'is_internal': payload.is_internal,
                'attachment_name': None,
                'attachment_url': None,
                'created_at': datetime.now(UTC),
            },
        )
        return SupportTicketActionResponse(message='Support ticket reply sent successfully', ticket=self._to_ticket_detail(ticket))

    async def resolve_ticket(self, ticket_id: str) -> SupportTicketActionResponse:
        ticket = await self.support_ticket_repository.resolve(ticket_id)
        return SupportTicketActionResponse(message='Support ticket resolved successfully', ticket=self._to_ticket_detail(ticket))

    @staticmethod
    def _build_ticket_number() -> str:
        return f"TKT-{str(ObjectId())[-6:].upper()}"

    def _to_ticket_list_item(self, ticket: dict) -> SupportTicketListItemResponse:
        serialized = self.serialize(ticket)
        return SupportTicketListItemResponse(
            id=serialized['id'],
            ticket_number=serialized['ticket_number'],
            user_name=serialized['user_name'],
            restaurant_name=serialized.get('restaurant_name'),
            issue_subject=serialized['subject'],
            status=serialized['status'],
            priority=serialized['priority'],
            date=serialized['created_at'],
            user_restaurant_label=serialized['user_name'],
            issue_subject_label=serialized['subject'],
            status_label=str(serialized['status']).capitalize(),
            status_variant=self._status_variant(serialized['status']),
            priority_label=str(serialized['priority']).capitalize(),
            date_formatted=self._format_date(serialized['created_at']),
            view_endpoint=f"/api/v1/support/tickets/{serialized['id']}",
            action_button_label='View Ticket',
            actions_menu=self._build_row_actions(serialized['id'], serialized['status']),
        )

    def _to_ticket_detail(self, ticket: dict) -> SupportTicketDetailResponse:
        serialized = self.serialize(ticket)
        messages = [
            SupportTicketMessageResponse(
                author_name=message['author_name'],
                author_role=message['author_role'],
                body=message['body'],
                is_internal=message.get('is_internal', False),
                attachment_name=message.get('attachment_name'),
                attachment_url=message.get('attachment_url'),
                created_at=message.get('created_at', serialized['created_at']),
            )
            for message in serialized.get('messages', [])
        ]
        return SupportTicketDetailResponse(
            id=serialized['id'],
            ticket_number=serialized['ticket_number'],
            subject=serialized['subject'],
            status=serialized['status'],
            priority=serialized['priority'],
            submitted_at=serialized['created_at'],
            resolved_at=serialized.get('resolved_at'),
            customer=SupportTicketCustomerResponse(
                user_name=serialized['user_name'],
                email=serialized['email'],
                phone=serialized.get('phone'),
                location=serialized.get('location'),
                restaurant_name=serialized.get('restaurant_name'),
            ),
            messages=messages,
        )

    @staticmethod
    def _format_date(value: str) -> str:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).strftime('%b %d, %Y')

    @staticmethod
    def _build_row_actions(ticket_id: str, status: str) -> list[SupportManagementRowActionResponse]:
        actions = [SupportManagementRowActionResponse(key='view', label='View Ticket', method='GET', endpoint=f'/api/v1/support/tickets/{ticket_id}', variant='outline')]
        if status != SupportTicketStatus.RESOLVED:
            actions.append(SupportManagementRowActionResponse(key='resolve', label='Resolve Ticket', method='POST', endpoint=f'/api/v1/support/tickets/{ticket_id}/resolve', variant='ghost'))
        return actions

    @staticmethod
    def _status_variant(status: str) -> str:
        if status == SupportTicketStatus.RESOLVED:
            return 'success'
        return 'warning'
