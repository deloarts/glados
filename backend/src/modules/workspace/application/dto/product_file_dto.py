"""
DTOs for product file attachments: the upload history and metadata
recorded for files attached to a product.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory


class ProductFileResult(ResultBase):
    product_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: ProductFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed


class UpdateProductFileCommand(BaseModel):
    file_name: str = Field(..., min_length=1)
