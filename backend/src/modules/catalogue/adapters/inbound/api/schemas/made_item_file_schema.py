"""HTTP schemas for made-item file upload, storage, and retrieval."""

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.item_file_base_schema import (
    ItemFileResponseBase,
)
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory


class MadeItemFileResponse(ItemFileResponseBase):
    made_item_id: int
    category: MadeItemFileCategory
    from_pdm: bool


class MadeItemFileUpdateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
