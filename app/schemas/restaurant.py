from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class RestaurantCreate(BaseSchema):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    cuisine_type: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str = Field(min_length=5, max_length=255)
    settings: dict = Field(default_factory=dict)


class RestaurantUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    cuisine_type: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, min_length=5, max_length=255)
    settings: dict | None = None


class RestaurantRead(BaseSchema):
    id: str
    owner_id: str
    name: str
    description: str | None = None
    cuisine_type: str | None = None
    contact_email: EmailStr
    contact_phone: str | None = None
    address: str
    settings: dict
    created_at: str
    updated_at: str
