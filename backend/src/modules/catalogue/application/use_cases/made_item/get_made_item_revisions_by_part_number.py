"""
PAT-only counterpart to get_made_item_revisions.py's `GET
/{item_id}/revisions`: keyed by part_number instead of id, backing
`GET /pat/made-items/partnumber/{part_number}/revisions`. Same
newest-first ordering as the web endpoint, since two different orderings
for the same list would be a trap for API consumers. Shares
`_build_revisions_result` with the web use case so the
next_revision/can_create/reason logic never drifts between the two;
only the lookup key differs.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemRevisionsResult
from src.modules.catalogue.application.use_cases.made_item.get_made_item_revisions import (
    _build_revisions_result,
)
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.policies.made_item_rules import newest_of
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
)
from src.modules.platform.domain.entities.user import User


class GetMadeItemRevisionsByPartNumber:
    def __init__(
        self, made_item_repo: IMadeItemRepository, admin_settings_repo: ICatalogueSettingsRepository
    ) -> None:
        self._items = made_item_repo
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User, part_number: str) -> MadeItemRevisionsResult:
        siblings = await self._items.get_revisions(part_number)
        if not siblings:
            raise MadeItemNotFoundError(
                f"Catalogue item with part number {part_number!r} not found."
            )

        newest = newest_of(siblings)
        return await _build_revisions_result(
            siblings, newest, actor, self._admin_settings, reverse=True
        )
