"""The schedule walk forecasts every position of external work, not only
the ones a later order of the lot reads: the last position of a lot, an
outsourced position nobody has given to a supplier yet, and the external
positions of a lot that has no production order at all. An outsourced
position without a supplier is dated for display only and moves no
internal order."""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from types import SimpleNamespace

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.auto_plan.fakes import FakeCalendarRepo
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakePoolRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.scheduling_service._helpers import MONDAY

# The walk plans no queued order before now, and the fixtures are dated in
# the week of MONDAY.
_BEFORE_THE_FIXTURES = datetime(2026, 7, 1, tzinfo=UTC)
_RESPONSE_TIME_DAYS = 1
_HARDENING_LEAD_DAYS = 4
_POOL_ID = 100


class _OrderItemRepo:
    """The order item lookups the chain walk reads: by position for a
    supplier line, by id for the raw material's line."""

    def __init__(self, items: list[OrderItem]) -> None:
        self.items = items

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        return next((i for i in self.items if i.lot_position_id == lot_position_id), None)

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[OrderItem]:
        return [i for i in self.items if i.lot_position_id in lot_position_ids]

    async def get_by_ids(self, ids: list[int]) -> list[OrderItem]:
        return [i for i in self.items if i.id in ids]


class _SourceDemandRepo(FakeEmptyRepo):
    """One raw-material demand, id 1, the one make_lot links."""

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        return [SimpleNamespace(id=1)] if 1 in ids else []


class _SourceAllocationRepo(FakeEmptyRepo):
    """The raw material of demand 1 comes on order item 99."""

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list:
        if 1 not in demand_item_ids:
            return []
        return [SimpleNamespace(demand_item_id=1, order_item_id=99)]


def _step(
    step_id: int,
    position_id: int,
    *,
    method_id: int,
    lead_days: int | None = None,
    outsourced: bool = False,
    requires_machine: bool = True,
    minutes_per_piece: float = 1.0,
) -> LotStep:
    return LotStep(
        id=step_id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        note=None,
        estimated_setup_minutes=0,
        estimated_minutes_per_piece=minutes_per_piece,
        sequence=step_id,
        creator_id=1,
        fabrication_method_id=method_id,
        lot_id=1,
        position_id=position_id,
        source_process_id=None,
        fabrication_method_requires_machine=requires_machine,
        fabrication_method_required_external=outsourced,
        fabrication_method_lead_time_days=lead_days,
    )


def _position(
    position_id: int,
    sequence: int,
    kind: LotPositionKind,
    steps: list[LotStep],
    status: LotPositionStatus = LotPositionStatus.ORDERED_OR_QUEUED,
) -> LotPosition:
    return LotPosition(
        id=position_id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=status,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=steps,
    )


def _milling() -> LotPosition:
    """Position 1, milled in house on the pool."""
    return _position(10, 1, LotPositionKind.INTERNAL, [_step(10, 10, method_id=1)])


def _hardening(kind: LotPositionKind, sequence: int = 2) -> LotPosition:
    """Position 2, hardened outside: an EXTERNAL position with a supplier
    line, or an UNASSIGNED one nobody has given to a supplier yet."""
    status = (
        LotPositionStatus.PENDING
        if kind == LotPositionKind.UNASSIGNED
        else LotPositionStatus.ORDERED_OR_QUEUED
    )
    return _position(
        20,
        sequence,
        kind,
        [_step(20, 20, method_id=3, lead_days=_HARDENING_LEAD_DAYS, outsourced=True)],
        status=status,
    )


def _inspection() -> LotPosition:
    """Position 3, the manual QA check after the hardening."""
    return _position(
        30, 3, LotPositionKind.INTERNAL, [_step(30, 30, method_id=2, requires_machine=False)]
    )


def _order(order_id: int, position_id: int, **overrides: object) -> ProductionOrder:
    values: dict[str, object] = dict(
        id=order_id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{order_id:04d}",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=200,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=None,
        machine_pool_id=None,
        lot_position_id=position_id,
        lot_id=1,
    )
    values.update(overrides)
    return ProductionOrder(**values)  # type: ignore[arg-type]


