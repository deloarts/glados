"""
What CAD & external data may write to Catalogue's items when it ingests,
links or reconciles CAD files: the CAD source owns the CAD fields of these
rows (docs/FIELD_OWNERSHIP.md) and applies Catalogue's ownership rules
itself, so it saves the rows directly in its own transaction. Each store is
the item's query port plus those writes; Catalogue's repositories satisfy
them as they are.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.made_item_process import MadeItemProcess
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IPartNumberRegistryQueries


@runtime_checkable
class IBoughtItemCadStore(IBoughtItemQueries, Protocol):
    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[BoughtItem]]:
        """Paged, non-archived rows with data_source == "CAD", ordered by
        id. The bought-item sibling of IMadeItemRepository's same-named
        method, see that method's docstring."""
        ...

    async def save(self, item: BoughtItem) -> BoughtItem: ...


@runtime_checkable
class IMadeItemCadStore(IMadeItemQueries, Protocol):
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

    async def get_processes(self, made_item_id: int) -> list[MadeItemProcess]: ...

    async def delete_process(self, process: MadeItemProcess) -> None: ...

    async def save_process(self, process: MadeItemProcess) -> MadeItemProcess: ...


@runtime_checkable
class IPartNumberRegistryCadStore(IPartNumberRegistryQueries, Protocol):
    async def claim(self, part_number: str, kind: str) -> None:
        """Inserts the registry row for `part_number` and `kind`. Raises
        PartNumberInUseError naming the owning kind when the number is already
        registered, to any kind; the table's primary key is the hard guarantee
        against a concurrent claim."""
        ...

    async def release_if_unused(self, part_number: str) -> None:
        """Deletes the registry row for `part_number` unless a made or bought item
        row still carries it, archived rows and every revision included. Every
        path that frees a number calls it, such as a merge that deletes its
        source or a renumber that moved every row off the old number."""
        ...
