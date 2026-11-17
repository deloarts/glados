"""HTTP schemas for production order file upload, storage, and retrieval."""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse


class ProductionOrderFileResponse(EntityResponse):
    production_order_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: ProductionOrderFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None


class ProductionOrderFileUpdateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
