"""HTTP schemas for product file upload, storage, and retrieval."""

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.item_file_base_schema import (
    ItemFileResponseBase,
)
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory


class ProductFileResponse(ItemFileResponseBase):
    product_id: int
    category: ProductFileCategory


class ProductFileUpdateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
