"""
DTOs for made-item file attachments (upload history and metadata).
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory
from src.modules.platform.application.dto.base import ResultBase


class MadeItemFileResult(ResultBase):
    made_item_id: int
    file_name: str
    stored_name: str
    mime_type: str
    size_bytes: int
    storage_path: str
    sha256: str
    category: MadeItemFileCategory
    created: datetime
    uploaded_by_user_id: int
    url: str | None  # None when storage is disabled or url generation failed
    # Whether a PdmDocumentLink row backs this file (see
    # application.use_cases.pdm.pdm_documents.PdmDocumentSync), resolved by
    # GetMadeItemFiles, one query per listing, never per file.
    from_pdm: bool


class UpdateMadeItemFileCommand(BaseModel):
    file_name: str = Field(..., min_length=1)
