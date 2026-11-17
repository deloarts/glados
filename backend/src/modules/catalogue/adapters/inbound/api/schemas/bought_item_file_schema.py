"""
HTTP schemas for bought item file responses and file metadata updates.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.item_file_base_schema import (
    ItemFileResponseBase,
)
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)


class BoughtItemFileResponse(ItemFileResponseBase):
    bought_item_id: int
    category: BoughtItemFileCategory
    from_pdm: bool


class BoughtItemFileUpdateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
