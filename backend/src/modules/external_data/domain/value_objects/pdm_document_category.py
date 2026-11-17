"""
The values AdminPdmSettings.document_categories may map a file extension
to: every made and bought item file category, plus `image_and_thumbnail`,
which stores one exported image as the matched item's CAD rendering (an
ItemPicture of source CAD_RENDERING, its thumbnail derived from it). The
value keeps its name from when such an image filled the item's image and
thumbnail file slots.
"""

from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)
from src.modules.catalogue.domain.value_objects.made_item_file_category import MadeItemFileCategory

IMAGE_AND_THUMBNAIL = "image_and_thumbnail"


def allowed_document_categories() -> set[str]:
    return (
        {c.value for c in MadeItemFileCategory}
        | {c.value for c in BoughtItemFileCategory}
        | {IMAGE_AND_THUMBNAIL}
    )


DOCUMENT_KINDS = ("made", "bought")


def normalize_document_excluded_kinds(value: dict[str, list[str]]) -> dict[str, list[str]]:
    """Normalises AdminPdmSettings.document_excluded_kinds as the request
    validators receive it: extension keys the same way as the category map's,
    each list deduplicated and sorted, and empty lists dropped. Raises
    ValueError for a malformed extension or an unknown kind."""
    normalised: dict[str, list[str]] = {}
    for ext, kinds in value.items():
        key = ext.strip().lower().lstrip(".")
        if not key or not key.isalnum():
            raise ValueError(f"invalid extension {key!r}: must be lower-case alphanumeric.")
        unknown = sorted(set(kinds) - set(DOCUMENT_KINDS))
        if unknown:
            raise ValueError(f"unknown item kind {unknown[0]!r} for extension {key!r}.")
        if kinds:
            normalised[key] = sorted(set(kinds))
    return normalised
