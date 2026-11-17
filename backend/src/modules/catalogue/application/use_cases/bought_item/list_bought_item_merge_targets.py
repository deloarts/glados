"""
Lists the catalogue items a bought item could be merged into, each with the
merge rule's verdict, so the merge dialog shows a refused target disabled
with its reason instead of repeating the rule on the client.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemMergeTargetResult
from src.modules.catalogue.application.use_cases.bought_item.get_bought_item import GetBoughtItems
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.policies.catalogue_item_status import merge_target_verdict
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User


class ListBoughtItemMergeTargets:
    def __init__(
        self,
        bought_item_repo: IBoughtItemRepository,
        cad_source: ICadSource,
    ) -> None:
        self._items = bought_item_repo
        self._list = GetBoughtItems(bought_item_repo, cad_source)

    async def execute(
        self, actor: User, source_id: int, search: str | None, limit: int
    ) -> list[BoughtItemMergeTargetResult]:
        """The catalogue search's first `limit` matches, archived ones
        included, without the source itself."""
        found_or_raise(
            await self._items.get_by_id(source_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{source_id} not found.",
        )
        page = await self._list.execute(
            BoughtItemFilterDto(limit=limit, search=search or None, include_archived=True),
            actor=actor,
        )
        targets = []
        for item in page.items:
            if item.id == source_id:
                continue
            verdict = merge_target_verdict(
                archived=item.archived,
                status=BoughtItemCatalogueStatus(item.status),
                successor_item_id=item.successor_item_id,
                source_id=source_id,
            )
            targets.append(
                BoughtItemMergeTargetResult(
                    item=item,
                    refusal=verdict.refusal.value if verdict.refusal else None,
                    reactivates=verdict.reactivates,
                )
            )
        return targets
