"""
The lots table column filters of SqlAlchemyProductionLotRepository.get_multi,
run against the throwaway SQLite database: lot number and quantity, the
resolved target date, the material source, and the step filters that must
all hold for one position. The ids filter of the live row sync is here too,
since it must return every requested row regardless of the default page
size.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.inspection_method_repository import (
    SqlAlchemyInspectionMethodRepository,
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
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.source_item_type import SourceItemType
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_delivery_model import (
    OrderItemDeliveryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
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
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration.production_lot_repository._helpers import _make_bare_lot
from tests.integration.production_lot_repository._helpers import _make_fabrication_method
from tests.integration.production_lot_repository._helpers import _make_internal_position_with_order
from tests.integration.production_lot_repository._helpers import _make_lot_with_position
from tests.integration.production_lot_repository._helpers import _make_open_demand


class TestGetMultiIdsFilterIgnoresPagingLimit:
    """LotFilterDto.ids is documented "live row-sync: refetch specific
    rows, ignore paging" (the frontend's useLiveRows refetches exactly the
    given ids with no skip/limit/order_by). get_multi runs every query
    through clamp_page, which defaults an omitted `limit` to
    DEFAULT_PAGE_SIZE, so it passes `len(filters.ids)` as clamp_page's
    `min_limit` and a caller passing more ids than that, with no explicit
    limit, still gets every row back. DEFAULT_PAGE_SIZE is monkeypatched
    down to prove this without seeding 100+ lots."""

    async def test_ids_past_the_default_page_size_are_not_truncated(
        self, db, create_user, monkeypatch
    ):
        # clamp_page resolves DEFAULT_PAGE_SIZE from pagination.py's own
        # module namespace at call time, so patch it there.
        monkeypatch.setattr(
            "src.modules.platform.adapters.outbound.persistence.pagination.DEFAULT_PAGE_SIZE", 2
        )
        user = await create_user()
        lot_ids = [
            await _make_bare_lot(db, user.id, f"LN-IDS-{i}", LotStatus.DRAFT, None)
            for i in range(4)
        ]

        repo = SqlAlchemyProductionLotRepository(db)
        total, lots = await repo.get_multi(LotFilterDto(ids=lot_ids))

        assert {lot.id for lot in lots} == set(lot_ids)
        assert total == 4

    async def test_explicit_limit_alongside_ids_is_still_honored(
        self, db, create_user, monkeypatch
    ):
        monkeypatch.setattr(
            "src.modules.platform.adapters.outbound.persistence.pagination.DEFAULT_PAGE_SIZE", 2
        )
        user = await create_user()
        lot_ids = [
            await _make_bare_lot(db, user.id, f"LN-IDS-LIM-{i}", LotStatus.DRAFT, None)
            for i in range(4)
        ]

        repo = SqlAlchemyProductionLotRepository(db)
        _, lots = await repo.get_multi(LotFilterDto(ids=lot_ids, limit=1))

        assert len(lots) == 1


_purchase_order_seq = itertools.count(1)


async def _lot_ids(db, **filters) -> set[int]:
    _, lots = await SqlAlchemyProductionLotRepository(db).get_multi(LotFilterDto(**filters))
    return {lot.id for lot in lots}


async def _update_lot(db, lot_id: int, **fields) -> None:
    """Writes the given lot fields through the repository so a test can set
    what the bare-lot helpers leave at their defaults (target date, source
    item links, quantity)."""
    repo = SqlAlchemyProductionLotRepository(db)
    lot = await repo.get_by_id(lot_id)
    assert lot is not None
    for name, value in fields.items():
        setattr(lot, name, value)
    await repo.save(lot)


async def _add_position(
    db,
    creator_id: int,
    lot_id: int,
    *,
    kind: LotPositionKind = LotPositionKind.UNASSIGNED,
    status: LotPositionStatus = LotPositionStatus.PENDING,
    planned_delivery_date: date | None = None,
) -> int:
    repo = SqlAlchemyProductionLotRepository(db)
    position = await repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=len(await repo.get_positions(lot_id)) + 1,
            kind=kind,
            status=status,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_id,
            planned_delivery_date=planned_delivery_date,
        )
    )
    return position.id


async def _add_step(
    db,
    creator_id: int,
    lot_id: int,
    position_id: int,
    *,
    fabrication_method_id: int | None = None,
    inspection_method_id: int | None = None,
    setup: int | None = None,
    per_piece: float | None = None,
    time_budget: float | None = None,
    note: str | None = None,
) -> int:
    repo = SqlAlchemyProductionLotRepository(db)
    role = StepRole.INSPECTION if inspection_method_id is not None else StepRole.FABRICATION
    step = await repo.save_step(
        LotStep(
            id=0,
            created=datetime.now(UTC),
            note=note,
            estimated_setup_minutes=setup,
            estimated_minutes_per_piece=per_piece,
            sequence=len(await repo.get_steps(lot_id)) + 1,
            creator_id=creator_id,
            fabrication_method_id=fabrication_method_id,
            lot_id=lot_id,
            position_id=position_id,
            source_process_id=None,
            role=role,
            inspection_method_id=inspection_method_id,
            time_budget_per_piece=time_budget,
        )
    )
    return step.id


async def _make_inspection_method(db, creator_id: int, name: str) -> InspectionMethod:
    saved = await SqlAlchemyInspectionMethodRepository(db).save(
        InspectionMethod(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            name=LocalizedText({"enGB": name}),
            label_color="#000000",
            label_font_color="#ffffff",
            description=LocalizedText(),
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _make_source_item(
    db, creator_id: int, *, type_name: str, dimension: str, material: str
) -> int:
    source_item_type = await SqlAlchemySourceItemTypeRepository(db).save(
        SourceItemType(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            name=LocalizedText({"enGB": type_name}),
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
            dimension=dimension,
            material=material,
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
    return source_item.id


async def _make_bought_item(db, creator_id: int, *, article_name: str, order_code_1: str) -> int:
    now = datetime.now(UTC)
    item = BoughtItemOrmModel(
        created=now,
        changed=now,
        changes=[],
        archived=False,
        order_code_1=order_code_1,
        status="active",
        article_name=article_name,
        data_source="WEB",
        creator_id=creator_id,
        manufacturer_id=await _make_supplier(db, creator_id, f"Maker of {article_name}"),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item.id


async def _make_made_item(
    db, creator_id: int, *, article_name: str, part_number: str | None
) -> int:
    seeded = (
        await SqlAlchemyMadeItemRepository(db).save(
            MadeItem(
                id=0,
                created=datetime.now(UTC),
                changed=datetime.now(UTC),
                changes=[],
                archived=False,
                revision="0",
                revision_date=None,
                revision_note=None,
                article_name=article_name,
                status=MadeItemCatalogueStatus.ACTIVE,
                data_source=DataSource.WEB,
                part_number=part_number,
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
    ).id
    await db.commit()
    return seeded


async def _make_supplier(db, creator_id: int, name: str) -> int:
    now = datetime.now(UTC)
    supplier = SupplierOrmModel(
        created=now,
        changed=now,
        changes=[],
        archived=False,
        name=name,
        level="B",
        creator_id=creator_id,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier.id


async def _make_purchase_order(
    db, creator_id: int, status: str = OrderStatus.ORDERED.value
) -> tuple[int, int]:
    """A supplier and one placed order of theirs, ordered or delivered.
    Returns (order_id, supplier_id)."""
    supplier_id = await _make_supplier(db, creator_id, f"Supplier {next(_purchase_order_seq)}")
    now = datetime.now(UTC)
    order = OrderOrmModel(
        order_number=f"PO-LOTS-{next(_purchase_order_seq)}",
        created=now,
        changes=[],
        status=status,
        ordered_date=now,
        delivery_date=now if status == OrderStatus.DELIVERED.value else None,
        creator_id=creator_id,
        supplier_id=supplier_id,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order.id, supplier_id


async def _make_order_item(
    db,
    creator_id: int,
    *,
    source_item_id: int | None = None,
    lot_position_id: int | None = None,
    status: str = OrderItemStatus.ORDERED.value,
    expected_delivery_date: date | None = None,
    delivery_date: datetime | None = None,
) -> int:
    """A SOURCE line (source_item_id) or a MADE line (lot_position_id) on a
    fresh purchase order, with the arrival dates the filters look at. A
    delivered line has its piece booked in a delivery row, and its order is
    delivered too."""
    delivered = status == OrderItemStatus.DELIVERED.value
    order_id, supplier_id = await _make_purchase_order(
        db,
        creator_id,
        OrderStatus.DELIVERED.value if delivered else OrderStatus.ORDERED.value,
    )
    now = datetime.now(UTC)
    item = OrderItemOrmModel(
        created=now,
        changes=[],
        status=status,
        quantity=1.0,
        quantity_delivered=1.0 if delivered else 0.0,
        ordered_date=now,
        unit="pcs",
        items_per_unit=1.0,
        creator_id=creator_id,
        order_id=order_id,
        supplier_id=supplier_id,
        project_id=(
            await SqlAlchemyProjectRepository(db).save(
                Project(
                    id=0,
                    created=now,
                    creator_id=creator_id,
                    project_number=f"P-OI-{next(_purchase_order_seq)}",
                )
            )
        ).id,
        line_type="SOURCE" if source_item_id is not None else "MADE",
        source_item_id=source_item_id,
        lot_position_id=lot_position_id,
        expected_delivery_date=expected_delivery_date,
        delivery_date=delivery_date,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    if delivered:
        db.add(
            OrderItemDeliveryOrmModel(
                created=now,
                order_item_id=item.id,
                quantity=1.0,
                delivery_date=delivery_date or now,
            )
        )
        await db.commit()
    return item.id


async def _make_source_demand(
    db,
    creator_id: int,
    project_id: int,
    source_item_id: int,
    status: SourceItemDemandStatus,
    lot_id: int,
) -> int:
    """Like _make_open_demand, but for an existing source item and an
    existing lot (the demand's lot_id is unique, so several demands in one
    test each need their own lot). Links the lot back to the demand."""
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
            source_item_id=source_item_id,
            lot_id=lot_id,
            project_id=project_id,
        )
    )
    await _update_lot(db, lot_id, input_demand_id=demand.id)
    return demand.id


async def _allocate_source_demand(db, demand_id: int, order_item_id: int) -> None:
    db.add(
        SourceItemAllocationOrmModel(
            demand_item_id=demand_id, order_item_id=order_item_id, source="order", quantity=1.0
        )
    )
    await db.commit()


async def _make_made_demand_for_lot(db, creator_id: int, lot_id: int, desired: date | None) -> int:
    """A made-item demand for the lot's own item, allocated to the lot, the
    fallback the resolved target date is computed from."""
    lot = await SqlAlchemyProductionLotRepository(db).get_by_id(lot_id)
    assert lot is not None
    demand = await SqlAlchemyMadeItemDemandItemRepository(db).save(
        MadeItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=MadeItemDemandStatus.ALLOCATED,
            quantity=1.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=desired,
            creator_id=creator_id,
            made_item_id=lot.made_item_id,
            project_id=lot.project_id,
        )
    )
    db.add(
        MadeItemAllocationOrmModel(
            demand_item_id=demand.id, lot_id=lot_id, source="lot", quantity=1.0
        )
    )
    await db.commit()
    return demand.id


async def _set_order_schedule(
    db,
    order: ProductionOrder,
    *,
    status: ProductionOrderStatus | None = None,
    planned_start: datetime | None = None,
    planned_end: datetime | None = None,
    actual_start: datetime | None = None,
    actual_end: datetime | None = None,
) -> None:
    if status is not None:
        order.status = status
    order.planned_start = planned_start
    order.planned_end = planned_end
    order.actual_start = actual_start
    order.actual_end = actual_end
    await SqlAlchemyProductionOrderRepository(db).save(order)
    await db.commit()


def _utc(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


class TestLotNumberAndQuantityFilters:
    async def test_lot_number_is_a_case_insensitive_substring_match(self, db, create_user):
        user = await create_user()
        hit = await _make_bare_lot(db, user.id, "LN-ABC-1", LotStatus.DRAFT, None)
        await _make_bare_lot(db, user.id, "LN-XYZ-2", LotStatus.DRAFT, None)

        assert await _lot_ids(db, lot_number="abc") == {hit}

    async def test_lot_number_treats_like_wildcards_literally(self, db, create_user):
        user = await create_user()
        literal = await _make_bare_lot(db, user.id, "LN_A", LotStatus.DRAFT, None)
        await _make_bare_lot(db, user.id, "LNXA", LotStatus.DRAFT, None)

        assert await _lot_ids(db, lot_number="LN_A") == {literal}

    async def test_quantity_bounds_are_inclusive(self, db, create_user):
        user = await create_user()
        low = await _make_bare_lot(db, user.id, "LN-Q-5", LotStatus.DRAFT, None)
        mid = await _make_bare_lot(db, user.id, "LN-Q-10", LotStatus.DRAFT, None)
        high = await _make_bare_lot(db, user.id, "LN-Q-15", LotStatus.DRAFT, None)
        await _update_lot(db, low, quantity=5.0)
        await _update_lot(db, high, quantity=15.0)

        assert await _lot_ids(db, quantity_min=10) == {mid, high}
        assert await _lot_ids(db, quantity_max=10) == {low, mid}
        assert await _lot_ids(db, quantity_min=5, quantity_max=15) == {low, mid, high}
        assert await _lot_ids(db, quantity_min=6, quantity_max=14) == {mid}


class TestItemFilters:
    async def test_part_number_and_article_name_filter_independently(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-ITEM-1", LotStatus.DRAFT, None)
        item_id = await _make_made_item(
            db, user.id, article_name="Mounting plate", part_number="PN-PLATE-12"
        )
        await _update_lot(db, lot_id, made_item_id=item_id)
        await _make_bare_lot(db, user.id, "LN-ITEM-OTHER", LotStatus.DRAFT, None)

        assert await _lot_ids(db, item_part_number="plate-12") == {lot_id}
        assert await _lot_ids(db, item_article_name="mounting") == {lot_id}
        assert await _lot_ids(db, item_part_number="pn-plate", item_article_name="mounting") == {
            lot_id
        }
        # The part number filter does not search the article name.
        assert await _lot_ids(db, item_part_number="mounting") == set()


class TestTargetDateFilter:
    """target_date_* filters the resolved target date the column shows: the
    lot's own required_delivery_date, else the earliest desired delivery
    date over its made-item demand allocations."""

    async def test_manual_required_delivery_date_wins_over_demand_dates(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-TD-MANUAL", LotStatus.DRAFT, None)
        await _update_lot(db, lot_id, required_delivery_date=date(2026, 10, 10))
        await _make_made_demand_for_lot(db, user.id, lot_id, date(2026, 9, 1))

        assert await _lot_ids(
            db, target_date_from=date(2026, 10, 10), target_date_to=date(2026, 10, 10)
        ) == {lot_id}
        assert (
            await _lot_ids(db, target_date_from=date(2026, 9, 1), target_date_to=date(2026, 9, 1))
            == set()
        )

    async def test_demand_fallback_uses_the_earliest_desired_date(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-TD-DEMAND", LotStatus.DRAFT, None)
        await _make_made_demand_for_lot(db, user.id, lot_id, date(2026, 9, 20))
        await _make_made_demand_for_lot(db, user.id, lot_id, date(2026, 9, 5))

        assert await _lot_ids(db, target_date_to=date(2026, 9, 5)) == {lot_id}
        assert (
            await _lot_ids(db, target_date_from=date(2026, 9, 10), target_date_to=date(2026, 9, 20))
            == set()
        )

    async def test_lot_with_neither_date_never_matches(self, db, create_user):
        user = await create_user()
        await _make_bare_lot(db, user.id, "LN-TD-NONE", LotStatus.DRAFT, None)
        dated = await _make_bare_lot(db, user.id, "LN-TD-DATED", LotStatus.DRAFT, None)
        await _update_lot(db, dated, required_delivery_date=date(2026, 9, 15))

        assert await _lot_ids(db, target_date_from=date(2000, 1, 1)) == {dated}


class TestSourceFilters:
    async def test_source_text_matches_bought_item_fields(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-B", LotStatus.DRAFT, None)
        bought_id = await _make_bought_item(
            db, user.id, article_name="Hex bolt M8", order_code_1="HB-M8"
        )
        await _update_lot(db, lot_id, source_bought_item_id=bought_id)
        await _make_bare_lot(db, user.id, "LN-SRC-B-OTHER", LotStatus.DRAFT, None)

        assert await _lot_ids(db, source_text="hex bolt") == {lot_id}
        assert await _lot_ids(db, source_text="hb-m8") == {lot_id}
        assert await _lot_ids(db, source_text="round bar") == set()

    async def test_source_text_matches_source_item_fields(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-S", LotStatus.DRAFT, None)
        source_id = await _make_source_item(
            db, user.id, type_name="Flat bar", dimension="40 x 8", material="1.4301"
        )
        await _update_lot(db, lot_id, source_item_id=source_id)
        await _make_bare_lot(db, user.id, "LN-SRC-S-OTHER", LotStatus.DRAFT, None)

        assert await _lot_ids(db, source_text="40 x 8") == {lot_id}
        assert await _lot_ids(db, source_text="1.4301") == {lot_id}
        assert await _lot_ids(db, source_text="flat bar") == {lot_id}
        assert await _lot_ids(db, source_text="round") == set()

    async def test_source_text_matches_source_made_item_fields(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-M", LotStatus.DRAFT, None)
        donor_id = await _make_made_item(
            db, user.id, article_name="Rework donor", part_number="PN-REWORK-7"
        )
        await _update_lot(db, lot_id, source_made_item_id=donor_id)
        await _make_bare_lot(db, user.id, "LN-SRC-M-OTHER", LotStatus.DRAFT, None)

        assert await _lot_ids(db, source_text="rework-7") == {lot_id}
        assert await _lot_ids(db, source_text="donor") == {lot_id}
        # The lot's own item is not the source; its article name must not match.
        assert await _lot_ids(db, source_text="Source target LN-SRC-M") == set()

    async def test_source_dimension_and_type_split_the_source_item_lines(self, db, create_user):
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-SRC-DT", LotStatus.DRAFT, None)
        source_id = await _make_source_item(
            db, user.id, type_name="Flat bar", dimension="40 x 8", material="1.4301"
        )
        await _update_lot(db, lot_id, source_item_id=source_id)
        await _make_bare_lot(db, user.id, "LN-SRC-DT-OTHER", LotStatus.DRAFT, None)

        assert await _lot_ids(db, source_dimension="40 x") == {lot_id}
        assert await _lot_ids(db, source_type="flat") == {lot_id}
        assert await _lot_ids(db, source_type="1.4301") == {lot_id}
        assert await _lot_ids(db, source_dimension="40 x", source_type="flat") == {lot_id}
        # Each field searches its own line only.
        assert await _lot_ids(db, source_dimension="flat") == set()
        assert await _lot_ids(db, source_type="40 x") == set()

    async def test_source_dimension_names_bought_and_made_sources(self, db, create_user):
        user = await create_user()
        bought_lot = await _make_bare_lot(db, user.id, "LN-SRC-DB", LotStatus.DRAFT, None)
        bought_id = await _make_bought_item(
            db, user.id, article_name="Hex bolt M8", order_code_1="HB-M8"
        )
        await _update_lot(db, bought_lot, source_bought_item_id=bought_id)
        made_lot = await _make_bare_lot(db, user.id, "LN-SRC-DM", LotStatus.DRAFT, None)
        donor_id = await _make_made_item(
            db, user.id, article_name="Rework donor", part_number="PN-REWORK-9"
        )
        await _update_lot(db, made_lot, source_made_item_id=donor_id)

        assert await _lot_ids(db, source_dimension="hb-m8") == {bought_lot}
        assert await _lot_ids(db, source_dimension="rework-9") == {made_lot}
        # Neither kind has a type line.
        assert await _lot_ids(db, source_type="bolt") == set()

    async def test_source_status_matches_the_linked_demand_status(
        self, db, create_user, allow_lifecycle_drift
    ):
        # The demand statuses are written by hand for the filter under test,
        # without the allocations they derive from.
        user = await create_user()
        project_id = (
            await SqlAlchemyProjectRepository(db).save(
                Project(
                    id=0, created=datetime.now(UTC), creator_id=user.id, project_number="P-SRC-ST"
                )
            )
        ).id
        allocated_demand = await _make_open_demand(
            db, user.id, project_id, SourceItemDemandStatus.ALLOCATED
        )
        allocated = await _make_bare_lot(
            db, user.id, "LN-SRC-ST-A", LotStatus.DRAFT, allocated_demand
        )
        await _make_bare_lot(db, user.id, "LN-SRC-ST-NONE", LotStatus.DRAFT, None)

        assert await _lot_ids(db, source_status=SourceItemDemandStatus.ALLOCATED.value) == {
            allocated
        }
        assert await _lot_ids(db, source_status=SourceItemDemandStatus.OPEN.value) == set()

    async def test_source_delivery_uses_delivery_date_over_expected_date(self, db, create_user):
        user = await create_user()
        project_id = (
            await SqlAlchemyProjectRepository(db).save(
                Project(
                    id=0, created=datetime.now(UTC), creator_id=user.id, project_number="P-SRC-DL"
                )
            )
        ).id
        source_id = await _make_source_item(
            db, user.id, type_name="Sheet", dimension="d", material="m"
        )

        expected_lot = await _make_bare_lot(db, user.id, "LN-SRC-DL-EXP", LotStatus.DRAFT, None)
        expected_demand = await _make_source_demand(
            db, user.id, project_id, source_id, SourceItemDemandStatus.ORDERED, expected_lot
        )
        await _allocate_source_demand(
            db,
            expected_demand,
            await _make_order_item(
                db, user.id, source_item_id=source_id, expected_delivery_date=date(2026, 9, 10)
            ),
        )

        delivered_lot = await _make_bare_lot(db, user.id, "LN-SRC-DL-DEL", LotStatus.DRAFT, None)
        delivered_demand = await _make_source_demand(
            db,
            user.id,
            project_id,
            source_id,
            SourceItemDemandStatus.FULFILLED,
            delivered_lot,
        )
        await _allocate_source_demand(
            db,
            delivered_demand,
            await _make_order_item(
                db,
                user.id,
                source_item_id=source_id,
                status=OrderItemStatus.DELIVERED.value,
                expected_delivery_date=date(2026, 9, 10),
                delivery_date=_utc(2026, 9, 12, 15),
            ),
        )
        await _make_bare_lot(db, user.id, "LN-SRC-DL-NONE", LotStatus.DRAFT, None)

        on_the_tenth = await _lot_ids(
            db, source_delivery_from=date(2026, 9, 10), source_delivery_to=date(2026, 9, 10)
        )
        on_the_twelfth = await _lot_ids(
            db, source_delivery_from=date(2026, 9, 12), source_delivery_to=date(2026, 9, 12)
        )
        assert on_the_tenth == {expected_lot}
        assert on_the_twelfth == {delivered_lot}
        assert await _lot_ids(db, source_delivery_from=date(2026, 9, 1)) == {
            expected_lot,
            delivered_lot,
        }


class TestStepFilters:
    """Every step filter describes ONE position: they are ANDed inside a
    single EXISTS over the lot's positions, and the lot matches as a whole."""

    async def test_step_filters_must_hold_for_the_same_position(self, db, create_user):
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        turning = await _make_fabrication_method(db, user.id, "Turning")
        lot_id = await _make_bare_lot(db, user.id, "LN-ST-SAME", LotStatus.PLANNED, None)
        pending_pos = await _add_position(db, user.id, lot_id)
        await _add_step(db, user.id, lot_id, pending_pos, fabrication_method_id=milling.id)
        queued_pos = await _add_position(
            db,
            user.id,
            lot_id,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
        )
        await _add_step(db, user.id, lot_id, queued_pos, fabrication_method_id=turning.id)

        assert await _lot_ids(db, step_fabrication_method_id=milling.id) == {lot_id}
        assert await _lot_ids(db, step_status="queued") == {lot_id}
        assert (
            await _lot_ids(db, step_fabrication_method_id=milling.id, step_status="queued") == set()
        )
        assert await _lot_ids(db, step_fabrication_method_id=turning.id, step_status="queued") == {
            lot_id
        }

    async def test_display_status_separates_pending_from_allocated(self, db, create_user):
        user = await create_user()
        pending_lot = await _make_bare_lot(db, user.id, "LN-ST-PEND", LotStatus.DRAFT, None)
        await _add_position(db, user.id, pending_lot)
        allocated_lot = await _make_bare_lot(db, user.id, "LN-ST-ALLOC", LotStatus.DRAFT, None)
        await _add_position(db, user.id, allocated_lot, kind=LotPositionKind.EXTERNAL)

        assert await _lot_ids(db, step_status="pending") == {pending_lot}
        assert await _lot_ids(db, step_status="allocated") == {allocated_lot}

    async def test_display_status_separates_ordered_queued_and_mixed(
        self, db, create_user, allow_lifecycle_drift
    ):
        # The position kinds and statuses are written by hand for the filter
        # under test, without the lines and orders they derive from.
        user = await create_user()
        queued_or_ordered = LotPositionStatus.ORDERED_OR_QUEUED
        queued_lot = await _make_bare_lot(db, user.id, "LN-ST-Q", LotStatus.PLANNED, None)
        await _add_position(
            db, user.id, queued_lot, kind=LotPositionKind.INTERNAL, status=queued_or_ordered
        )
        ordered_lot = await _make_bare_lot(db, user.id, "LN-ST-O", LotStatus.PLANNED, None)
        await _add_position(
            db, user.id, ordered_lot, kind=LotPositionKind.EXTERNAL, status=queued_or_ordered
        )
        mixed_lot = await _make_bare_lot(db, user.id, "LN-ST-MIX", LotStatus.PLANNED, None)
        await _add_position(
            db, user.id, mixed_lot, kind=LotPositionKind.MIXED, status=queued_or_ordered
        )
        completed_lot = await _make_bare_lot(db, user.id, "LN-ST-DONE", LotStatus.COMPLETED, None)
        await _add_position(
            db,
            user.id,
            completed_lot,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.COMPLETED,
        )

        assert await _lot_ids(db, step_status="queued") == {queued_lot}
        assert await _lot_ids(db, step_status="ordered") == {ordered_lot}
        assert await _lot_ids(db, step_status="ordered_or_queued") == {mixed_lot}
        assert await _lot_ids(db, step_status="completed") == {completed_lot}

    async def test_method_filters_match_fabrication_and_inspection_steps(self, db, create_user):
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        turning = await _make_fabrication_method(db, user.id, "Turning")
        visual = await _make_inspection_method(db, user.id, "Visual check")
        milled_lot, _ = await _make_lot_with_position(db, user.id, "LN-ST-MILL", [milling.id])
        inspected_lot = await _make_bare_lot(db, user.id, "LN-ST-INSP", LotStatus.DRAFT, None)
        inspected_pos = await _add_position(db, user.id, inspected_lot)
        await _add_step(db, user.id, inspected_lot, inspected_pos, fabrication_method_id=turning.id)
        await _add_step(db, user.id, inspected_lot, inspected_pos, inspection_method_id=visual.id)

        assert await _lot_ids(db, step_fabrication_method_id=milling.id) == {milled_lot}
        assert await _lot_ids(db, step_fabrication_method_id=turning.id) == {inspected_lot}
        assert await _lot_ids(db, step_inspection_method_id=visual.id) == {inspected_lot}

    async def test_setup_and_per_piece_compare_against_the_position_sum(self, db, create_user):
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        lot_id = await _make_bare_lot(db, user.id, "LN-ST-SUM", LotStatus.DRAFT, None)
        pos = await _add_position(db, user.id, lot_id)
        await _add_step(
            db, user.id, lot_id, pos, fabrication_method_id=milling.id, setup=10, per_piece=1.5
        )
        # No estimate of its own, so the time budget stands in for it.
        await _add_step(
            db, user.id, lot_id, pos, fabrication_method_id=milling.id, setup=20, time_budget=2.5
        )
        unestimated_lot, _ = await _make_lot_with_position(db, user.id, "LN-ST-NOSUM", [milling.id])

        assert await _lot_ids(db, step_setup_min=30, step_setup_max=30) == {lot_id}
        assert await _lot_ids(db, step_setup_max=29) == set()
        assert await _lot_ids(db, step_setup_min=31) == set()
        assert await _lot_ids(db, step_per_piece_min=4.0, step_per_piece_max=4.0) == {lot_id}
        assert await _lot_ids(db, step_per_piece_max=3.9) == set()
        assert unestimated_lot not in await _lot_ids(db, step_setup_min=0)

    async def test_planned_start_matches_any_live_order_start_day(self, db, create_user):
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        in_lot, in_pos = await _make_internal_position_with_order(
            db, user.id, "LN-PS-IN", [milling.id]
        )
        out_lot, out_pos = await _make_internal_position_with_order(
            db, user.id, "LN-PS-OUT", [milling.id]
        )
        orders = SqlAlchemyProductionOrderRepository(db)
        (in_order,) = await orders.get_by_lot_position_id(in_pos)
        (out_order,) = await orders.get_by_lot_position_id(out_pos)
        await _set_order_schedule(db, in_order, planned_start=_utc(2026, 9, 10, 8))
        await _set_order_schedule(db, out_order, planned_start=_utc(2026, 9, 20, 8))

        assert await _lot_ids(
            db, step_planned_start_from=date(2026, 9, 10), step_planned_start_to=date(2026, 9, 10)
        ) == {in_lot}
        assert await _lot_ids(db, step_planned_start_from=date(2026, 9, 11)) == {out_lot}

    async def test_planned_start_prefers_the_actual_start_and_skips_canceled_orders(
        self, db, create_user, allow_lifecycle_drift
    ):
        # The order statuses are written by hand for the filter under test.
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        started_lot, started_pos = await _make_internal_position_with_order(
            db, user.id, "LN-PS-ACT", [milling.id]
        )
        canceled_lot, canceled_pos = await _make_internal_position_with_order(
            db, user.id, "LN-PS-CAN", [milling.id]
        )
        orders = SqlAlchemyProductionOrderRepository(db)
        (started,) = await orders.get_by_lot_position_id(started_pos)
        (canceled,) = await orders.get_by_lot_position_id(canceled_pos)
        await _set_order_schedule(
            db,
            started,
            status=ProductionOrderStatus.IN_PROGRESS,
            planned_start=_utc(2026, 9, 10),
            actual_start=_utc(2026, 9, 11),
        )
        await _set_order_schedule(
            db,
            canceled,
            status=ProductionOrderStatus.CANCELED,
            planned_start=_utc(2026, 9, 10),
        )

        on_the_tenth = await _lot_ids(
            db, step_planned_start_from=date(2026, 9, 10), step_planned_start_to=date(2026, 9, 10)
        )
        on_the_eleventh = await _lot_ids(
            db, step_planned_start_from=date(2026, 9, 11), step_planned_start_to=date(2026, 9, 11)
        )
        assert on_the_tenth == set()
        assert on_the_eleventh == {started_lot}
        assert canceled_lot not in await _lot_ids(db, step_planned_start_from=date(2000, 1, 1))

    async def test_planned_end_matches_orders_order_items_and_position_forecast(
        self, db, create_user, allow_lifecycle_drift
    ):
        # The position kinds and statuses are written by hand for the filter
        # under test, without the lines and orders they derive from.
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        order_lot, order_pos = await _make_internal_position_with_order(
            db, user.id, "LN-PE-ORD", [milling.id]
        )
        (order,) = await SqlAlchemyProductionOrderRepository(db).get_by_lot_position_id(order_pos)
        await _set_order_schedule(db, order, planned_end=_utc(2026, 9, 10, 16))

        item_lot = await _make_bare_lot(db, user.id, "LN-PE-ITEM", LotStatus.PLANNED, None)
        item_pos = await _add_position(db, user.id, item_lot, kind=LotPositionKind.EXTERNAL)
        await _make_order_item(
            db, user.id, lot_position_id=item_pos, expected_delivery_date=date(2026, 9, 10)
        )

        forecast_lot = await _make_bare_lot(db, user.id, "LN-PE-FC", LotStatus.PLANNED, None)
        await _add_position(
            db,
            user.id,
            forecast_lot,
            kind=LotPositionKind.EXTERNAL,
            planned_delivery_date=date(2026, 9, 10),
        )

        out_lot = await _make_bare_lot(db, user.id, "LN-PE-OUT", LotStatus.PLANNED, None)
        out_pos = await _add_position(db, user.id, out_lot, kind=LotPositionKind.EXTERNAL)
        await _make_order_item(
            db, user.id, lot_position_id=out_pos, expected_delivery_date=date(2026, 9, 20)
        )

        assert await _lot_ids(
            db, step_planned_end_from=date(2026, 9, 10), step_planned_end_to=date(2026, 9, 10)
        ) == {order_lot, item_lot, forecast_lot}
        assert await _lot_ids(db, step_planned_end_from=date(2026, 9, 11)) == {out_lot}

    async def test_planned_end_ignores_position_forecast_once_an_order_item_is_linked(
        self, db, create_user, allow_lifecycle_drift
    ):
        # The position kinds and statuses are written by hand for the filter
        # under test, without the lines and orders they derive from.
        user = await create_user()
        lot_id = await _make_bare_lot(db, user.id, "LN-PE-SUPERSEDED", LotStatus.PLANNED, None)
        pos = await _add_position(
            db,
            user.id,
            lot_id,
            kind=LotPositionKind.EXTERNAL,
            planned_delivery_date=date(2026, 9, 10),
        )
        await _make_order_item(
            db, user.id, lot_position_id=pos, expected_delivery_date=date(2026, 9, 20)
        )

        assert (
            await _lot_ids(
                db, step_planned_end_from=date(2026, 9, 10), step_planned_end_to=date(2026, 9, 10)
            )
            == set()
        )
        assert await _lot_ids(
            db, step_planned_end_from=date(2026, 9, 20), step_planned_end_to=date(2026, 9, 20)
        ) == {lot_id}

    async def test_delivery_matches_final_dates_only(self, db, create_user, allow_lifecycle_drift):
        # The order statuses are written by hand for the filter under test.
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        done_lot, done_pos = await _make_internal_position_with_order(
            db, user.id, "LN-DL-DONE", [milling.id]
        )
        _planned_lot, planned_pos = await _make_internal_position_with_order(
            db, user.id, "LN-DL-PLAN", [milling.id]
        )
        orders = SqlAlchemyProductionOrderRepository(db)
        (done,) = await orders.get_by_lot_position_id(done_pos)
        (planned,) = await orders.get_by_lot_position_id(planned_pos)
        await _set_order_schedule(
            db,
            done,
            status=ProductionOrderStatus.COMPLETED,
            planned_end=_utc(2026, 9, 9),
            actual_end=_utc(2026, 9, 10, 17),
        )
        # Still queued: its planned end is a projection, not a delivery.
        await _set_order_schedule(db, planned, planned_end=_utc(2026, 9, 10))

        delivered_lot = await _make_bare_lot(db, user.id, "LN-DL-ITEM", LotStatus.PLANNED, None)
        delivered_pos = await _add_position(
            db, user.id, delivered_lot, kind=LotPositionKind.EXTERNAL
        )
        await _make_order_item(
            db,
            user.id,
            lot_position_id=delivered_pos,
            status=OrderItemStatus.DELIVERED.value,
            delivery_date=_utc(2026, 9, 10, 9),
        )
        ordered_lot = await _make_bare_lot(db, user.id, "LN-DL-ORDERED", LotStatus.PLANNED, None)
        ordered_pos = await _add_position(db, user.id, ordered_lot, kind=LotPositionKind.EXTERNAL)
        await _make_order_item(
            db, user.id, lot_position_id=ordered_pos, expected_delivery_date=date(2026, 9, 10)
        )

        assert await _lot_ids(
            db, step_delivery_from=date(2026, 9, 10), step_delivery_to=date(2026, 9, 10)
        ) == {done_lot, delivered_lot}
        assert await _lot_ids(db, step_delivery_from=date(2026, 9, 11)) == set()

    async def test_step_note_is_a_case_insensitive_substring_match(self, db, create_user):
        user = await create_user()
        milling = await _make_fabrication_method(db, user.id, "Milling")
        noted_lot = await _make_bare_lot(db, user.id, "LN-NOTE-HIT", LotStatus.DRAFT, None)
        noted_pos = await _add_position(db, user.id, noted_lot)
        await _add_step(
            db, user.id, noted_lot, noted_pos, fabrication_method_id=milling.id, note="Deburr edges"
        )
        await _make_lot_with_position(db, user.id, "LN-NOTE-MISS", [milling.id])

        assert await _lot_ids(db, step_note="deburr") == {noted_lot}
        assert await _lot_ids(db, step_note="polish") == set()
