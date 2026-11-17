"""
HTTP schemas for a product's variants.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class ProductVariantRequest(BaseModel):
    id: int | None = None
    name: str = Field(max_length=500)


class ProductVariantsSaveRequest(BaseModel):
    variants: list[ProductVariantRequest] = Field(max_length=200)


class ProductVariantResponse(EntityResponse):
    product_id: int
    name: str
    sort_order: int
    archived: bool
