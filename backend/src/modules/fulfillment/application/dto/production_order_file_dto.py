"""
DTOs for production order file attachments: the upload history and
metadata recorded for files attached to a production order, such as QA
evidence.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.platform.application.dto.base import ResultBase


class ProductionOrderFileResult(ResultBase):
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
    url: str | None  # None when storage is disabled or url generation failed


class UpdateProductionOrderFileCommand(BaseModel):
    file_name: str = Field(..., min_length=1)
