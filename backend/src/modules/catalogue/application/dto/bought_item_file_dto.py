"""DTOs for bought item file operations."""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.platform.application.dto.base import ResultBase


class BoughtItemFileResult(ResultBase):
    bought_item_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: BoughtItemFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed
    # Whether a PdmDocumentLink row backs this file (see
    # application.use_cases.pdm.pdm_documents.PdmDocumentSync), resolved by
    # GetBoughtItemFiles, one query per listing, never per file.
    from_pdm: bool


class UpdateBoughtItemFileCommand(BaseModel):
    file_name: str = Field(..., min_length=1)
