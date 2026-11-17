"""
Pins the SQL round-trip count of the scheduling path (walk inputs, board,
recompute and Auto-Plan) against the throwaway SQLite database. Every
seeded lot carries the full set of per-lot lookups the schedule walk
resolves (a linked raw-material demand with an order-item allocation, a
made-item demand allocation for the target date, an EXTERNAL position with
its order item, machine-assigned and pool-assigned orders), so a lookup or
write that is issued once per lot instead of once per walk shows up as a
count that grows with the number of lots.
"""

import itertools
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest
from sqlalchemy import update

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_calendar_repository import (
    SqlAlchemyMachineCalendarRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_downtime_repository import (
    SqlAlchemyMachineDowntimeRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.demand_item import (
    SqlAlchemyMadeItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule._walk_inputs import (
    build_schedule_walk_inputs,
)
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.application.use_cases.production_schedule.get_schedule_board import (
    GetScheduleBoard,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.domain.entities.user import User
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._demand_facts import give_demand_facts

_seq = itertools.count(1)

# Fixed round-trip budgets for the seeded schedule, the same for every
# lot count. A per-lot lookup creeping back in makes the larger
# parametrization exceed them.
_WALK_INPUT_STATEMENTS = 97
_BOARD_STATEMENTS = 128
_RECOMPUTE_STATEMENTS = 122
_AUTO_PLAN_STATEMENTS = 309


@pytest.fixture(autouse=True)
async def _seed_production_settings(db) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PON-{yy}-{seq:05d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
        )
    )
    await db.commit()


def _scheduling_repos(db) -> SchedulingRepos:
    return SchedulingRepos(
        orders=SqlAlchemyProductionOrderRepository(db),
        lots=SqlAlchemyProductionLotRepository(db),
        order_items=SqlAlchemyOrderItemRepository(db),
        source_item_demands=SqlAlchemySourceItemDemandRepository(db),
        source_item_allocations=SqlAlchemySourceItemAllocationRepository(db),
        made_item_allocations=SqlAlchemyMadeItemAllocationRepository(db),
        made_item_demands=SqlAlchemyMadeItemDemandItemRepository(db),
        settings=SqlAlchemyAdminSettingsRepository(db),
    )


def _recompute(db) -> RecomputeMachineSchedule:
    return RecomputeMachineSchedule(
        repos=_scheduling_repos(db),
        machine_repo=SqlAlchemyProductionMachineRepository(db),
        calendar_repo=SqlAlchemyMachineCalendarRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        pool_repo=SqlAlchemyMachinePoolRepository(db),
        downtime_repo=SqlAlchemyMachineDowntimeRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    )


def _auto_plan(db) -> AutoPlan:
    return AutoPlan(
        repos=_scheduling_repos(db),
        machine_repo=SqlAlchemyProductionMachineRepository(db),
        calendar_repo=SqlAlchemyMachineCalendarRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        recompute_schedule=_recompute(db),
        pool_repo=SqlAlchemyMachinePoolRepository(db),
        downtime_repo=SqlAlchemyMachineDowntimeRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    )


def _board(db) -> GetScheduleBoard:
    return GetScheduleBoard(
        repos=_scheduling_repos(db),
        machine_repo=SqlAlchemyProductionMachineRepository(db),
        calendar_repo=SqlAlchemyMachineCalendarRepository(db),
        settings_repo=SqlAlchemyAdminSettingsRepository(db),
        pool_repo=SqlAlchemyMachinePoolRepository(db),
        downtime_repo=SqlAlchemyMachineDowntimeRepository(db),
    )


async def _make_machine(db, creator_id: int) -> ProductionMachine:
    saved = await SqlAlchemyProductionMachineRepository(db).save(
        ProductionMachine(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            internal_name=f"QC-MACHINE-{next(_seq)}",
            vendor="Contoso",
            model="VF-2",
            fabrication_method_ids=[],
            max_part_dimension=None,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _make_pool(db, creator_id: int, machine_ids: list[int]) -> MachinePool:
    saved = await SqlAlchemyMachinePoolRepository(db).save(
        MachinePool(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            archived=False,
            name=f"QC-POOL-{next(_seq)}",
            machine_ids=machine_ids,
            note=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _make_made_item(db, creator_id: int) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name=f"Query count item {next(_seq)}",
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
    return seeded


async def _make_order_item(
    db,
    creator_id: int,
    *,
    project_id: int,
    lot_position_id: int | None,
    expected_delivery_date: date,
) -> int:
    now = datetime.now(UTC)
    supplier = SupplierOrmModel(
        created=now,
        changed=now,
        changes=[],
        archived=False,
        name=f"QC supplier {next(_seq)}",
        level="B",
        creator_id=creator_id,
    )
    db.add(supplier)
    await db.flush()
    order = OrderOrmModel(
        order_number=f"PO-QC-{next(_seq)}",
        created=now,
        changes=[],
        status="ordered",
        ordered_date=now,
        creator_id=creator_id,
        supplier_id=supplier.id,
    )
    db.add(order)
    await db.flush()
    item = OrderItemOrmModel(
        created=now,
        changes=[],
        status=OrderItemStatus.ORDERED.value,
        ordered_date=now,
        quantity=1.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        creator_id=creator_id,
        order_id=order.id,
        supplier_id=supplier.id,
        project_id=project_id,
        line_type="MADE" if lot_position_id is not None else "VIRTUAL",
        virtual_name=None if lot_position_id is not None else "Raw material",
        source_item_id=None,
        lot_position_id=lot_position_id,
        expected_delivery_date=expected_delivery_date,
        delivery_date=None,
    )
    db.add(item)
    await db.commit()
    return item.id


async def _make_position(
    db, creator_id: int, lot_id: int, sequence: int, kind: LotPositionKind
) -> LotPosition:
    saved = await SqlAlchemyProductionLotRepository(db).save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=sequence,
            kind=kind,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot_id,
        )
    )
    await db.commit()
    return saved


async def _make_order(
    db,
    creator_id: int,
    lot_position_id: int,
    *,
    machine_id: int | None = None,
    machine_pool_id: int | None = None,
) -> None:
    await SqlAlchemyProductionOrderRepository(db).save(
        ProductionOrder(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            production_order_number=f"PO-QC-ORDER-{next(_seq)}",
            status=ProductionOrderStatus.QUEUED,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=next(_seq),
            quantity=10.0,
            quantity_completed=0.0,
            estimated_duration_minutes=60,
            note=None,
            planned_start=None,
            planned_end=None,
            not_before=None,
            actual_start=None,
            actual_end=None,
            creator_id=creator_id,
            machine_id=machine_id,
            lot_position_id=lot_position_id,
            machine_pool_id=machine_pool_id,
        )
    )
    await db.commit()


async def _seed_lot(db, creator_id: int, project_id: int, machine_id: int, pool_id: int) -> None:
    """One lot with three positions: INTERNAL on a machine (gated by a
    linked raw-material demand), EXTERNAL with its own order item, and a
    pool-assigned INTERNAL position. The lot has no manual due date, so
    its target date comes from an allocated made-item demand."""
    made_item = await _make_made_item(db, creator_id)
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number=f"LN-QC-{next(_seq)}",
            quantity=10.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project_id,
            input_demand_id=None,
        )
    )

    source_demand = await SqlAlchemySourceItemDemandRepository(db).save(
        SourceItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=SourceItemDemandStatus.OPEN,
            quantity=10.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=creator_id,
            bought_item_id=None,
            source_item_id=None,
            lot_id=lot.id,
            project_id=project_id,
        )
    )
    await db.execute(
        update(ProductionLotOrmModel)
        .where(ProductionLotOrmModel.id == lot.id)
        .values(input_demand_id=source_demand.id)
    )
    material_order_item_id = await _make_order_item(
        db,
        creator_id,
        project_id=project_id,
        lot_position_id=None,
        expected_delivery_date=date(2026, 11, 2),
    )
    db.add(
        SourceItemAllocationOrmModel(
            demand_item_id=source_demand.id,
            order_item_id=material_order_item_id,
            source="order",
            quantity=10.0,
        )
    )

    made_demand = await SqlAlchemyMadeItemDemandItemRepository(db).save(
        MadeItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=MadeItemDemandStatus.ALLOCATED,
            quantity=10.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=date(2026, 12, 15),
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project_id,
        )
    )
    db.add(
        MadeItemAllocationOrmModel(
            demand_item_id=made_demand.id, lot_id=lot.id, source="lot", quantity=10.0
        )
    )
    await db.commit()

    first = await _make_position(db, creator_id, lot.id, 1, LotPositionKind.INTERNAL)
    second = await _make_position(db, creator_id, lot.id, 2, LotPositionKind.EXTERNAL)
    third = await _make_position(db, creator_id, lot.id, 3, LotPositionKind.INTERNAL)
    await _make_order_item(
        db,
        creator_id,
        project_id=project_id,
        lot_position_id=second.id,
        expected_delivery_date=date(2026, 11, 20),
    )
    await _make_order(db, creator_id, first.id, machine_id=machine_id)
    await _make_order(db, creator_id, third.id, machine_pool_id=pool_id)
    # Both demands take the status their allocations derive once the lot is
    # complete, as the allocation use cases would have stored it.
    await give_demand_facts(
        db, LifecycleAggregate.SOURCE_DEMANDS, source_demand.id, expected="ordered"
    )
    await give_demand_facts(db, LifecycleAggregate.MADE_DEMANDS, made_demand.id, expected="ordered")
    await db.commit()


async def _seed_schedule(db, create_user, lot_count: int) -> User:
    """`lot_count` lots spread over a fixed set of two machines and one
    pool, so only the number of lots varies between parametrized runs."""
    user = await create_user(
        username=f"qc-owner-{next(_seq)}",
        email=f"qc-owner-{next(_seq)}@example.com",
        permissions=["write:production_orders"],
    )
    project = await SqlAlchemyProjectRepository(db).save(
        Project(
            id=0,
            created=datetime.now(UTC),
            creator_id=user.id,
            project_number=f"P-QC-{next(_seq)}",
        )
    )
    machines = [await _make_machine(db, user.id) for _ in range(2)]
    pool = await _make_pool(db, user.id, [m.id for m in machines])
    for i in range(lot_count):
        await _seed_lot(db, user.id, project.id, machines[i % 2].id, pool.id)
    db.expunge_all()
    return user


async def _walk_input_statements(db, query_counter) -> int:
    repos = _scheduling_repos(db)
    settings = await SqlAlchemyAdminSettingsRepository(db).get_production()
    orders = await repos.orders.get_all_non_terminal()
    db.expunge_all()
    with query_counter() as statements:
        await build_schedule_walk_inputs(
            orders,
            repos,
            SqlAlchemyProductionMachineRepository(db),
            SqlAlchemyMachineCalendarRepository(db),
            SqlAlchemyMachinePoolRepository(db),
            settings,
            settings.response_time_days,
            downtime_repo=SqlAlchemyMachineDowntimeRepository(db),
            zone=UTC,
        )
    return len(statements)


async def _board_statements(db, query_counter) -> int:
    with query_counter() as statements:
        await _board(db).execute(date(2026, 10, 1), date(2026, 10, 31))
    return len(statements)


@pytest.mark.parametrize("lot_count", [2, 6])
async def test_walk_inputs_query_count_does_not_grow_with_lots(
    db, create_user, query_counter, lot_count
) -> None:
    """Building the walk inputs that RecomputeMachineSchedule and
    GetScheduleBoard share prefetches once per walk instead of issuing
    several queries per lot (lot, target date, raw material readiness and
    arrival, one context batch per machine)."""
    await _seed_schedule(db, create_user, lot_count)

    count = await _walk_input_statements(db, query_counter)

    assert count == _WALK_INPUT_STATEMENTS, count


@pytest.mark.parametrize("lot_count", [2, 6])
async def test_schedule_board_query_count_does_not_grow_with_lots(
    db, create_user, query_counter, lot_count
) -> None:
    await _seed_schedule(db, create_user, lot_count)

    count = await _board_statements(db, query_counter)

    assert count == _BOARD_STATEMENTS, count


async def _recompute_statements(db, query_counter) -> int:
    with query_counter() as statements:
        await _recompute(db).execute_all()
    return len(statements)


async def _auto_plan_statements(db, query_counter, actor: User) -> int:
    with query_counter() as statements:
        await _auto_plan(db).execute(actor, AutoPlanCommand(assign_machines=True))
    return len(statements)


@pytest.mark.parametrize("lot_count", [2, 6])
async def test_recompute_query_count_does_not_grow_with_lots(
    db, create_user, query_counter, lot_count
) -> None:
    """The recompute writes every walked order and every forecast position
    through one lean batch write each instead of a save and reload per
    row, so the whole recompute, writes included, costs the same number of
    round trips however many lots it walks."""
    await _seed_schedule(db, create_user, lot_count)

    count = await _recompute_statements(db, query_counter)

    assert count == _RECOMPUTE_STATEMENTS, count


@pytest.mark.parametrize("lot_count", [2, 6])
async def test_auto_plan_query_count_does_not_grow_with_lots(
    db, create_user, query_counter, lot_count
) -> None:
    """Auto-Plan loads every candidate machine's orders in one query, reuses
    one prefetch for the context build and the due-date pass, writes its
    placements in one batch and reads the moved orders back in one query,
    so neither its reads nor its writes grow per lot."""
    actor = await _seed_schedule(db, create_user, lot_count)

    count = await _auto_plan_statements(db, query_counter, actor)

    assert count == _AUTO_PLAN_STATEMENTS, count


async def test_recompute_writes_forecast_positions_in_one_batch(
    db, create_user, monkeypatch
) -> None:
    """The external forecast write-back hands every forecast position to
    one save_position_forecasts call instead of reading and
    saving each position on its own, and the dates land on the rows."""
    lot_count = 4
    await _seed_schedule(db, create_user, lot_count)

    async def _forbidden(self, *args: object) -> None:
        raise AssertionError("per-position read or save in the recompute write-back")

    forecast_calls: list[list[ExternalForecast]] = []
    original_write = SqlAlchemyProductionLotRepository.save_position_forecasts

    async def _spy_write(self, forecasts: list[ExternalForecast]) -> None:
        forecast_calls.append(list(forecasts))
        await original_write(self, forecasts)

    monkeypatch.setattr(SqlAlchemyProductionLotRepository, "get_position_by_id", _forbidden)
    monkeypatch.setattr(SqlAlchemyProductionLotRepository, "get_positions_by_ids", _forbidden)
    monkeypatch.setattr(SqlAlchemyProductionLotRepository, "save_position", _forbidden)
    monkeypatch.setattr(SqlAlchemyProductionLotRepository, "save_position_forecasts", _spy_write)

    await _recompute(db).execute_all()
    monkeypatch.undo()

    assert len(forecast_calls) == 1
    assert len(forecast_calls[0]) == lot_count
    db.expunge_all()
    persisted = {
        p.id: p
        for p in await SqlAlchemyProductionLotRepository(db).get_positions_by_ids(
            [f.position_id for f in forecast_calls[0]]
        )
    }
    for forecast in forecast_calls[0]:
        position = persisted[forecast.position_id]
        assert position.kind == LotPositionKind.EXTERNAL.value
        assert position.planned_pickup_date == forecast.planned_pickup_date
        assert position.planned_delivery_date == forecast.planned_delivery_date


async def test_batched_lookups_match_their_single_row_counterparts(db, create_user) -> None:
    """Every batch method the schedule walk relies on returns what its
    per-row counterpart returns, row for row."""
    await _seed_schedule(db, create_user, 3)
    repos = _scheduling_repos(db)
    lots = await repos.lots.get_by_ids(
        sorted({o.lot_id for o in await repos.orders.get_all_non_terminal()})
    )
    lot_ids = [lot.id for lot in lots]
    demand_ids = [lot.input_demand_id for lot in lots if lot.input_demand_id is not None]
    position_ids = [p.id for lot in lots for p in lot.positions]
    assert len(demand_ids) == 3

    arrived = await repos.lots.get_raw_material_arrived_quantities([*demand_ids, 999_999])
    for demand_id in demand_ids:
        assert arrived[demand_id] == await repos.lots.get_raw_material_arrived_quantity(demand_id)
    assert arrived[999_999] == 0.0

    batched_allocations = await repos.made_item_allocations.get_by_lot_ids(lot_ids)
    single_allocations = [
        a for lot_id in lot_ids for a in await repos.made_item_allocations.get_by_lot_id(lot_id)
    ]
    assert sorted(batched_allocations, key=lambda a: (a.lot_id, a.demand_item_id)) == sorted(
        single_allocations, key=lambda a: (a.lot_id, a.demand_item_id)
    )

    batched_positions = {p.id: p for p in await repos.lots.get_positions_by_ids(position_ids)}
    for position_id in position_ids:
        assert batched_positions[position_id] == await repos.lots.get_position_by_id(position_id)

    machine_repo = SqlAlchemyProductionMachineRepository(db)
    machines = await machine_repo.get_all()
    batched_machines = {m.id: m for m in await machine_repo.get_by_ids([m.id for m in machines])}
    for machine in machines:
        assert batched_machines[machine.id] == await machine_repo.get_by_id(machine.id)

    pool_repo = SqlAlchemyMachinePoolRepository(db)
    pools = await pool_repo.get_all()
    batched_pools = {p.id: p for p in await pool_repo.get_by_ids([p.id for p in pools])}
    for pool in pools:
        assert batched_pools[pool.id] == await pool_repo.get_by_id(pool.id)
