"""
Row builders shared by the production lot repository tests. Each one writes
through the real repositories or ORM models, so the rows carry every column
the lot queries join on. The production order number and queue place
counters are module-global, so the orders that tests in different modules
build never collide on the unique production order number or the partial
unique index on live queue places.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.repositories.fabrication_method_repository import (
    SqlAlchemyFabricationMethodRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_repository import (
    SqlAlchemySourceItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.source_item_type_repository import (
    SqlAlchemySourceItemTypeRepository,
)
from src.modules.catalogue.domain.entities.fabrication_method import FabricationMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project

_order_number_seq = itertools.count(1)
# See test_production_order_repository.py's own _queue_sequence_seq for why
# this must be module-global: the partial unique index
# on live queue_sequence values would otherwise collide across tests that
# both build a machine-less (queue_sequence=1) order.
_queue_sequence_seq = itertools.count(1)


async def _make_order(
    db, creator_id: int, lot_position_id: int, *, machine_id: int | None = None
) -> ProductionOrder:
    saved = await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-TEST-{next(_order_number_seq)}",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=next(_queue_sequence_seq),
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=30,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine_id,
            lot_position_id=lot_position_id,
        )
    )
    await db.commit()
    return saved


async def _make_bare_lot(
    db, creator_id: int, lot_number: str, status: LotStatus, input_demand_id: int | None
) -> int:
    """A lot with no positions: actionable_for='source' is a purely
    lot-level predicate, so positions are irrelevant to it."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=lot_number)
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"Source target {lot_number}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot = await SqlAlchemyProductionLotRepository(db).save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=10.0,
            status=status,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=input_demand_id,
        )
    )
    return lot.id


async def _make_open_demand(
    db, creator_id: int, project_id: int, status: SourceItemDemandStatus
) -> int:
    source_item_type = await SqlAlchemySourceItemTypeRepository(db).save(
        SourceItemType(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": "Round bar"}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )
    source_item = await SqlAlchemySourceItemRepository(db).save(
        SourceItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            type_id=source_item_type.id,
            dimension="100 x 200 x 20",
            material="S235",
            mass=None,
            note=None,
            order_code_1=None,
            order_code_2=None,
            status=SourceItemCatalogueStatus.ACTIVE,
            creator_id=creator_id,
            approver_id=None,
            manufacturer_id=None,
            successor_item_id=None,
        )
    )
    await db.commit()
    demand = await SqlAlchemySourceItemDemandRepository(db).save(
        SourceItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=status,
            quantity=1.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            bought_item_id=None,
            source_item_id=source_item.id,
            lot_id=0,
            project_id=project_id,
        )
    )
    return demand.id


async def _make_fabrication_method(
    db, creator_id: int, name: str, *, requires_machine: bool = True
) -> FabricationMethod:
    return await SqlAlchemyFabricationMethodRepository(db).save(
        FabricationMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": name}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            requires_machine=requires_machine,
            creator_id=creator_id,
        )
    )


async def _make_lot_with_position(
    db, creator_id: int, lot_number: str, fabrication_method_ids: list[int]
) -> tuple[int, int]:
    """A DRAFT lot with a single UNASSIGNED position (quantity 10, nothing
    committed against it, so remaining=10>0) carrying one step per given
    fabrication method id. UNASSIGNED + remaining>0 is actionable-for-
    machines by construction (see _position_actionable_for_machines in
    _filters.py), so the coverable_by_* tests below only ever need to vary
    coverage, never actionability. Returns (lot_id, position_id)."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=lot_number)
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"Coverage target {lot_number}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=10.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    for sequence, method_id in enumerate(fabrication_method_ids, start=1):
        await lot_repo.save_step(
            LotStep(
                id=0,
                created=datetime.now(UTC),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=sequence,
                creator_id=creator_id,
                fabrication_method_id=method_id,
                lot_id=lot.id,
                position_id=position.id,
                source_process_id=None,
            )
        )
    return lot.id, position.id


async def _make_internal_position_with_order(
    db,
    creator_id: int,
    lot_number: str,
    fabrication_method_ids: list[int],
    *,
    machine_id: int | None = None,
) -> tuple[int, int]:
    """An already-committed INTERNAL position (quantity fully queued) with
    one ProductionOrder against it: the "already queued, does it still
    need a machine picked" shape _position_actionable_for_machines' second
    branch exists for. One step per given fabrication method id. Returns
    (lot_id, position_id)."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number=lot_number)
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"Coverage target {lot_number}",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=lot_number,
            quantity=10.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    for sequence, method_id in enumerate(fabrication_method_ids, start=1):
        await lot_repo.save_step(
            LotStep(
                id=0,
                created=datetime.now(UTC),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=sequence,
                creator_id=creator_id,
                fabrication_method_id=method_id,
                lot_id=lot.id,
                position_id=position.id,
                source_process_id=None,
            )
        )
    await _make_order(db, creator_id, position.id, machine_id=machine_id)
    return lot.id, position.id
