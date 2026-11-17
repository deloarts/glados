"""
Repository interfaces for the MadeItem catalogue and MadeItemProcess
aggregates.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto


@runtime_checkable
class IMadeItemRepository(Protocol):
    async def get_by_id(self, id: int) -> MadeItem | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_revisions(self, part_number: str) -> list[MadeItem]:
        """All non-archived rows sharing `part_number`: a family's
        revisions. Order is not guaranteed to any particular scheme;
        callers needing "newest first" apply that sort key themselves."""
        ...

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        """Batch counterpart to get_revisions' existence check: which of
        `part_numbers` have at least one non-archived row, without
        fetching the rows themselves. Used by reconcile_pdm_vault's
        registry cross-check, which only needs presence, not the
        family's contents."""
        ...

    async def get_by_part_number_and_revision(
        self, part_number: str, revision: str
    ) -> MadeItem | None:
        """The one non-archived row identified by the (part_number,
        revision) pair `uq_made_item_part_number_revision` makes
        unique."""
        ...

    async def get_family(self, part_number: str) -> list[MadeItem]:
        """Every row sharing `part_number`, archived included. Used
        only by UpdateMadeItem's renumber path, which must rename every
        row of a family (not just the live ones) to keep
        uq_made_item_part_number_revision (a TOTAL index) satisfied.
        Contrast get_revisions, which excludes archived rows for
        read-facing uses (GetMadeItemRevisions)."""
        ...

    async def get_family_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> list[MadeItem]:
        """Every non-archived revision row of the PDM file identified by
        (vault_id, pdm_file_id), newest revision first (same ordering as
        get_multi's latest_only window: revision_scheme.sort_key, ties
        broken by created desc, id desc). Used by ingest to find the
        current newest row of a part and decide new-revision vs.
        update-in-place."""
        ...

    async def get_multi(self, filters: MadeItemFilterDto) -> tuple[int, list[MadeItem]]: ...

    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[MadeItem]]:
        """Paged, non-archived rows with data_source == "CAD", ordered by
        id. Used by ReconcilePdmVault to walk every CAD-owned made item
        without the general-purpose filtering/sorting get_multi carries
        for the catalogue UI: the reconciliation report only ever needs
        this one filter, paged simply so a large catalogue is never loaded
        in one query."""
        ...

    async def save(self, item: MadeItem) -> MadeItem: ...
    async def delete(self, item: MadeItem) -> None: ...
    async def merge_references(self, source_id: int, target_id: int) -> None:
        """Points the successor links that name the source item at the
        target. The lots and demands move through IMadeItemUsages."""
        ...

    async def merge_article_groups(self, source_id: int, target_id: int) -> None: ...

    # ── Process steps (owned, ordered children) ────────────────────────
    async def get_processes(self, made_item_id: int) -> list[MadeItemProcess]: ...
    async def get_process_by_id(self, process_id: int) -> MadeItemProcess | None: ...
    async def save_process(self, process: MadeItemProcess) -> MadeItemProcess: ...
    async def delete_process(self, process: MadeItemProcess) -> None: ...
    async def reorder_processes(
        self, made_item_id: int, ordered_process_ids: list[int]
    ) -> list[MadeItemProcess]: ...
    async def set_process_groups(
        self, made_item_id: int, groups: list[list[int]]
    ) -> list[MadeItemProcess]: ...
