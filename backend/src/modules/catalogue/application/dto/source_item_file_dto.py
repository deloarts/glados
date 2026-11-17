"""
DTOs for source item file results and update commands.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)
from src.modules.platform.application.dto.base import ResultBase


class SourceItemFileResult(ResultBase):
    source_item_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: SourceItemFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed


class UpdateSourceItemFileCommand(BaseModel):
    file_name: str = Field(..., min_length=1)
