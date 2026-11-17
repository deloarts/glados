"""
Commands and results of the product variant use cases.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class ProductVariantDraft(BaseModel):
    id: int | None = None
    name: str


class SaveProductVariantsCommand(BaseModel):
    variants: list[ProductVariantDraft]


class ProductVariantResult(ResultBase):
    product_id: int
    name: str
    sort_order: int
    archived: bool