def _milling_order() -> ProductionOrder:
    # not_before=MONDAY places the milling at 08:00 on MONDAY, and its 200
    # minutes end the same day, independent of the real clock.
    return _order(1, 10, machine_pool_id=_POOL_ID, not_before=MONDAY)


def _inspection_order() -> ProductionOrder:
    return _order(3, 30, estimated_duration_minutes=20)


def _order_item(item_id: int, **overrides: object) -> OrderItem:
    values: dict[str, object] = dict(
        id=item_id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        status=OrderItemStatus.ORDERED,
        quantity=10.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.MADE,
        lot_position_id=None,
        source_item_id=None,
    )
    values.update(overrides)
    return OrderItem(**values)  # type: ignore[arg-type]


def _hardening_line() -> OrderItem:
    """The supplier line of the EXTERNAL hardening position, no date typed."""
    return _order_item(1, lot_position_id=20)


def _recompute(
    lot: ProductionLot,
    orders: list[ProductionOrder],
    order_items: list[OrderItem],
    *,
    with_raw_material: bool = False,
) -> tuple[RecomputeMachineSchedule, FakeOrderRepo]:
    order_repo = FakeOrderRepo(orders)
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepo([lot]),  # type: ignore[arg-type]
        order_items=_OrderItemRepo(order_items),  # type: ignore[arg-type]
        source_item_demands=(  # type: ignore[arg-type]
            _SourceDemandRepo() if with_raw_material else FakeEmptyRepo()
        ),
        source_item_allocations=(  # type: ignore[arg-type]
            _SourceAllocationRepo() if with_raw_material else FakeEmptyRepo()
        ),
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=_RESPONSE_TIME_DAYS,
            require_qa=False,
        ),
        # The fixtures' dates are UTC days, so the tenant is in UTC too.
        default_timezone="UTC",
    )
    recompute = RecomputeMachineSchedule(
        repos,
        FakeMachineRepo([make_machine(1)]),
        FakeCalendarRepo(),
        settings_repo,
        FakePoolRepo([make_pool(_POOL_ID, machine_ids=[1])]),
        uow=FakeUnitOfWork(),  # type: ignore[arg-type]
    )
    return recompute, order_repo


def _lot(*positions: LotPosition) -> ProductionLot:
    lot = make_lot(1)
    lot.positions = list(positions)
    return lot


# The milling ends on MONDAY, so the hardening can be picked up the next
# day, after the response-time buffer, and is back after its lead days.
_EXPECTED_PICKUP = MONDAY + timedelta(days=_RESPONSE_TIME_DAYS)
_EXPECTED_DELIVERY = _EXPECTED_PICKUP + timedelta(days=_HARDENING_LEAD_DAYS)


async def test_an_external_position_that_ends_the_lot_is_forecast(monkeypatch):
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.EXTERNAL)
    recompute, _orders = _recompute(
        _lot(_milling(), hardening), [_milling_order()], [_hardening_line()]
    )

    await recompute.execute_all()

    assert hardening.planned_pickup_date == _EXPECTED_PICKUP
    assert hardening.planned_delivery_date == _EXPECTED_DELIVERY


async def test_an_outsourced_position_without_a_supplier_that_ends_the_lot_is_forecast(
    monkeypatch,
):
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.UNASSIGNED)
    recompute, _orders = _recompute(_lot(_milling(), hardening), [_milling_order()], [])

    await recompute.execute_all()

    assert hardening.planned_pickup_date == _EXPECTED_PICKUP
    assert hardening.planned_delivery_date == _EXPECTED_DELIVERY


async def test_an_unassigned_position_of_a_method_done_in_house_gets_no_forecast(monkeypatch):
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    deburring = _position(
        20, 2, LotPositionKind.UNASSIGNED, [_step(20, 20, method_id=3, lead_days=4)]
    )
    recompute, _orders = _recompute(_lot(_milling(), deburring), [_milling_order()], [])

    await recompute.execute_all()

    assert deburring.planned_pickup_date is None
    assert deburring.planned_delivery_date is None


