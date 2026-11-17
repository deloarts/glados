"""
Application-level test for GetLots' new read-model fields: an internal
production order's earliest_start_reason/earliest_start_date (see
scheduling.explain_earliest_start), an external/mixed position's
lead_days/lead_days_source (resolve_position_lead_days_with_source), and a
lot's target_date/target_date_source/target_date_demand_item_id (see
_context.describe_lot_target_dates). All three are computed once per page
and threaded through LotMapper.to_summary, which proves the wiring end to
end, on top of the pure-domain coverage in
tests/unit/scheduling_service/test_earliest_start_explanation.py and the
resolve_lot_target_date coverage in tests/unit/test_resolve_lot_target_date.py.

Fakes are imported from tests/unit/auto_plan/, the same convention every
other scheduler application test already follows.
"""

from datetime import date

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLots
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo


class FakeAllocationRepo:
    """Backs made_item_allocations for the target-date fallback tests,
    the same shape as test_resolve_lot_target_date.py's own fake, kept
    local here so this file's fixtures don't depend on another test
    module's internals."""

    def __init__(self, allocations: list[MadeItemDemandAllocation]) -> None:
        self._allocations = allocations

    async def get_by_lot_id(self, lot_id: int) -> list[MadeItemDemandAllocation]:
        return [a for a in self._allocations if a.lot_id == lot_id]

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]


class FakeDemandRepo:
    def __init__(self, demands: list[MadeItemDemandItem]) -> None:
        self._demands = {d.id: d for d in demands}

    async def get_by_ids(self, ids: list[int]) -> list[MadeItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]


def make_demand(id: int, desired_delivery_date: date | None) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=MadeItemDemandStatus.ALLOCATED,
        quantity=10.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=desired_delivery_date,
        creator_id=1,
        made_item_id=1,
        project_id=1,
    )


NOT_BEFORE = date(2026, 8, 3)


class FakeLotRepoForGetLots(FakeLotRepo):
    """Adds the one method GetLots itself calls
    (IProductionLotRepository.get_multi) on top of FakeLotRepo's existing
    get_by_id/get_raw_material_arrived_quantity; no other test module
    needed it, so it wasn't part of the shared fake."""

    async def get_multi(self, filters: LotFilterDto) -> tuple[int, list[ProductionLot]]:
        lots = list(self.lots.values())
        return len(lots), lots


def _settings_repo() -> FakeSettingsRepo:
    return FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=2,
            response_time_days=1,
            require_qa=False,
        )
    )


def _lot_with_not_before_order() -> tuple[ProductionLot, ProductionOrder]:
    """A one-position INTERNAL lot (material already arrived, see
    make_lot's material_arrived default) whose single order carries an
    explicit not_before, the simplest case that isolates the "not_before"
    reason from predecessor/material readiness."""
    lot = make_lot(1)
    order = make_order(id=1, lot_id=1, not_before=NOT_BEFORE)
    lot.positions[0].production_orders = [order]
    return lot, order


def _external_position_lot() -> ProductionLot:
    """A one-position EXTERNAL lot with a single fabrication step carrying
    its own lead time. No supplier override is set, so
    resolve_position_lead_days_with_source reports "method" rather than
    "supplier" or "default"."""
    lot = make_lot(2)
    position = LotPosition(
        id=20,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.EXTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=2,
        steps=[
            LotStep(
                id=20,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=0.0,
                sequence=1,
                creator_id=1,
                fabrication_method_id=3,
                lot_id=2,
                position_id=20,
                source_process_id=None,
                fabrication_method_lead_time_days=5,
            )
        ],
    )
    lot.positions = [position]
    return lot


