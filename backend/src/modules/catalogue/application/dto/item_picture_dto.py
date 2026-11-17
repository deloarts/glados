"""DTOs for item pictures (made, bought and source items)."""

from datetime import datetime

from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel


class ItemPictureResult(ResultBase):
    item_id: int
    source: ItemPictureSource
    file_name: str
    has_image: bool
    has_thumbnail: bool
    created: datetime
    uploaded_by_user_id: int
    # Whether this is the picture shown for the item (pick_picture).
    in_use: bool

    @classmethod
    def of(cls, picture: ItemPicture, *, in_use: bool) -> "ItemPictureResult":
        return cls(
            id=picture.id,
            public_id=picture.public_id,
            item_id=picture.item_id,
            source=picture.source,
            file_name=picture.file_name,
            has_image=picture.image_path is not None,
            has_thumbnail=picture.thumbnail_path is not None,
            created=picture.created,
            uploaded_by_user_id=picture.uploaded_by_user_id,
            in_use=in_use,
        )


class ItemPictureInUseResult(ResultModel):
    """The picture shown for one item of a batch, for a table of thumbnails
    that fetches a picture only for the rows that have one. `picture_id`
    changes whenever the picture shown changes, so it doubles as a cache
    key."""

    item_id: int
    picture_id: int
    source: ItemPictureSource
