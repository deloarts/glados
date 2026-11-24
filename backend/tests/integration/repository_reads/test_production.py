"""
Read scenarios for production lots, production orders and the machines
they run on. See the package docstring for how the scenarios work.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_calendar_repository import (
    SqlAlchemyMachineCalendarRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_downtime_repository import (
    SqlAlchemyMachineDowntimeRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.machine_pool_repository import (
    SqlAlchemyMachinePoolRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.manufacturing_assessment_repository import (
    SqlAlchemyManufacturingAssessmentRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    SqlAlchemyProductionMachineRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_file_repository import (
    SqlAlchemyProductionOrderFileRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.entities.machine_calendar_exception import (
    MachineCalendarException,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.entities.machine_working_hours import MachineWorkingHours
from src.modules.fulfillment.domain.entities.manufacturing_assessment import ManufacturingAssessment
from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.fulfillment.ports.outbound.repositories.machine_downtime_repository import (
    MachineDowntimeFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    MachinePoolFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    ExternalWorkFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.platform.domain.entities.tenant_holiday import TenantHoliday
from src.modules.platform.domain.value_objects.holiday_category import HolidayCategory
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import TODAY
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import file_fields
from tests.integration.repository_reads._graph import make
from tests.integration.repository_reads._harness import Scenarios

SCENARIOS = Scenarios()


@SCENARIOS.register(SqlAlchemyProductionLotRepository)
async def _lots(g: Graph, r: Any) -> None:
    lot = await g.full_lot()
    internal = await g.internal_position()
    demand = await g.source_demand()
    await r.get_by_id(lot.id)
    await r.get_by_public_id(lot.public_id)
    await r.get_by_id_for_update(lot.id)
    await r.get_by_ids([lot.id])
    await r.get_ids_after(0, 10)
    await r.get_ids_with_external_work()
    await r.get_external_work_page(ExternalWorkFilterDto(today=TODAY))
    forced = await r.get_by_id(lot.id)
    forced.force_completed_at = datetime(2026, 2, 1, tzinfo=UTC)
    await r.save(forced)
    await r.get_force_completed_since(datetime(2026, 1, 1, tzinfo=UTC))
    forced.force_completed_at = None
    await r.save(forced)
    await r.get_multi(LotFilterDto())
    await r.maybe_empty.get_multi(LotFilterDto(todo_horizon=TODAY))
    await r.count_by_status()
    await r.get_by_project_id(lot.project_id)
    await r.get_events(lot.id)
    await r.get_position_by_id(internal.id)
    positions = await r.get_positions(lot.id)
    await r.get_positions_by_ids([p.id for p in positions])
    # Plain ids, no mapper: the graph puts no position on a quote request.
    await r.maybe_empty.get_quote_request_ids_of_positions([p.id for p in positions])
    await r.get_provisions(internal.id)
    steps = await r.get_steps(lot.id)
    await r.get_step_by_id(steps[0].id)
    await r.maybe_empty.get_raw_material_arrived_quantities([demand.id])
    await r.get_raw_material_arrived_quantity(demand.id)
    await r.next_lot_number("L-{seq}")


@SCENARIOS.register(SqlAlchemyProductionOrderRepository)
async def _production_orders(g: Graph, r: Any) -> None:
    await g.full_lot()
    order = await g.production_order()
    completion = await g.completion()
    machine_id = order.machine_id
    assert machine_id is not None
    await r.get_by_id(order.id)
    await r.get_by_id_for_update(order.id)
    await r.get_by_ids([order.id])
    await r.get_multi(ProductionOrderFilterDto())
    await r.get_all_non_terminal()
    await r.get_active_by_machine_ids([machine_id])
    await r.count_live_by_machine_ids([machine_id])
    await r.get_by_lot_position_id(order.lot_position_id)
    await r.get_by_lot_position_ids([order.lot_position_id])
    await r.get_by_machine_id(machine_id)
    await r.get_live_by_machine_ids([machine_id])
    await r.get_completion_by_id(completion.id)
    await r.get_completions(order.id)
    await r.next_production_order_number("PO-{seq}")
    await r.next_queue_sequence(machine_id)


@SCENARIOS.register(SqlAlchemyProductionOrderInterruptionRepository)
async def _interruptions(g: Graph, r: Any) -> None:
    interruption = await g.interruption()
    await r.get_by_order_ids([interruption.production_order_id])
    await r.sum_minutes_by_order_ids([interruption.production_order_id])


@SCENARIOS.register(SqlAlchemyProductionMachineRepository)
async def _machines(g: Graph, r: Any) -> None:
    machine = await g.machine()
    await g.machine_pool()
    await r.get_all()
    await r.get_by_id(machine.id)
    await r.get_by_ids([machine.id])
    await r.get_multi(ProductionMachineFilterDto())
    await r.get_list_order()
    await r.next_sort_order()


@SCENARIOS.register(SqlAlchemyMachinePoolRepository)
async def _pools(g: Graph, r: Any) -> None:
    pool = await g.machine_pool()
    await r.get_all()
    await r.get_by_id(pool.id)
    await r.get_by_ids([pool.id])
    await r.get_multi(MachinePoolFilterDto())
    await r.get_list_order()
    await r.next_sort_order()


@SCENARIOS.register(SqlAlchemyMachineCalendarRepository)
async def _calendar(g: Graph, r: Any) -> None:
    machine = await g.machine()
    exception = await SqlAlchemyMachineCalendarRepository(g.db).save_exception(
        make(
            MachineCalendarException, available_minutes=60, creator_id=g.uid, machine_id=machine.id
        )
    )
    await SqlAlchemyMachineCalendarRepository(g.db).save_working_hours(
        make(MachineWorkingHours, weekly_hours={0: 480}, creator_id=g.uid, machine_id=machine.id)
    )
    holiday = await SqlAlchemyMachineCalendarRepository(g.db).save_holiday(
        make(
            TenantHoliday,
            category=HolidayCategory.PUBLIC_HOLIDAY,
            start_date=TODAY,
            end_date=TODAY,
            creator_id=g.uid,
        )
    )
    await g.db.commit()
    await r.get_holidays()
    await r.get_holiday_by_id(holiday.id)
    await r.get_exception_by_id(exception.id)
    await r.get_exception_by_machine_and_date(machine.id, exception.exception_date)
    await r.get_exceptions_by_machine_id(machine.id)
    await r.get_exceptions_by_machine_ids([machine.id])
    await r.get_working_hours_by_machine_id(machine.id)
    await r.get_working_hours_by_machine_ids([machine.id])


@SCENARIOS.register(SqlAlchemyMachineDowntimeRepository)
async def _downtimes(g: Graph, r: Any) -> None:
    machine = await g.machine()
    repo = SqlAlchemyMachineDowntimeRepository(g.db)
    downtime = await repo.save(
        make(
            MachineDowntime,
            machine_id=machine.id,
            started_at=NOW - timedelta(hours=1),
            reason=MachineDowntimeReason.BREAKDOWN,
            reported_by_id=g.uid,
        )
    )
    await g.db.commit()
    start, end = NOW - timedelta(days=1), NOW + timedelta(days=1)
    await r.get_by_id(downtime.id)
    await r.get_for_update(downtime.id)
    await r.get_multi(MachineDowntimeFilterDto())
    await r.get_open_by_machine_ids([machine.id])
    await r.get_open_by_machine_ids([machine.id], started_by=NOW)
    await r.get_overlapping([machine.id], start, end)
    await r.minutes_by_machine_in_period([machine.id], start, end)


@SCENARIOS.register(SqlAlchemyManufacturingAssessmentRepository)
async def _assessments(g: Graph, r: Any) -> None:
    order = await g.production_order()
    await SqlAlchemyManufacturingAssessmentRepository(g.db).save(
        make(
            ManufacturingAssessment,
            production_order_id=order.id,
            operator_id=g.other_user.id,
            actual_minutes_per_piece=3,
            complexity=ComplexityClass.NORMAL,
        )
    )
    await g.db.commit()
    await r.get_by_production_order_id(order.id)


@SCENARIOS.register(SqlAlchemyProductionOrderFileRepository)
async def _production_order_files(g: Graph, r: Any) -> None:
    order = await g.production_order()
    category = next(iter(ProductionOrderFileCategory))
    file = await SqlAlchemyProductionOrderFileRepository(g.db).save(
        make(
            ProductionOrderFile,
            production_order_id=order.id,
            category=category,
            uploaded_by_user_id=g.uid,
            **file_fields("production-order"),
        )
    )
    await g.db.commit()
    await r.get_by_id(file.id)
    await r.get_by_item_id(order.id)
    await r.get_by_item_id_and_category(order.id, category)
    await r.get_by_item_ids([order.id])


@SCENARIOS.parametrize
async def test_read_methods_map_without_lazy_loads(repo_cls: type, db: AsyncSession) -> None:
    await SCENARIOS.run(repo_cls, db)