async def test_get_lots_fills_earliest_start_reason_and_date_for_an_internal_order():
    lot, order = _lot_with_not_before_order()
    lot_repo = FakeLotRepoForGetLots([lot])
    repos = SchedulingRepos(
        orders=FakeOrderRepo([order]),  # type: ignore[arg-type]
        lots=lot_repo,  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    use_case = GetLots(
        lot_repo=lot_repo,  # type: ignore[arg-type]
        repos=repos,
        machine_repo=FakeMachineRepo([]),  # type: ignore[arg-type]
        pool_repo=None,
        settings_repo=_settings_repo(),  # type: ignore[arg-type]
    )

    total, results = await use_case.execute(LotFilterDto())

    assert total == 1
    production_order = results[0].positions[0].production_orders[0]
    assert production_order.earliest_start_reason == "not_before"
    assert production_order.earliest_start_date == NOT_BEFORE


async def test_get_lots_fills_lead_days_for_an_external_position():
    lot = _external_position_lot()
    lot_repo = FakeLotRepoForGetLots([lot])
    repos = SchedulingRepos(
        orders=FakeOrderRepo([]),  # type: ignore[arg-type]
        lots=lot_repo,  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    use_case = GetLots(
        lot_repo=lot_repo,  # type: ignore[arg-type]
        repos=repos,
        machine_repo=FakeMachineRepo([]),  # type: ignore[arg-type]
        pool_repo=None,
        settings_repo=_settings_repo(),  # type: ignore[arg-type]
    )

    _total, results = await use_case.execute(LotFilterDto())

    position = results[0].positions[0]
    assert (position.lead_days, position.lead_days_source) == (5, "method")


async def test_get_lots_fills_target_date_from_the_manual_date_when_set():
    lot = make_lot(3, required_delivery_date=date(2026, 3, 1))
    lot_repo = FakeLotRepoForGetLots([lot])
    repos = SchedulingRepos(
        orders=FakeOrderRepo([]),  # type: ignore[arg-type]
        lots=lot_repo,  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    use_case = GetLots(
        lot_repo=lot_repo,  # type: ignore[arg-type]
        repos=repos,
        machine_repo=FakeMachineRepo([]),  # type: ignore[arg-type]
        pool_repo=None,
        settings_repo=_settings_repo(),  # type: ignore[arg-type]
    )

    _total, results = await use_case.execute(LotFilterDto())

    result = results[0]
    assert result.target_date == date(2026, 3, 1)
    assert result.target_date_source == "lot"
    assert result.target_date_demand_item_id is None


async def test_get_lots_fills_target_date_from_the_demand_derived_fallback():
    lot = make_lot(4, required_delivery_date=None)
    allocation = MadeItemDemandAllocation(demand_item_id=7, lot_id=4, quantity=10.0)
    demand = make_demand(7, desired_delivery_date=date(2026, 6, 1))
    lot_repo = FakeLotRepoForGetLots([lot])
    repos = SchedulingRepos(
        orders=FakeOrderRepo([]),  # type: ignore[arg-type]
        lots=lot_repo,  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeAllocationRepo([allocation]),  # type: ignore[arg-type]
        made_item_demands=FakeDemandRepo([demand]),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    use_case = GetLots(
        lot_repo=lot_repo,  # type: ignore[arg-type]
        repos=repos,
        machine_repo=FakeMachineRepo([]),  # type: ignore[arg-type]
        pool_repo=None,
        settings_repo=_settings_repo(),  # type: ignore[arg-type]
    )

    _total, results = await use_case.execute(LotFilterDto())

    result = results[0]
    assert result.target_date == date(2026, 6, 1)
    assert result.target_date_source == "demand"
    assert result.target_date_demand_item_id == 7


async def test_get_lots_leaves_target_date_none_without_a_manual_date_or_allocation():
    lot = make_lot(5, required_delivery_date=None)
    lot_repo = FakeLotRepoForGetLots([lot])
    repos = SchedulingRepos(
        orders=FakeOrderRepo([]),  # type: ignore[arg-type]
        lots=lot_repo,  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    use_case = GetLots(
        lot_repo=lot_repo,  # type: ignore[arg-type]
        repos=repos,
        machine_repo=FakeMachineRepo([]),  # type: ignore[arg-type]
        pool_repo=None,
        settings_repo=_settings_repo(),  # type: ignore[arg-type]
    )

    _total, results = await use_case.execute(LotFilterDto())

    result = results[0]
    assert result.target_date is None
    assert result.target_date_source is None
    assert result.target_date_demand_item_id is None
