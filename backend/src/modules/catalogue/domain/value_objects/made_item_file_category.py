"""File categories for MadeItem catalogue entries: singletons for CAD and
drawings, plus a multiple category for generic documentation. Pictures are
not files; see ItemPicture."""

from enum import Enum
from enum import unique


@unique
class MadeItemFileCategory(str, Enum):
    STEP = "step"  # singleton, STEP 3D CAD file
    MESH = "mesh"  # singleton, 3D mesh file (STL or 3MF)
    DRAWING = "drawing"  # singleton, the technical drawing (PDF)
    DXF = "dxf"  # singleton, the technical drawing (DXF)
    PDF = "pdf"  # multiple, generic document / datasheet

    @classmethod
    def singletons(cls) -> set["MadeItemFileCategory"]:
        return {cls.STEP, cls.MESH, cls.DRAWING, cls.DXF}

    def is_singleton(self) -> bool:
        return self in self.singletons()
