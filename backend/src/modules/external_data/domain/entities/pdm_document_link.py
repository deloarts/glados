"""
Links one exported PDM document (a file under a `documents` watched folder)
to the made or bought item file it was stored as, or to the item picture
for an `image_and_thumbnail` document, so item file listings can report
`from_pdm` cheaply. A document is never revisioned onto a new row, so the link is keyed
by (vault_id, file_id) alone. See application.use_cases.pdm.pdm_documents.
"""

from dataclasses import dataclass

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PdmDocumentLink(Entity):
    kind: ItemKind  # MADE or BOUGHT, the item table item_id refers to
    item_id: int
    # MadeItemFile.id or BoughtItemFile.id, per `kind`; None for a document
    # stored as the item's CAD rendering, which item_picture_id names.
    item_file_id: int | None
    vault_id: str
    file_id: int
    version: int
    item_picture_id: int | None = None
