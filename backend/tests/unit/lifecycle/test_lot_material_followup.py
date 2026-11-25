"""
The material follow-up's scans and the reconciler's lock step for it. The
scan finds a lot whose first position changed kind, or is MIXED and had a
line touched, and says who brings its material and how much of ours it
needs. The lock step locks a lot's live raw material demand and the lines it
is allocated on with the use case's locks when the touched rows reach the
lot's first position, and leaves them out when the lock order forbids it.
What the follow-up writes is covered end to end in
tests/integration/test_api_external_first_step_material.py.
"""

from dataclasses import dataclass

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import FollowUpTouches
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_material_followup import (
    first_position_changes,
)
from src.modules.fulfillment.application.services.lot_material_followup import material_lock_demands
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lot_material_rules import MaterialSupply
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import FakeWorld

_A = LifecycleAggregate


@dataclass
class _Lot:
    """A lot of two positions, made from a source item, with a live raw
    material demand allocated on a supplier line of the material."""

    lot: ProductionLot
    first: int
    second: int
    demand: int
    material_line: int


def _lot(world: FakeWorld, *, status: LotStatus = LotStatus.PLANNED, **values: object) -> _Lot:
    material_line = world.line(world.order(), status=OrderItemStatus.ORDERED, quantity=10.0)
    demand = world.source_demand(status=SourceItemDemandStatus.ORDERED)
    world.allocate_source(demand, material_line, 10.0)
    lot = world.lot(
        status=status,
        source_item_id=4,
        input_demand_id=demand.id,
        demand_status=SourceItemDemandStatus.ORDERED,
        **values,
    )
    demand.lot_id = lot.id
    first = world.position(lot)
    second = world.position(lot)
    return _Lot(lot, first.id, second.id, demand.id, material_line.id)


def _kind_change(position_id: int, new: LotPositionKind) -> FieldChange:
    return FieldChange(
        aggregate=_A.LOT_POSITIONS,
        id=position_id,
        field=LifecycleField.KIND,
        old="unassigned",
        new=new.value,
        rule="test",
        value=new,
    )


def _changes(world: FakeWorld, *changes: FieldChange, lines: tuple[int, ...] = ()):
    snapshot = world.snapshot()
    return first_position_changes(
        changes,
        snapshot,
        derive_snapshot(snapshot),
        AggregateIds.of({_A.ORDER_ITEMS: lines}),
    )


class TestFirstPositionChanges:
    def test_nothing_changed_finds_nothing(self) -> None:
        world = FakeWorld()
        _lot(world)

        assert _changes(world) == []

    def test_a_supplier_line_on_the_first_position_brings_the_material(self) -> None:
        world = FakeWorld()
        lot = _lot(world)
        line = world.line(world.order(), quantity=10.0, position=world.positions[lot.first])

        [found] = _changes(
            world, _kind_change(lot.first, LotPositionKind.EXTERNAL), lines=(line.id,)
        )

        assert (found.lot.id, found.supply, found.need) == (
            lot.lot.id,
            MaterialSupply.SUPPLIER,
            0.0,
        )

    def test_a_later_position_changing_hands_does_not_count(self) -> None:
        world = FakeWorld()
        lot = _lot(world)
        world.line(world.order(), quantity=10.0, position=world.positions[lot.second])

        assert _changes(world, _kind_change(lot.second, LotPositionKind.EXTERNAL)) == []

    def test_a_mixed_first_position_with_a_touched_line_needs_the_in_house_share(self) -> None:
        world = FakeWorld()
        lot = _lot(world)
        position = world.positions[lot.first]
        world.production_order(position, quantity=6.0)
        line = world.line(world.order(), quantity=4.0, position=position)

        [found] = _changes(world, lines=(line.id,))

        assert (found.supply, found.need) == (MaterialSupply.SHARED, 6.0)

    def test_an_ended_lot_and_a_lot_without_a_material_source_are_left_alone(self) -> None:
        world = FakeWorld()
        ended = _lot(world, status=LotStatus.COMPLETED)
        unsourced = _lot(world)
        unsourced.lot.source_item_id = None

        assert (
            _changes(
                world,
                _kind_change(ended.first, LotPositionKind.EXTERNAL),
                _kind_change(unsourced.first, LotPositionKind.EXTERNAL),
            )
            == []
        )


class _LockOnly:
    """A material follow-up that only names its locks."""

    def lock_demands(self, snapshot: LifecycleSnapshot, touched: AggregateIds) -> frozenset[int]:
        return material_lock_demands(snapshot, touched)

    async def apply(self, *args: object, **kwargs: object) -> FollowUpTouches:
        return FollowUpTouches()


def _reconciler(world: FakeWorld) -> LifecycleReconciler:
    return LifecycleReconciler(world.repositories, FakeEventBus(), material_followup=_LockOnly())


class TestMaterialLocks:
    async def test_a_line_of_the_first_position_locks_the_demand_and_its_lines(self) -> None:
        world = FakeWorld()
        lot = _lot(world)
        line = world.line(world.order(), position=world.positions[lot.first])
        reconciler = _reconciler(world)
        reconciler.touch_order_items([line.id])

        await reconciler.lock_touched()

        assert lot.demand in world.locked(_A.SOURCE_DEMANDS)
        assert lot.material_line in world.locked(_A.ORDER_ITEMS)

    async def test_a_line_of_a_later_position_locks_no_material(self) -> None:
        world = FakeWorld()
        lot = _lot(world)
        line = world.line(world.order(), position=world.positions[lot.second])
        reconciler = _reconciler(world)
        reconciler.touch_order_items([line.id])

        await reconciler.lock_touched()

        assert world.locked(_A.SOURCE_DEMANDS) == set()
        assert lot.material_line not in world.locked(_A.ORDER_ITEMS)

    async def test_an_ended_demand_locks_nothing(self) -> None:
        world = FakeWorld()
        lot = _lot(world)
        lot.lot.demand_status = SourceItemDemandStatus.FULFILLED
        line = world.line(world.order(), position=world.positions[lot.first])
        reconciler = _reconciler(world)
        reconciler.touch_order_items([line.id])

        await reconciler.lock_touched()

        assert world.locked(_A.SOURCE_DEMANDS) == set()

    async def test_locks_the_order_forbids_are_left_for_the_follow_up(self) -> None:
        """The use case holds the first position's line and what it widens
        to already, and that line sorts after the material's line, so the
        lock step leaves the demand and its line out instead of refusing
        the use case."""
        world = FakeWorld()
        lot = _lot(world)
        line = world.line(world.order(), position=world.positions[lot.first])
        reconciler = _reconciler(world)
        await reconciler.lock_plan.acquire(
            AggregateIds.of(
                {_A.LOTS: [lot.lot.id], _A.ORDERS: [line.order_id], _A.ORDER_ITEMS: [line.id]}
            )
        )
        reconciler.touch_order_items([line.id])

        await reconciler.lock_touched()

        assert world.locked(_A.SOURCE_DEMANDS) == set()
        assert lot.material_line not in world.locked(_A.ORDER_ITEMS)