async def test_an_outsourced_position_without_a_supplier_moves_no_internal_order(monkeypatch):
    """Milling, hardening without a supplier, QA. The hardening gets its
    forecast, but the QA order still waits on an undated predecessor, just
    as it did before the hardening was forecast at all."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.UNASSIGNED)
    recompute, orders = _recompute(
        _lot(_milling(), hardening, _inspection()),
        [_milling_order(), _inspection_order()],
        [],
    )

    await recompute.execute_all()

    assert hardening.planned_pickup_date == _EXPECTED_PICKUP
    assert hardening.planned_delivery_date == _EXPECTED_DELIVERY
    qa_order = orders.orders[3]
    assert qa_order.planned_start is None
    assert qa_order.planned_end is None


async def test_an_external_position_before_an_internal_one_keeps_its_forecast(monkeypatch):
    """The case the walk already dated: the lot's own chain agrees with it,
    and the QA order starts after the forecast delivery."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.EXTERNAL)
    recompute, orders = _recompute(
        _lot(_milling(), hardening, _inspection()),
        [_milling_order(), _inspection_order()],
        [_hardening_line()],
    )

    await recompute.execute_all()

    assert hardening.planned_pickup_date == _EXPECTED_PICKUP
    assert hardening.planned_delivery_date == _EXPECTED_DELIVERY
    # Delivery is Saturday, the buffer makes it Sunday, so the QA order
    # starts on the next working day.
    assert _EXPECTED_DELIVERY.weekday() == 5
    qa_order = orders.orders[3]
    assert qa_order.planned_start == datetime.combine(
        _EXPECTED_DELIVERY + timedelta(days=2), time(8), tzinfo=UTC
    )


async def test_a_lot_of_external_work_only_is_forecast_without_any_production_order(
    monkeypatch,
):
    """No order to walk at all: the hardening is the lot's first position,
    so its pickup follows the raw material's expected delivery."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.EXTERNAL, sequence=1)
    raw_material_line = _order_item(
        99, expected_delivery_date=MONDAY, line_type=OrderLineType.SOURCE
    )
    recompute, _orders = _recompute(
        _lot(hardening), [], [_hardening_line(), raw_material_line], with_raw_material=True
    )

    await recompute.execute_all()

    assert hardening.planned_pickup_date == _EXPECTED_PICKUP
    assert hardening.planned_delivery_date == _EXPECTED_DELIVERY


async def test_a_completed_external_position_is_left_alone(monkeypatch):
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.EXTERNAL)
    hardening.status = LotPositionStatus.COMPLETED
    recompute, _orders = _recompute(
        _lot(_milling(), hardening), [_milling_order()], [_hardening_line()]
    )

    await recompute.execute_all()

    assert hardening.planned_pickup_date is None
    assert hardening.planned_delivery_date is None


async def test_the_recompute_writes_the_latest_pickup_from_the_lot_target_date(monkeypatch):
    """Target the 20th, 2 days margin (the default), QA one day: the
    hardening has to be back on the 17th and leaves 4 days before."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.EXTERNAL)
    lot = _lot(_milling(), hardening, _inspection())
    lot.required_delivery_date = date(2026, 8, 20)
    recompute, _orders = _recompute(
        lot, [_milling_order(), _inspection_order()], [_hardening_line()]
    )

    await recompute.execute_all()

    assert hardening.latest_pickup_date == date(2026, 8, 13)
    assert hardening.planned_pickup_date == _EXPECTED_PICKUP


async def test_a_lot_without_a_target_date_gets_no_latest_pickup(monkeypatch):
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    hardening = _hardening(LotPositionKind.EXTERNAL)
    recompute, _orders = _recompute(
        _lot(_milling(), hardening), [_milling_order()], [_hardening_line()]
    )

    await recompute.execute_all()

    assert hardening.latest_pickup_date is None
