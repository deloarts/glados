"""
Repository interface for PdmDocumentLink, mirroring
IPdmFileSnapshotRepository's shape for the one table PdmDocumentSync owns.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.external_data.domain.entities.pdm_document_link import PdmDocumentLink


@runtime_checkable
class IPdmDocumentLinkRepository(Protocol):
    async def get_by_pdm_file(self, vault_id: str, file_id: int) -> PdmDocumentLink | None: ...

    async def get_by_pdm_files(self, vault_id: str, file_ids: list[int]) -> list[PdmDocumentLink]:
        """The links of every listed file of `vault_id` that has one, in one
        query, for a page of the admin "PDM files" list."""
        ...

    async def upsert(self, link: PdmDocumentLink) -> PdmDocumentLink:
        """Inserts or updates the row matched on (vault_id, file_id). Does
        not commit; PdmDocumentSync commits as part of its own write."""
        ...

    async def delete(self, link: PdmDocumentLink) -> None: ...

    async def get_linked_item_file_ids(self, item_file_ids: list[int]) -> set[int]:
        """The subset of `item_file_ids` that a PdmDocumentLink row backs,
        one query for a whole file
        listing's `from_pdm` flag, rather than one query per file."""
        ...

    async def all_for_vault(self, vault_id: str) -> list[PdmDocumentLink]:
        """Every document link row of `vault_id`, unpaged. ReconcilePdmVault
        loads the whole set once per run to check each link's snapshot for
        `document_missing`, the same "load once, diff in memory" shape it
        uses for pdm_file_snapshot itself
        (IPdmFileSnapshotRepository.get_all_for_vault)."""
        ...
