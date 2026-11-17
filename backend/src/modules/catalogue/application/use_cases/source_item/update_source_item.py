"""
Updates a source item's metadata (type, dimension, material, etc.),
validating uniqueness of the dimension/type/material combination. Status and
successor are checked together (src/modules/catalogue/domain/policies/catalogue_item_status.py),
and a status change publishes SourceItemStatusChanged.
"""

from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.dto.source_item_dto import UpdateSourceItemCommand
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.application.services.catalogue_successor import resolve_successor
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    assert_valid_item_tolerances,
)
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    keep_unsent_tolerances,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.errors import SourceItemDuplicateSpecError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemTypeNotFoundError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.events.source_item_events import SourceItemStatusChanged
from src.modules.catalogue.domain.policies.catalogue_item_status import CatalogueStatusChange
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.domain.services.dimension_spec import canonicalize_dimension
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    ISourceItemTypeRepository,
)
from src.modules.catalogue.ports.outbound.repositories.supplier_repository import (
    ISupplierRepository,
)
from src.modules.platform.application.services.command_changelog import diff_command
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class UpdateSourceItem:
    def __init__(
        self,
        source_item_repo: ISourceItemRepository,
        supplier_repo: ISupplierRepository,
        source_item_type_repo: ISourceItemTypeRepository,
        *,
        uow: IUnitOfWork,
        # None only for unit tests that predate the status event; the deps
        # factory always passes the transactional bus.
        event_bus: IEventBus | None = None,
    ) -> None:
        self._items = source_item_repo
        self._suppliers = supplier_repo
        self._types = source_item_type_repo
        self._uow = uow
        self._bus = event_bus

    async def execute(
        self, actor: User, item_id: int, cmd: UpdateSourceItemCommand
    ) -> SourceItemResult:
        SourceItemCatalogueRules.assert_can_update(actor)

        await self._items.lock_for_update(item_id)
        item = found_or_raise(
            await self._items.get_by_id(item_id),
            SourceItemNotFoundError,
            f"Source item #{item_id} not found.",
        )
        assert_edit_version(item, cmd.expected_edit_version, what=f"Source item #{item.id}")
        cmd = keep_unsent_tolerances(cmd, item)
        assert_valid_item_tolerances(cmd)

        if not await self._types.get_by_id(cmd.type_id):
            raise SourceItemTypeNotFoundError(f"Source item type #{cmd.type_id} not found.")

        if cmd.manufacturer_id is not None and not await self._suppliers.get_by_id(
            cmd.manufacturer_id
        ):
            raise SupplierNotFoundError(f"Supplier #{cmd.manufacturer_id} not found.")

        wanted_dimension = canonicalize_dimension(cmd.dimension)
        candidates = await self._items.get_by_spec_candidates(
            cmd.type_id, cmd.material, cmd.manufacturer_id
        )
        duplicate = next(
            (
                candidate
                for candidate in candidates
                if canonicalize_dimension(candidate.dimension) == wanted_dimension
            ),
            None,
        )
        if duplicate and duplicate.id != item.id:
            raise SourceItemDuplicateSpecError(
                f"A source item with this dimension/type/material"
                f"{'/manufacturer' if cmd.manufacturer_id is not None else ''}"
                f" combination already exists (#{duplicate.id})."
            )

        # From here on the command carries the successor the item keeps.
        cmd = cmd.model_copy(update={"successor_item_id": await self._resolve_successor(item, cmd)})

        old_status = item.status
        changelog_entry = diff_command(item, cmd)

        item.type_id = cmd.type_id
        item.dimension = cmd.dimension
        item.material = cmd.material
        item.mass = cmd.mass
        item.note = cmd.note
        item.order_code_1 = cmd.order_code_1
        item.order_code_2 = cmd.order_code_2
        item.status = SourceItemCatalogueStatus(cmd.status)
        item.manufacturer_id = cmd.manufacturer_id
        item.approver_id = cmd.approver_id
        item.successor_item_id = cmd.successor_item_id
        item.over_delivery_tolerance_percent = cmd.over_delivery_tolerance_percent
        item.under_delivery_tolerance_percent = cmd.under_delivery_tolerance_percent
        item.changed = now_utc()
        item.changes = append_changelog(item.changes, actor.full_name, changelog_entry)

        saved = await self._items.save(item)
        await self._publish_status_change(actor, old_status, saved)
        await self._uow.commit()
        log.info(f"Updated source item #{saved.id}.")
        return SourceItemMapper.to_result(saved)

    async def _resolve_successor(
        self, item: SourceItem, cmd: UpdateSourceItemCommand
    ) -> int | None:
        """The successor the item keeps, after the status rule accepted the
        write. Source items have no PDM file, so their status is always the
        caller's."""
        return await resolve_successor(
            CatalogueStatusChange(
                family="source item",
                item_id=item.id,
                old_status=item.status,
                old_successor_id=item.successor_item_id,
                new_status=SourceItemCatalogueStatus(cmd.status),
                requested_successor_id=cmd.successor_item_id,
            ),
            self._items.get_by_id,
        )

    async def _publish_status_change(self, actor: User, old_status: str, saved: SourceItem) -> None:
        if self._bus is None or saved.status == old_status:
            return
        await self._bus.publish(
            SourceItemStatusChanged(
                item_id=saved.id,
                old_status=SourceItemCatalogueStatus(old_status),
                new_status=SourceItemCatalogueStatus(saved.status),
                actor_id=actor.id,
            )
        )
