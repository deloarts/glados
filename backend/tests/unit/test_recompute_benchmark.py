"""
Wall-clock guard for RecomputeMachineSchedule.execute_all(): every
schedule-affecting mutation re-walks the ENTIRE schedule, not just one
machine's queue. This synthesizes a board large enough to
notice a quadratic regression: 20 machines x 50 queued orders, 5 pools x
50 floating orders (2-4 members each, some machines shared across pools).
It then times one execute_all() call over it.

Every order is backed by a 2-3 position lot with completed anchor orders
on its earlier positions (not an isolated single-position lot), so the
predecessor-chain resolution path (_context.resolve_predecessor_ready_at)
is exercised at scale too, the same shape a live multi-step lot has.

Deterministic (no randomness), so a timing regression here reproduces
exactly. Marked `benchmark` (registered in pyproject.toml's
[tool.pytest.ini_options] markers) so CI can deselect it from the regular
unit run.
"""

import itertools
import time
from collections.abc import Iterator
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.scheduling import ScheduleWalkResult
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.test_recompute_machine_schedule import build_recompute

_ANCHOR_START = datetime(2026, 1, 1, tzinfo=UTC)


def _make_position(
    position_id: int, lot_id: int, sequence: int, quantity_completed: float
) -> LotPosition:
    return LotPosition(
        id=position_id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=lot_id,
        steps=[
            LotStep(
                id=position_id,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=1.0,
                sequence=1,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=lot_id,
                position_id=position_id,
                source_process_id=None,
            )
        ],
    )


def _build_chain_lot(
    ids: Iterator[int],
    num_positions: int,
    machine_id: int | None,
    machine_pool_id: int | None,
    queue_sequence: int,
    duration_minutes: int,
) -> tuple[ProductionLot, list[ProductionOrder]]:
    """A `num_positions`-position (2 or 3) lot: every position before the
    last carries one COMPLETED anchor order with a real planned_end and a
    fully-consumed quantity_completed, so the last position's order (the
    one actually placed on the synthetic board) resolves a real,
    non-unknown predecessor chain and upstream_input_available, the same
    multi-position shape a live lot has, not an isolated single-position
    one. Returns (lot, [*anchor_orders, final_order])."""
    lot_id = next(ids)
    positions: list[LotPosition] = []
    anchor_orders: list[ProductionOrder] = []

    for sequence in range(1, num_positions):
        position_id = next(ids)
        anchor_order_id = next(ids)
        positions.append(_make_position(position_id, lot_id, sequence, quantity_completed=10.0))
        anchor = make_order(
            anchor_order_id,
            lot_id=position_id,  # make_order conflates lot_id/lot_position_id, fixed below
            duration_minutes=30,
            status=ProductionOrderStatus.COMPLETED,
            queue_sequence=1,
            planned_start=_ANCHOR_START,
            planned_end=_ANCHOR_START + timedelta(minutes=30),
        )
        anchor.lot_id = lot_id
        anchor_orders.append(anchor)

    final_position_id = next(ids)
    positions.append(
        _make_position(final_position_id, lot_id, num_positions, quantity_completed=0.0)
    )

    lot = ProductionLot(
        id=lot_id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number=f"LOT-{lot_id:06d}",
        quantity=10.0,
        status=LotStatus.PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
        required_delivery_date=None,
    )
    lot.positions = positions

    final_order_id = next(ids)
    final_order = make_order(
        final_order_id,
        lot_id=final_position_id,  # see anchor comment above
        duration_minutes=duration_minutes,
        machine_id=machine_id,
        machine_pool_id=machine_pool_id,
        queue_sequence=queue_sequence,
    )
    final_order.lot_id = lot_id

    return lot, [*anchor_orders, final_order]


def _assert_no_overlaps_per_machine(result: ScheduleWalkResult) -> None:
    """Sanity check: no two dated orders committed to the same physical
    machine, whether machine-assigned (by_machine) or a pool order that
    floated onto it (trial_machine_id), may overlap in time."""
    windows_by_machine: dict[int, list[tuple[datetime, datetime]]] = {}
    for machine_id, orders in result.by_machine.items():
        for o in orders:
            if o.planned_start is not None and o.planned_end is not None:
                windows_by_machine.setdefault(machine_id, []).append(
                    (o.planned_start, o.planned_end)
                )
    for pool_orders in result.by_pool.values():
        for o in pool_orders:
            if (
                o.trial_machine_id is not None
                and o.planned_start is not None
                and o.planned_end is not None
            ):
                windows_by_machine.setdefault(o.trial_machine_id, []).append(
                    (o.planned_start, o.planned_end)
                )

    for machine_id, windows in windows_by_machine.items():
        windows.sort()
        for (start1, end1), (start2, end2) in itertools.pairwise(windows):
            assert end1 <= start2, (
                f"overlap on machine {machine_id}: ({start1}, {end1}) vs ({start2}, {end2})"
            )


@pytest.mark.benchmark
async def test_global_recompute_benchmark_under_2_seconds():
    ids = itertools.count(1)
    machine_ids = list(range(1, 21))
    machines = [make_machine(i) for i in machine_ids]

    pool_members = {
        101: [1, 2],
        102: [2, 3, 4],
        103: [4, 5, 6, 7],
        104: [7, 8],
        105: [1, 9, 10],
    }
    pools = [make_pool(pool_id, machine_ids=members) for pool_id, members in pool_members.items()]

    lots: list[ProductionLot] = []
    orders: list[ProductionOrder] = []

    for machine_id in machine_ids:
        for seq in range(1, 51):
            num_positions = 2 if (machine_id + seq) % 2 == 0 else 3
            lot, chain_orders = _build_chain_lot(
                ids,
                num_positions,
                machine_id=machine_id,
                machine_pool_id=None,
                queue_sequence=seq,
                duration_minutes=60,
            )
            lots.append(lot)
            orders.extend(chain_orders)

    for pool_id in pool_members:
        for seq in range(1, 51):
            num_positions = 2 if (pool_id + seq) % 2 == 0 else 3
            lot, chain_orders = _build_chain_lot(
                ids,
                num_positions,
                machine_id=None,
                machine_pool_id=pool_id,
                queue_sequence=seq,
                duration_minutes=45,
            )
            lots.append(lot)
            orders.extend(chain_orders)

    recompute, _order_repo, _uow = build_recompute(lots, orders, machines, pools)

    started = time.perf_counter()
    result = await recompute.execute_all()
    elapsed_seconds = time.perf_counter() - started
    print(
        f"\nexecute_all() benchmark: {elapsed_seconds * 1000:.1f}ms for "
        f"{len(orders)} order(s) ({sum(len(v) for v in result.by_machine.values())} "
        f"machine-assigned, {sum(len(v) for v in result.by_pool.values())} pool-floating)"
    )

    assert elapsed_seconds < 2.0
    assert sum(len(v) for v in result.by_machine.values()) == 1000
    assert sum(len(v) for v in result.by_pool.values()) == 250
    _assert_no_overlaps_per_machine(result)
