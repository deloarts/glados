"""Where an item picture comes from. An item keeps at most one picture per
source, so a photo, the EPLAN Data Portal picture and the CAD rendering
from PDM never replace one another. PICTURE is a photo of the real object
uploaded by a person; DATA_PORTAL is fetched for a bought item linked to a
portal part; CAD_RENDERING comes from PDM, as an exported image document
or as the thumbnail PDM renders on check-in.

PRECEDENCE is the order in which the picture shown for an item is chosen:
the real photo first, then the portal picture, then the CAD rendering."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ItemPictureSource(StrValueEnum):
    PICTURE = "picture"
    DATA_PORTAL = "data_portal"
    CAD_RENDERING = "cad_rendering"


PRECEDENCE: tuple[ItemPictureSource, ...] = (
    ItemPictureSource.PICTURE,
    ItemPictureSource.DATA_PORTAL,
    ItemPictureSource.CAD_RENDERING,
)
