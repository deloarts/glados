"""
Lists the catalogue items a made item could be merged into, each with the
merge rule's verdict, so the merge dialog shows a refused target disabled
with its reason instead of repeating the rule on the client.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemMergeTargetResult
from src.modules.catalogue.application.use_cases.made_item.get_made_item import GetMadeItems
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.catalogue_item_status import merge_target_verdict
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class ListMadeItemMergeTargets:
    def __init__(
        self,
        made_item_repo: IMadeItemRepository,
        cad_source: ICadSource,
    ) -> None:
        self._items = made_item_repo
        self._list = GetMadeItems(made_item_repo, cad_source)

    async def execute(
        self, actor: User, source_id: int, search: str | None, limit: int
    ) -> list[MadeItemMergeTargetResult]:
        """The catalogue search's first `limit` matches, archived ones
        included, without the source itself."""
        found_or_raise(
            await self._items.get_by_id(source_id),
            MadeItemNotFoundError,
            f"Catalogue item #{source_id} not found.",
        )
        page = await self._list.execute(
            MadeItemFilterDto(limit=limit, search=search or None, include_archived=True),
            actor=actor,
        )
        targets = []
        for item in page.items:
            if item.id == source_id:
                continue
            verdict = merge_target_verdict(
                archived=item.archived,
                status=MadeItemCatalogueStatus(item.status),
                successor_item_id=item.successor_item_id,
                source_id=source_id,
            )
            targets.append(
                MadeItemMergeTargetResult(
                    item=item,
                    refusal=verdict.refusal.value if verdict.refusal else None,
                    reactivates=verdict.reactivates,
                )
            )
        return targets
