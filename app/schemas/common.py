from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.constants import DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, populate_by_name=True)


class PaginationQuery(BaseSchema):
    page: int = Field(default=DEFAULT_PAGE, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class PaginatedResponse(BaseSchema, Generic[T]):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[T]


class MessageResponse(BaseSchema):
    message: str


class ErrorDetail(BaseSchema):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseSchema):
    success: bool = False
    error: ErrorDetail


class MongoReadSchema(BaseSchema):
    id: str
    created_at: str
    updated_at: str


class EmailMixin(BaseSchema):
    email: EmailStr
