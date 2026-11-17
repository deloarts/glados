"""HTTP schemas for source item file management: uploads, metadata, and file retrieval."""

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.item_file_base_schema import (
    ItemFileResponseBase,
)
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)


class SourceItemFileResponse(ItemFileResponseBase):
    source_item_id: int
    category: SourceItemFileCategory


class SourceItemFileUpdateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
