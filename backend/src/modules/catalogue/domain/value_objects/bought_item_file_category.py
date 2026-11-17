"""
Categories for BoughtItem file attachments. Singletons (STEP, mesh,
drawing, DXF) each represent one slot per item; PDF is the only category
that allows multiple documents per item. Pictures are not files; see
ItemPicture.

DRAWING and DXF mirror MadeItemFileCategory's own categories of the same
name (used by the PDM `documents` watched folder, see
application.use_cases.pdm.pdm_documents): a bought item can equally have an
exported drawing PDF or DXF attached, and AdminPdmSettings.
document_categories maps extensions to these category names uniformly
across made and bought items.
"""

from enum import Enum
from enum import unique


@unique
class BoughtItemFileCategory(str, Enum):
    STEP = "step"  # singleton, STEP 3D CAD file
    MESH = "mesh"  # singleton, 3D mesh file (STL or 3MF)
    DRAWING = "drawing"  # singleton, the technical drawing (PDF)
    DXF = "dxf"  # singleton, the technical drawing (DXF)
    PDF = "pdf"  # multiple, generic document / datasheet

    @classmethod
    def singletons(cls) -> set["BoughtItemFileCategory"]:
        return {cls.STEP, cls.MESH, cls.DRAWING, cls.DXF}

    def is_singleton(self) -> bool:
        return self in self.singletons()
