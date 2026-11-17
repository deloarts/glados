"""
Retrieves one bought catalogue item by ID or part number, or lists items
with filtering and pagination.

`pdm_locked_fields` is resolved here and stamped onto the mapped result
rather than in BoughtItemMapper itself: it needs the current PDM settings
and the requesting actor, neither of which a bare entity->DTO mapping has;
see src.modules.catalogue.domain.policies.pdm_ownership.pdm_locked_fields, computed the
exact same way UpdateBoughtItem's own write-path enforcement is, so the
two never disagree about which fields are actually locked.
`actor` is optional (default None, meaning "always empty pdm_locked_fields")
so the PAT surface and other read-only callers, none of which need this,
are unaffected.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_locked_fields
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class PaginatedBoughtItems:
    def __init__(self, total: int, items: list[BoughtItemResult]):
        self.total = total
        self.items = items


class GetBoughtItem:
    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        cad_source: ICadSource,
    ) -> None:
        self._items = bought_item_repo
        self._cad = cad_source

    async def _to_result(self, item: BoughtItem, actor: User | None) -> BoughtItemResult:
        result = BoughtItemMapper.to_result(item)
        result.pdm_locked_fields = pdm_locked_fields(
            kind="bought",
            enforce=await self._enforce(actor),
            item_data_source=item.data_source,
        )
        return result

    async def _enforce(self, actor: User | None) -> bool:
        if actor is None:
            return False
        return (await self._cad.policy()).enforces_ownership_for(actor)

    async def execute(
        self,
        item_id: int | None = None,
        part_number: str | None = None,
        actor: User | None = None,
    ) -> BoughtItemResult:
        if part_number is not None:
            item = await self._items.get_by_part_number(part_number)
            if not item:
                raise BoughtItemNotFoundError(
                    f"Catalogue item with part number '{part_number}' not found."
                )
            return await self._to_result(item, actor)

        if item_id is None:
            raise ValueError("Either item_id or part_number must be provided.")

        item = found_or_raise(
            await self._items.get_by_id(item_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )
        return await self._to_result(item, actor)


class GetBoughtItems:
    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        cad_source: ICadSource,
    ) -> None:
        self._items = bought_item_repo
        self._cad = cad_source

    async def execute(
        self, filters: BoughtItemFilterDto, actor: User | None = None
    ) -> PaginatedBoughtItems:
        total, items = await self._items.get_multi(filters)
        enforce = False
        if actor is not None:
            enforce = (await self._cad.policy()).enforces_ownership_for(actor)
        results = []
        for item in items:
            result = BoughtItemMapper.to_result(item)
            result.pdm_locked_fields = pdm_locked_fields(
                kind="bought", enforce=enforce, item_data_source=item.data_source
            )
            results.append(result)
        return PaginatedBoughtItems(total=total, items=results)
