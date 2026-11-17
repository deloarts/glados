"""
Properties of the lifecycle reconciler over random fake worlds whose stored
statuses, kinds and stamps may contradict their facts, every aggregate
reconciled: after a run every target stores its derivation, a second run
changes nothing, every change adds exactly one changelog line to its row,
and events come only from status changes.
"""

import asyncio
from collections import Counter
from enum import Enum

from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleLoader
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lifecycle_reconciler import ReconcileResult
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lifecycle.stored import demand_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_item_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import position_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import production_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import source_demand_changes
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

_A = LifecycleAggregate

_maybe_now = st.sampled_from([None, NOW])
_quantities = st.sampled_from([1.0, 2.5, 10.0])
_ENDED_PRODUCTION_ORDER = frozenset(
    {ProductionOrderStatus.COMPLETED.value, ProductionOrderStatus.CANCELED.value}
)


def _values[E: Enum](enum: type[E]) -> st.SearchStrategy[E]:
    return st.sampled_from(list(enum))


@st.composite
def _lots(draw: st.DrawFn, world: FakeWorld) -> None:
    for _ in range(draw(st.integers(0, 2))):
        quantity = draw(_quantities)
        lot = world.lot(
            quantity=quantity,
            status=draw(_values(LotStatus)),
            held_at=draw(_maybe_now),
            canceled_at=draw(_maybe_now),
            force_completed_at=draw(_maybe_now),
            completed_at=draw(_maybe_now),
        )
        for _ in range(draw(st.integers(0, 3))):
            position = world.position(
                lot,
                kind=draw(_values(LotPositionKind)),
                status=draw(_values(LotPositionStatus)),
                quantity_completed=draw(st.sampled_from([0.0, quantity])),
            )
            for _ in range(draw(st.integers(0, 2))):
                world.production_order(
                    position,
                    status=draw(_values(ProductionOrderStatus)),
                    quantity=draw(_quantities),
                    processed=draw(st.sampled_from([0.0, 1.0, 10.0])),
                    actual_start=draw(_maybe_now),
                    actual_end=draw(_maybe_now),
                    canceled_at=draw(_maybe_now),
                    open_interruption=draw(
                        st.sampled_from(
                            [None, InterruptionReason.MANUAL, InterruptionReason.LOT_HOLD]
                        )
                    ),
                )


@st.composite
def _orders(draw: st.DrawFn, world: FakeWorld) -> None:
    free_positions = sorted(world.positions)
    for _ in range(draw(st.integers(0, 2))):
        order = world.order(
            status=draw(_values(OrderStatus)),
            requested_at=draw(_maybe_now),
            ordered_date=draw(_maybe_now),
            canceled_at=draw(_maybe_now),
            delivery_date=draw(_maybe_now),
        )
        for _ in range(draw(st.integers(0, 3))):
            quantity = draw(_quantities)
            linked = draw(st.booleans()) and bool(free_positions)
            position = world.positions[free_positions.pop()] if linked else None
            world.line(
                order,
                status=draw(_values(OrderItemStatus)),
                quantity=quantity,
                delivered=draw(st.sampled_from([0.0, quantity / 2, quantity])),
                lost=draw(st.sampled_from([0.0, 1.0])),
                requested_at=draw(_maybe_now),
                ordered_date=draw(_maybe_now),
                canceled_at=draw(_maybe_now),
                position=position,
            )


@st.composite
def _demands(draw: st.DrawFn, world: FakeWorld) -> None:
    lines = sorted(world.order_items)
    lots = sorted(world.lots)
    for _ in range(draw(st.integers(0, 2))):
        bought = world.bought_demand(
            quantity=draw(_quantities),
            status=draw(_values(BoughtItemDemandStatus)),
            canceled_at=draw(_maybe_now),
            fulfilled_manually_at=draw(_maybe_now),
        )
        for line_id in (
            draw(st.lists(st.sampled_from(lines), max_size=2, unique=True)) if lines else []
        ):
            world.allocate_bought(bought, world.order_items[line_id], draw(_quantities))
        if draw(st.booleans()):
            world.allocate_bought(bought, None, draw(_quantities))
    for _ in range(draw(st.integers(0, 2))):
        made = world.made_demand(
            quantity=draw(_quantities), status=draw(_values(MadeItemDemandStatus))
        )
        for lot_id in (
            draw(st.lists(st.sampled_from(lots), max_size=2, unique=True)) if lots else []
        ):
            world.allocate_made(made, world.lots[lot_id], draw(_quantities))
    for _ in range(draw(st.integers(0, 1))):
        source = world.source_demand(
            quantity=draw(_quantities),
            status=draw(_values(SourceItemDemandStatus)),
            canceled_at=draw(_maybe_now),
        )
        for line_id in draw(st.lists(st.sampled_from(lines), max_size=1)) if lines else []:
            world.allocate_source(source, world.order_items[line_id], draw(_quantities))


_STORES = {
    _A.LOTS: "lots",
    _A.LOT_POSITIONS: "positions",
    _A.PRODUCTION_ORDERS: "production_orders",
    _A.ORDERS: "orders",
    _A.ORDER_ITEMS: "order_items",
    _A.BOUGHT_DEMANDS: "bought_demands",
    _A.MADE_DEMANDS: "made_demands",
    _A.SOURCE_DEMANDS: "source_demands",
}


@st.composite
def worlds(draw: st.DrawFn) -> tuple[FakeWorld, AggregateIds]:
    world = FakeWorld()
    draw(_lots(world))
    draw(_orders(world))
    draw(_demands(world))
    touched: dict[LifecycleAggregate, list[int]] = {}
    for aggregate, store in _STORES.items():
        ids = sorted(getattr(world, store))
        if ids:
            touched[aggregate] = draw(st.lists(st.sampled_from(ids), max_size=3, unique=True))
    return world, AggregateIds.of(touched)


