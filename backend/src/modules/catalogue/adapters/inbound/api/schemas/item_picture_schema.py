"""
HTTP schemas for item pictures (made, bought and source items).
"""

from datetime import datetime

from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class ItemPictureResponse(EntityResponse):
    item_id: int
    source: ItemPictureSource
    file_name: str
    has_image: bool
    has_thumbnail: bool
    created: datetime
    uploaded_by_user_id: int
    in_use: bool


class ItemPictureInUseResponse(ResponseModel):
    item_id: int
    picture_id: int
    source: ItemPictureSource
