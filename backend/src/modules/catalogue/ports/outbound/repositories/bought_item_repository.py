"""
Repository interface for the BoughtItem catalogue. The demand items and
allocations of bought items are Planning & fulfillment's, in its
bought_item_demand_repository.py.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto


@runtime_checkable
class IBoughtItemRepository(Protocol):
    async def get_by_id(self, id: int) -> BoughtItem | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_by_part_number(self, part_number: str) -> BoughtItem | None: ...

    async def existing_part_numbers(self, part_numbers: list[str]) -> set[str]:
        """Batch counterpart to get_by_part_number's existence check:
        which of `part_numbers` have a live (non-archived) row, without
        fetching the rows themselves. Used by reconcile_pdm_vault's
        registry cross-check, which only needs presence, not the row
        itself."""
        ...

    async def get_by_gtin(self, gtin: str) -> BoughtItem | None:
        """Live (non-archived) rows only, matches the scope of
        `uq_bought_item_gtin_active`."""
        ...

    async def find_by_order_code(self, manufacturer_id: int, order_code: str) -> list[BoughtItem]:
        """Live rows of `manufacturer_id` whose order_code_1 equals
        `order_code` in the comparison form of
        domain.services.order_code.normalize_order_code."""
        ...

    async def find_by_edp_part_id(self, edp_part_id: int) -> list[BoughtItem]:
        """Live rows linked to this EPLAN Data Portal part."""
        ...

    async def find_by_ean(self, ean: str) -> list[BoughtItem]:
        """Live rows with this EAN; unlike the GTIN, an EAN is not unique."""
        ...

    async def get_by_pdm_file(self, vault_id: str, pdm_file_id: int) -> BoughtItem | None:
        """The one non-archived row identified by (vault_id, pdm_file_id);
        uq_bought_item_pdm_file makes that pair unique."""
        ...

    async def list_cad_items_with_links(
        self, skip: int | None, limit: int | None
    ) -> tuple[int, list[BoughtItem]]:
        """Paged, non-archived rows with data_source == "CAD", ordered by
        id. The bought-item sibling of IMadeItemRepository's same-named
        method, see that method's docstring."""
        ...

    async def find_claim_candidate(
        self,
        *,
        gtin: str | None,
        manufacturer_id: int | None,
        order_code_1: str | None,
    ) -> BoughtItem | None:
        """Finds the single non-archived row without a PDM link (web- or
        add-in-created) a PDM file should claim on first sight
        (docs/reference/field-ownership.md sections 1 and 3): an exact `gtin` match first,
        falling back to `manufacturer_id` + `order_code_1` only when no
        gtin is given. Returns None when nothing matches or more than one
        row does, since an ambiguous match is never claimed automatically."""
        ...

    async def get_multi(self, filters: BoughtItemFilterDto) -> tuple[int, list[BoughtItem]]: ...
    async def save(self, item: BoughtItem) -> BoughtItem: ...
    async def delete(self, item: BoughtItem) -> None: ...
    async def merge_catalogue_references(self, source_id: int, target_id: int) -> None:
        """Points the made items and successor links that name the source at
        the target. Other modules' references move through IBoughtItemUsages."""
        ...

    async def merge_article_groups(self, source_id: int, target_id: int) -> None: ...
