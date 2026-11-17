"""
Merges a source catalogue item into a target, then permanently deletes the
source (cascading its process steps). All FK reassignments and the delete
run in a single DB transaction. A PDM-owned (CAD) source row is refused
while ownership enforcement is active, see the execute() comment.
The target must be active and not archived, since the merge moves live work
onto it; a target the source had replaced is the exception and becomes
active again.
"""

from src.modules.catalogue.application.dto.made_item_dto import MadeItemResult
from src.modules.catalogue.application.dto.made_item_dto import MergeMadeItemCommand
from src.modules.catalogue.application.mappers.made_item_mapper import MadeItemMapper
from src.modules.catalogue.application.services.item_picture_merge import merge_item_pictures
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import PdmOwnedFieldReadOnlyError
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.catalogue_item_status import (
    assert_catalogue_status_change,
)
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.ports.outbound.cad_source_port import ICadSource
from src.modules.catalogue.ports.outbound.made_item_usage_port import IMadeItemUsages
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_file_repository import (
    IMadeItemFileRepository,
)
from src.modules.catalogue.ports.outbound.repositories.made_item_repository import (
    IMadeItemRepository,
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


class MergeMadeItem:
    def __init__(
        self,
        item_repo: IMadeItemRepository,
        file_repo: IMadeItemFileRepository,
        uow: IUnitOfWork,
        cad_source: ICadSource,
        *,
        part_number_registry: IPartNumberRegistry,
        picture_repo: IItemPictureRepository,
        item_usages: IMadeItemUsages,
    ) -> None:
        self._items = item_repo
        self._usages = item_usages
        self._files = file_repo
        self._pictures = picture_repo
        self._uow = uow
        self._cad = cad_source
        self._registry = part_number_registry

    async def execute(
        self, actor: User, source_id: int, cmd: MergeMadeItemCommand
    ) -> MadeItemResult:
        MadeItemCatalogueRules.assert_can_archive(actor)

        target_id = cmd.target_id

        if source_id == target_id:
            raise InvalidInputError("An item cannot be merged into itself.")

        source = found_or_raise(
            await self._items.get_by_id(source_id),
            MadeItemNotFoundError,
            f"Catalogue item #{source_id} not found.",
        )

        target = found_or_raise(
            await self._items.get_by_id(target_id),
            MadeItemNotFoundError,
            f"Catalogue item #{target_id} not found.",
        )
        # The merge moves live demands and order lines onto the target, so it
        # must take new work; one the source had replaced becomes active again.
        reactivate = MadeItemCatalogueRules.assert_merge_target(target, source)

        # PDM-owned field enforcement (docs/FIELD_OWNERSHIP.md principle 3):
        # merging away a CAD row would hard-delete the row ingest matches by
        # (vault_id, pdm_file_id), so it is refused outright while
        # enforcement is active; see update_made_item.py's matching
        # comment on `enforce`.
        enforce = (await self._cad.policy()).enforces_ownership_for(actor)
        if enforce and source.data_source == DataSource.CAD.value:
            raise PdmOwnedFieldReadOnlyError(
                f"Catalogue item #{source_id} is a PDM-owned (CAD) row and cannot be merged "
                "away while the PDM integration is enabled."
            )

        # The lots and demands of the source, the lots first as the lock
        # order has it, then its successor links, so the delete below leaves
        # nothing pointing at it.
        await self._usages.merge_lots_and_demands(source_id, target_id)
        await self._items.merge_references(source_id, target_id)

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
                await self._files.delete(existing)
                await self._files.reassign(src_file.id, target_id)
            else:
                await self._files.delete(src_file)

        await merge_item_pictures(self._pictures, ItemKind.MADE, source_id, target_id)

        # Append a merge note to the target's changelog.
        target.changed = now_utc()
        target.changed_by_id = actor.id
        target.changes = append_changelog(
            target.changes,
            actor.full_name,
            f"Merged from item #{source.id} ({source.article_name}, {source.part_number}).",
        )
        if reactivate:
            target.successor_item_id = assert_catalogue_status_change(
                CatalogueStatusChange(
                    family="made item",
                    item_id=target.id,
                    old_status=target.status,
                    old_successor_id=target.successor_item_id,
                    new_status=MadeItemCatalogueStatus.ACTIVE,
                    requested_successor_id=None,
                ),
                None,
            )
            target.status = MadeItemCatalogueStatus.ACTIVE
            target.changes = append_changelog(
                target.changes,
                actor.full_name,
                f"Status: replaced → active again, its successor #{source.id} was merged into it.",
            )
        await self._items.save(target)

        # Hard-delete the source (cascades its process steps), then commit everything.
        await self._items.delete(source)
        # Release the part number only if no row of either kind still
        # carries it: for a made item the family may live on in other
        # revisions, which release_if_unused checks for itself.
        if source.part_number is not None:
            await self._registry.release_if_unused(source.part_number)
        await self._uow.commit()

        log.info(
            f"Merged made-item catalogue item #{source_id} "
            f"({source.article_name!r}) into #{target_id} ({target.article_name!r})."
        )

        refreshed = found_or_raise(
            await self._items.get_by_id(target_id),
            MadeItemNotFoundError,
            f"Catalogue item #{target_id} not found after merge.",
        )
        return MadeItemMapper.to_result(refreshed)
