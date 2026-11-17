"""
Fetch a made item by ID or part number, with optional revision filtering.

`pdm_locked_fields` is resolved here and stamped onto the
mapped result rather than in MadeItemMapper itself: it needs the current PDM
settings and the requesting actor, neither of which a bare entity->DTO
mapping has, and every other MadeItemMapper.to_result() call site (create,
archive, restore, merge, revision, demand-matching, print-root resolution)
has no need to show it. See src.modules.catalogue.domain.policies.pdm_ownership.
pdm_locked_fields, computed the exact same way UpdateMadeItem's own
write-path enforcement is, so the two never disagree about which fields are
actually locked. `actor` is optional (default None, meaning "always empty
pdm_locked_fields") so the PAT surface and the changelog/thumbnail reads,
none of which need this, are unaffected.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import newest_of
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_locked_fields
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class PaginatedMadeItems:
    def __init__(self, total: int, items: list[MadeItemResult]):
        self.total = total
        self.items = items


class GetMadeItem:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        cad_source: ICadSource,
    ) -> None:
        self._items = made_item_repo
        self._cad = cad_source

    async def _to_result(self, item: MadeItem, actor: User | None) -> MadeItemResult:
        result = MadeItemMapper.to_result(item)
        result.pdm_locked_fields = pdm_locked_fields(
            kind="made",
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
        revision: str | None = None,
        actor: User | None = None,
    ) -> MadeItemResult:
        if part_number is not None:
            if revision is not None:
                item = await self._items.get_by_part_number_and_revision(part_number, revision)
                if not item:
                    raise MadeItemNotFoundError(
                        f"Catalogue item with part number '{part_number}' revision "
                        f"'{revision}' not found."
                    )
                return await self._to_result(item, actor)

            family = await self._items.get_revisions(part_number)
            if not family:
                raise MadeItemNotFoundError(
                    f"Catalogue item with part number '{part_number}' not found."
                )
            return await self._to_result(newest_of(family), actor)

        if item_id is None:
            raise ValueError("Either item_id or part_number must be provided.")

        item = found_or_raise(
            await self._items.get_by_id(item_id),
            MadeItemNotFoundError,
            f"Catalogue item #{item_id} not found.",
        )
        return await self._to_result(item, actor)


class GetMadeItems:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        cad_source: ICadSource,
    ) -> None:
        self._items = made_item_repo
        self._cad = cad_source

    async def execute(
        self, filters: MadeItemFilterDto, actor: User | None = None
    ) -> PaginatedMadeItems:
        total, items = await self._items.get_multi(filters)
        enforce = False
        if actor is not None:
            enforce = (await self._cad.policy()).enforces_ownership_for(actor)
        results = []
        for item in items:
            result = MadeItemMapper.to_result(item)
            result.pdm_locked_fields = pdm_locked_fields(
                kind="made", enforce=enforce, item_data_source=item.data_source
            )
            results.append(result)
        return PaginatedMadeItems(total=total, items=results)
