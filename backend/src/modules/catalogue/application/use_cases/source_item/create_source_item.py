"""
Creates a source item after checking that its source item type exists, its supplier (if given)
exists, and no other live source item already has the same spec.
"""

from src.modules.catalogue.application.dto.source_item_dto import CreateSourceItemCommand
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.mappers.source_item_mapper import SourceItemMapper
from src.modules.catalogue.application.services.item_delivery_tolerance import (
    assert_valid_item_tolerances,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.errors import SourceItemDuplicateSpecError
from src.modules.catalogue.domain.errors import SourceItemTypeNotFoundError
from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.domain.policies.catalogue_item_status import assert_new_item_status
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
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc


class CreateSourceItem:
    def __init__(
        self,
        source_item_repo: ISourceItemRepository,
        supplier_repo: ISupplierRepository,
        source_item_type_repo: ISourceItemTypeRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._items = source_item_repo
        self._suppliers = supplier_repo
        self._types = source_item_type_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: CreateSourceItemCommand) -> SourceItemResult:
        SourceItemCatalogueRules.assert_can_create(actor)
        assert_new_item_status(family="source item", status=SourceItemCatalogueStatus(cmd.status))
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
        if duplicate:
            raise SourceItemDuplicateSpecError(
                f"A source item with this dimension/type/material"
                f"{'/manufacturer' if cmd.manufacturer_id is not None else ''}"
                f" combination already exists (#{duplicate.id})."
            )

        now = now_utc()
        item = SourceItem(
            id=0,
            created=now,
            changed=now,
            changes=append_changelog([], actor.full_name, "Source item created."),
            archived=False,
            type_id=cmd.type_id,
            dimension=cmd.dimension,
            material=cmd.material,
            mass=cmd.mass,
            note=cmd.note,
            order_code_1=cmd.order_code_1,
            order_code_2=cmd.order_code_2,
            status=SourceItemCatalogueStatus(cmd.status),
            creator_id=actor.id,
            approver_id=None,
            manufacturer_id=cmd.manufacturer_id,
            successor_item_id=None,
            over_delivery_tolerance_percent=cmd.over_delivery_tolerance_percent,
            under_delivery_tolerance_percent=cmd.under_delivery_tolerance_percent,
            creator=actor,
        )

        saved = await self._items.save(item)
        await self._uow.commit()
        log.info(f"Created source item #{saved.id}.")
        return SourceItemMapper.to_result(saved)
