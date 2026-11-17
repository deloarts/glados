"""File categories for SourceItem (raw stock) catalogue entries: mesh
geometry and datasheets. Pictures are not files; see ItemPicture."""

from enum import Enum
from enum import unique


@unique
class SourceItemFileCategory(str, Enum):
    """Deliberately narrower than the bought/made item categories: a source
    item is raw stock identified by dimension, material and type. There is no
    assembly geometry to attach, so STEP has no owner here. A source item can
    still carry a 3D mesh (STL or 3MF) of the stock shape, so MESH is shared
    with bought/made. What else gets attached is its material certificate
    or supplier datasheet; a photo of the stock is an ItemPicture."""

    MESH = "mesh"  # singleton, 3D mesh file (STL or 3MF)
    PDF = "pdf"  # multiple, material certificate / datasheet

    @classmethod
    def singletons(cls) -> set["SourceItemFileCategory"]:
        return {cls.MESH}

    def is_singleton(self) -> bool:
        return self in self.singletons()
