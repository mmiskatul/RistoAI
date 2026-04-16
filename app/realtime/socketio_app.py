from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI

from app.core.exceptions import AuthenticationException, ValidationException
from app.core.security import token_manager
from app.db.mongodb import MongoDB
from app.dependencies.services import build_restaurant_operations_service
from app.repositories.restaurant_ops import ScopedRepository
from app.repositories.user import UserRepository
from app.schemas.restaurant import ChatConversationResponse, ChatMessageCreateRequest, ChatMessageUpdateRequest

logger = logging.getLogger(__name__)

try:
    import socketio
except ImportError:
    socketio = None


class RestaurantChatSocketGateway:
    namespace = "/restaurant-chat"
    event_conversation = "chat:conversation"
    event_error = "chat:error"

    def __init__(self) -> None:
        self.sio = None
        if socketio is None:
            return
        self.sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
        self._register_handlers()

    @property
    def enabled(self) -> bool:
        return self.sio is not None

    def wrap_app(self, fastapi_app: FastAPI):
        if not self.enabled:
            return fastapi_app
        return socketio.ASGIApp(self.sio, other_asgi_app=fastapi_app, socketio_path="socket.io")

    def _register_handlers(self) -> None:
        assert self.sio is not None

        @self.sio.event(namespace=self.namespace)
        async def connect(sid: str, environ: dict[str, Any], auth: dict[str, Any] | None):
            user = await self._authenticate(auth=auth, environ=environ)
            scope_id = ScopedRepository.resolve_scope_id(user)
            room = self._room(scope_id)
            await self.sio.save_session(sid, {"user": user, "scope_id": scope_id, "room": room}, namespace=self.namespace)
            await self.sio.enter_room(sid, room, namespace=self.namespace)
            conversation = await self._list_conversation(user)
            await self.sio.emit(self.event_conversation, conversation.model_dump(mode="json"), room=sid, namespace=self.namespace)

        @self.sio.event(namespace=self.namespace)
        async def disconnect(sid: str):
            try:
                session = await self.sio.get_session(sid, namespace=self.namespace)
            except KeyError:
                return
            room = session.get("room")
            if room:
                await self.sio.leave_room(sid, room, namespace=self.namespace)

        @self.sio.on("chat:history", namespace=self.namespace)
        async def chat_history(sid: str):
            session = await self._require_session(sid)
            conversation = await self._list_conversation(session["user"])
            payload = conversation.model_dump(mode="json")
            await self.sio.emit(self.event_conversation, payload, room=sid, namespace=self.namespace)
            return payload

        @self.sio.on("chat:message", namespace=self.namespace)
        async def chat_message(sid: str, data: dict[str, Any] | None):
            session = await self._require_session(sid)
            payload = ChatMessageCreateRequest(message=str((data or {}).get("message") or "").strip(), attachment_source=(data or {}).get("attachment_source"))
            conversation = await self._service().create_chat_message(session["user"], payload)
            return await self._broadcast_conversation(session["room"], conversation)

        @self.sio.on("chat:message_edit", namespace=self.namespace)
        async def chat_message_edit(sid: str, data: dict[str, Any] | None):
            session = await self._require_session(sid)
            resolved = data or {}
            message_id = str(resolved.get("message_id") or "").strip()
            payload = ChatMessageUpdateRequest(message=str(resolved.get("message") or "").strip())
            conversation = await self._service().update_chat_message(session["user"], message_id, payload)
            return await self._broadcast_conversation(session["room"], conversation)

        @self.sio.on("chat:attachment", namespace=self.namespace)
        async def chat_attachment(sid: str, data: dict[str, Any] | None):
            session = await self._require_session(sid)
            resolved = data or {}
            message = str(resolved.get("message") or "").strip()
            file_name = str(resolved.get("file_name") or "attachment")
            content_type = str(resolved.get("content_type") or "application/octet-stream")
            encoded = str(resolved.get("file_base64") or "")
            if not encoded:
                raise ValidationException("file_base64 is required")
            try:
                file_bytes = base64.b64decode(encoded, validate=True)
            except Exception as exc:  # noqa: BLE001
                raise ValidationException("Invalid base64 attachment payload") from exc
            payload = ChatMessageCreateRequest(message=message, attachment_source=resolved.get("attachment_source"))
            conversation = await self._service().create_chat_message_with_attachment(
                session["user"],
                payload=payload,
                file_name=file_name,
                content_type=content_type,
                file_bytes=file_bytes,
            )
            return await self._broadcast_conversation(session["room"], conversation)

    async def _broadcast_conversation(self, room: str, conversation: ChatConversationResponse) -> dict[str, Any]:
        payload = conversation.model_dump(mode="json")
        await self.sio.emit(self.event_conversation, payload, room=room, namespace=self.namespace)
        return payload

    async def _require_session(self, sid: str) -> dict[str, Any]:
        try:
            return await self.sio.get_session(sid, namespace=self.namespace)
        except KeyError as exc:
            raise AuthenticationException("Socket session is not authenticated") from exc

    async def _authenticate(self, *, auth: dict[str, Any] | None, environ: dict[str, Any]) -> dict[str, Any]:
        token = self._extract_token(auth=auth, environ=environ)
        if not token:
            raise ConnectionRefusedError("Missing access token")
        payload = token_manager.decode_token(token)
        if payload.get("type") != "access":
            raise ConnectionRefusedError("Invalid access token")
        db = MongoDB.get_database()
        user = await UserRepository(db).get_optional_by_id(payload["sub"])
        if not user or not user.get("is_active", False):
            raise ConnectionRefusedError("User account is invalid or inactive")
        return user

    def _extract_token(self, *, auth: dict[str, Any] | None, environ: dict[str, Any]) -> str | None:
        if auth:
            token = auth.get("token") or auth.get("access_token")
            if isinstance(token, str) and token.strip():
                return token.strip()
            authorization = auth.get("authorization")
            if isinstance(authorization, str) and authorization.lower().startswith("bearer "):
                return authorization.split(" ", 1)[1].strip()
        authorization_header = environ.get("HTTP_AUTHORIZATION")
        if isinstance(authorization_header, str) and authorization_header.lower().startswith("bearer "):
            return authorization_header.split(" ", 1)[1].strip()
        query_string = environ.get("QUERY_STRING", "")
        if isinstance(query_string, bytes):
            query_string = query_string.decode("utf-8", errors="ignore")
        params = parse_qs(query_string)
        for key in ("token", "access_token"):
            values = params.get(key)
            if values and values[0].strip():
                return values[0].strip()
        return None

    async def _list_conversation(self, user: dict) -> ChatConversationResponse:
        return await self._service().list_chat_messages(user)

    def _service(self):
        db = MongoDB.get_database()
        return build_restaurant_operations_service(db)

    @staticmethod
    def _room(scope_id: str) -> str:
        return f"restaurant-chat:{scope_id}"


def create_socketio_app(fastapi_app: FastAPI):
    gateway = RestaurantChatSocketGateway()
    fastapi_app.state.socketio_gateway = gateway
    if not gateway.enabled:
        logger.warning("python-socketio is not installed; Socket.IO chat is disabled")
        return fastapi_app
    wrapped_app = gateway.wrap_app(fastapi_app)
    setattr(wrapped_app, "fastapi_app", fastapi_app)
    setattr(wrapped_app, "dependency_overrides", fastapi_app.dependency_overrides)
    setattr(wrapped_app, "state", fastapi_app.state)
    return wrapped_app