def _reconciler(world: FakeWorld) -> tuple[LifecycleReconciler, FakeEventBus]:
    bus = FakeEventBus()
    return LifecycleReconciler(world.repositories, bus, aggregates=set(LifecycleAggregate)), bus


async def _run(world: FakeWorld, touched: AggregateIds) -> tuple[ReconcileResult, FakeEventBus]:
    reconciler, bus = _reconciler(world)
    for aggregate, ids in touched:
        if aggregate is _A.LOTS:
            reconciler.touch_lots(ids)
        elif aggregate is _A.LOT_POSITIONS:
            reconciler.touch_positions(ids)
        elif aggregate is _A.PRODUCTION_ORDERS:
            reconciler.touch_production_orders(ids)
        elif aggregate is _A.ORDERS:
            reconciler.touch_orders(ids)
        elif aggregate is _A.ORDER_ITEMS:
            reconciler.touch_order_items(ids)
        else:
            reconciler.touch_demands(aggregate, ids)
    return await reconciler.run(actor(), NOW), bus


async def _remaining_differences(world: FakeWorld, touched: AggregateIds) -> list[FieldChange]:
    """What a fresh comparison still finds on the targets of `touched`."""
    loader = LifecycleLoader(world.repositories, refresh=False)
    targets = await loader.widen(touched)
    snapshot = await loader.load_facts(targets)
    derived = derive_snapshot(snapshot)
    positions = snapshot.positions()
    found: list[FieldChange] = []
    for row_id in targets.get(_A.ORDER_ITEMS) & set(snapshot.order_items):
        found += order_item_changes(snapshot.order_items[row_id], derived.order_items[row_id])
    for row_id in targets.get(_A.PRODUCTION_ORDERS) & set(snapshot.production_orders):
        order = snapshot.production_orders[row_id]
        found += production_order_changes(order, derived.production_orders[row_id], now=NOW)
    for row_id in targets.get(_A.LOT_POSITIONS) & set(positions):
        found += position_changes(positions[row_id], derived.positions[row_id])
    for row_id in targets.get(_A.LOTS) & set(snapshot.lots):
        found += lot_changes(snapshot.lots[row_id], derived.lots[row_id], now=NOW)
    for row_id in targets.get(_A.ORDERS) & set(snapshot.orders):
        found += order_changes(snapshot.orders[row_id], derived.orders[row_id], now=NOW)
    for row_id in targets.get(_A.BOUGHT_DEMANDS) & set(snapshot.bought_demands):
        found += demand_changes(
            _A.BOUGHT_DEMANDS, snapshot.bought_demands[row_id], derived.bought_demands[row_id]
        )
    for row_id in targets.get(_A.MADE_DEMANDS) & set(snapshot.made_demands):
        found += demand_changes(
            _A.MADE_DEMANDS, snapshot.made_demands[row_id], derived.made_demands[row_id]
        )
    for row_id in targets.get(_A.SOURCE_DEMANDS) & set(snapshot.source_demands):
        found += source_demand_changes(
            snapshot.source_demands[row_id], derived.source_demands[row_id]
        )
    return found


def _changelog_lengths(world: FakeWorld) -> Counter[tuple[LifecycleAggregate, int]]:
    lengths: Counter[tuple[LifecycleAggregate, int]] = Counter()
    for aggregate, store in _STORES.items():
        for row_id, row in getattr(world, store).items():
            lengths[(aggregate, row_id)] = len(row.changes)
    return lengths


@settings(deadline=None)
@given(worlds())
def test_after_a_run_every_target_stores_its_derivation(
    case: tuple[FakeWorld, AggregateIds],
) -> None:
    world, touched = case
    asyncio.run(_run(world, touched))

    assert asyncio.run(_remaining_differences(world, touched)) == []


@settings(deadline=None)
@given(worlds())
def test_a_second_run_changes_nothing(case: tuple[FakeWorld, AggregateIds]) -> None:
    world, touched = case
    asyncio.run(_run(world, touched))
    saves = list(world.saves)

    result, bus = asyncio.run(_run(world, touched))

    assert result.changes == ()
    assert world.saves == saves
    assert bus.published == []


@settings(deadline=None)
@given(worlds())
def test_every_change_adds_one_changelog_line(case: tuple[FakeWorld, AggregateIds]) -> None:
    world, touched = case
    before = _changelog_lengths(world)

    result, _ = asyncio.run(_run(world, touched))

    after = _changelog_lengths(world)
    per_row = Counter((c.aggregate, c.id) for c in result.changes)
    assert {key: after[key] - before[key] for key in after if after[key] != before[key]} == dict(
        per_row
    )


@settings(deadline=None)
@given(worlds())
def test_events_come_only_from_status_changes(case: tuple[FakeWorld, AggregateIds]) -> None:
    world, touched = case

    result, bus = asyncio.run(_run(world, touched))

    status_changes = [c for c in result.changes if c.field is LifecycleField.STATUS]
    # A production order that ends announces how it ended besides the change,
    # and a lot that completes announces its completion.
    endings = [
        c
        for c in status_changes
        if (c.aggregate is _A.PRODUCTION_ORDERS and c.new in _ENDED_PRODUCTION_ORDER)
        or (c.aggregate is _A.LOTS and c.new == LotStatus.COMPLETED.value)
    ]
    assert len(bus.published) <= len(status_changes) + len(endings)
    assert len(world.lot_events) <= len(status_changes)
