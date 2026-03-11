from __future__ import annotations

from pydantic import Field, HttpUrl, field_validator

from app.schemas.common import BaseSchema


class MenuCategoryCreate(BaseSchema):
    restaurant_id: str
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    sort_order: int = 0


class MenuCategoryUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    sort_order: int | None = None


class MenuCategoryRead(BaseSchema):
    id: str
    restaurant_id: str
    name: str
    description: str | None = None
    sort_order: int
    created_at: str
    updated_at: str


class MenuItemCreate(BaseSchema):
    restaurant_id: str
    category_id: str
    branch_id: str | None = None
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    price: float = Field(gt=0)
    image_url: HttpUrl | None = None
    availability: bool = True
    preparation_time: int | None = Field(default=None, ge=1, le=240)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in value if item.strip()})


class MenuItemUpdate(BaseSchema):
    category_id: str | None = None
    branch_id: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, gt=0)
    image_url: HttpUrl | None = None
    availability: bool | None = None
    preparation_time: int | None = Field(default=None, ge=1, le=240)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def normalize_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return sorted({item.strip().lower() for item in value if item.strip()})


class MenuAvailabilityUpdate(BaseSchema):
    availability: bool


class MenuItemRead(BaseSchema):
    id: str
    restaurant_id: str
    branch_id: str | None = None
    category_id: str
    name: str
    description: str | None = None
    price: float
    image_url: str | None = None
    availability: bool
    preparation_time: int | None = None
    tags: list[str]
    created_at: str
    updated_at: str
