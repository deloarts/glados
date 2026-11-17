"""
Which catalogue the item a PDM file snapshot names belongs to, so the admin
"PDM files" list can link each row to the right item page. A made or bought
snapshot is its own answer. A document snapshot's kind is only "document",
so its item's catalogue comes from the file's document link instead.
"""

from collections import defaultdict

from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.ports.outbound.repositories.pdm_document_link_repository import (
    IPdmDocumentLinkRepository,
)

_ITEM_KINDS = ("made", "bought")


async def snapshot_item_kinds(
    snapshots: list[PdmFileSnapshot], links: IPdmDocumentLinkRepository | None
) -> dict[int, str | None]:
    """The item's catalogue ("made" or "bought") per snapshot id, None for a
    snapshot naming no item. Document links are read once per vault on the
    page. Without a link repository a document's catalogue stays unknown."""
    kinds: dict[int, str | None] = {}
    documents_by_vault: dict[str, list[PdmFileSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.item_id is None:
            kinds[snapshot.id] = None
        elif snapshot.kind in _ITEM_KINDS:
            kinds[snapshot.id] = snapshot.kind
        else:
            kinds[snapshot.id] = None
            documents_by_vault[snapshot.vault_id].append(snapshot)

    if links is None:
        return kinds
    for vault_id, documents in documents_by_vault.items():
        found = await links.get_by_pdm_files(vault_id, [s.file_id for s in documents])
        link_by_file = {link.file_id: link for link in found}
        for snapshot in documents:
            link = link_by_file.get(snapshot.file_id)
            # A link pointing at another item says nothing about this one.
            if link is not None and link.item_id == snapshot.item_id:
                kinds[snapshot.id] = link.kind
    return kinds
