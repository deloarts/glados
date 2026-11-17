"""
Merges a source catalogue item into a target, then permanently deletes the source.
All FK reassignments and the delete run in a single DB transaction. A PDM-owned
(CAD) source row is refused while ownership enforcement is active, see the
execute() comment.
The target must be active and not archived, since the merge moves live work
onto it; a target the source had replaced is the exception and becomes
active again.
"""

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.bought_item_dto import MergeBoughtItemCommand
from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.catalogue.application.services.item_picture_merge import merge_item_pictures
from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import PdmOwnedFieldReadOnlyError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.catalogue_item_status import (
    assert_catalogue_status_change,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.ports.outbound.bought_item_usage_port import IBoughtItemUsages
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.repositories.bought_item_file_repository import (
    IBoughtItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.bought_item_repository import (
    IBoughtItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.catalogue.ports.outbound.repositories.part_number_registry import (
    IPartNumberRegistry,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InvalidInputError
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class MergeBoughtItem:
    def __init__(
        self,
        item_repo: IBoughtItemRepository,
        file_repo: IBoughtItemFileRepository,
        uow: IUnitOfWork,
        cad_source: ICadSource,
        *,
        part_number_registry: IPartNumberRegistry,
        picture_repo: IItemPictureRepository,
        item_usages: IBoughtItemUsages,
    ) -> None:
        self._items = item_repo
        self._usages = item_usages
        self._files = file_repo
        self._pictures = picture_repo
        self._uow = uow
        self._cad = cad_source
        self._registry = part_number_registry

    async def execute(
        self, actor: User, source_id: int, cmd: MergeBoughtItemCommand
    ) -> BoughtItemResult:
        BoughtItemCatalogueRules.assert_can_archive(actor)

        target_id = cmd.target_id

        if source_id == target_id:
            raise InvalidInputError("An item cannot be merged into itself.")

        source = found_or_raise(
            await self._items.get_by_id(source_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{source_id} not found.",
        )

        target = found_or_raise(
            await self._items.get_by_id(target_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{target_id} not found.",
        )
        # The merge moves live demands and order lines onto the target, so it
        # must take new work; one the source had replaced becomes active again.
        reactivate = BoughtItemCatalogueRules.assert_merge_target(target, source)

        # PDM-owned field enforcement (docs/FIELD_OWNERSHIP.md principle 3):
        # see merge_made_item.py's matching comment.
        enforce = (await self._cad.policy()).enforces_ownership_for(actor)
        if enforce and source.data_source == DataSource.CAD.value:
            raise PdmOwnedFieldReadOnlyError(
                f"Catalogue item #{source_id} is a PDM-owned (CAD) row and cannot be merged "
                "away while the PDM integration is enabled."
            )

        # The lots, the order lines, the bought and then the raw material
        # demands, as the lifecycle lock order has it, so the merge waits
        # behind a delivery instead of deadlocking with it; then everything
        # else that names the item, so its delete leaves nothing behind.
        await self._usages.merge_lot_sources(source_id, target_id)
        await self._usages.merge_order_items(source_id, target_id)
        await self._usages.merge_demand_items(source_id, target_id)
        await self._usages.merge_source_demands(source_id, target_id)
        await self._usages.merge_substitutions(source_id, target_id)
        await self._usages.merge_references(source_id, target_id)
        await self._items.merge_catalogue_references(source_id, target_id)

        # Union article groups: source groups not already on target are added to target.
        await self._items.merge_article_groups(source_id, target_id)

        # File deduplication: identical content (same sha256) → keep the newer file.
        source_files = await self._files.get_by_item_id(source_id)
        target_files = await self._files.get_by_item_id(target_id)
        target_by_sha256 = {f.sha256: f for f in target_files}

        for src_file in source_files:
            existing = target_by_sha256.get(src_file.sha256)
            if existing is None:
                await self._files.reassign(src_file.id, target_id)
            elif src_file.created > existing.created:
                # Source file is newer: delete the target copy, reassign the source.
                await self._files.delete(existing)
                await self._files.reassign(src_file.id, target_id)
            else:
                # Source file is older or same age: discard it.
                await self._files.delete(src_file)

        await merge_item_pictures(self._pictures, ItemKind.BOUGHT, source_id, target_id)

        # Append a merge note to the target's changelog.
        target.changed = now_utc()
        target.changes = append_changelog(
            target.changes,
            actor.full_name,
            f"Merged from item #{source.id} ({source.article_name}, {source.order_code_1}).",
        )
        if reactivate:
            target.successor_item_id = assert_catalogue_status_change(
                CatalogueStatusChange(
                    family="bought item",
                    item_id=target.id,
                    old_status=target.status,
                    old_successor_id=target.successor_item_id,
                    new_status=BoughtItemCatalogueStatus.ACTIVE,
                    requested_successor_id=None,
                ),
                None,
            )
            target.status = BoughtItemCatalogueStatus.ACTIVE
            target.changes = append_changelog(
                target.changes,
                actor.full_name,
                f"Status: replaced → active again, its successor #{source.id} was merged into it.",
            )
        await self._items.save(target)

        # Hard-delete the source, then commit everything in one transaction.
        await self._items.delete(source)
        # Release the part number only if no row of either kind (bought
        # item or made item) still carries it.
        if source.part_number is not None:
            await self._registry.release_if_unused(source.part_number)
        await self._uow.commit()

        log.info(
            f"Merged catalogue item #{source_id} "
            f"({source.article_name!r}) into #{target_id} ({target.article_name!r})."
        )

        refreshed = found_or_raise(
            await self._items.get_by_id(target_id),
            BoughtItemNotFoundError,
            f"Catalogue item #{target_id} not found after merge.",
        )
        return BoughtItemMapper.to_result(refreshed)
