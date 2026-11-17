"""The two sizes an item picture is served in: the full-size image and the
thumbnail derived from it."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ItemPictureVariant(StrValueEnum):
    IMAGE = "image"
    THUMBNAIL = "thumbnail"
