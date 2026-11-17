"""
Structure edits register the lot with the lifecycle reconciler, so what they
change shows in the derived statuses at once: deleting the last step of the
only unfinished position completes the lot, and a created lot with a QA
position planned from birth is PARTIALLY_PLANNED. A position committed to a
machine or with pieces made keeps its place in the sequence, a new step
joins its position after the position's last step, and the positions are
numbered again after one disappears.
"""

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import AddLotStepCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ReorderLotStepsCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import AddLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import DeleteLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import ReorderLotSteps
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.production_lot._floor import NOW
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot._helpers import make_fabrication_method
from tests.unit.production_lot.fakes import FakeFabricationMethodRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


def _delete(floor: Floor) -> DeleteLotStep:
    return DeleteLotStep(
        floor.lots,
        order_item_repo=FakeOrderItemRepository(),
        order_repo=FakeProductionOrderRepository(),
        uow=FakeUnitOfWork(),
        reconciler=lot_reconciler(floor.lots, floor.orders, bus=floor.bus),
    )


def _reorder(floor: Floor) -> ReorderLotSteps:
    return ReorderLotSteps(
        floor.lots,
        uow=FakeUnitOfWork(),
        reconciler=lot_reconciler(floor.lots, floor.orders, bus=floor.bus),
    )


async def test_deleting_the_emptied_trailing_step_completes_the_lot() -> None:
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=10.0)
    await floor.settle(lot.id)
    assert (await floor.reload(lot.id)).status == "in_progress"
    [trailing] = [s for s in await floor.lots.get_steps(lot.id) if s.position_id == second.id]

    await _delete(floor).execute(floor.planner, trailing.id)

    lot = await floor.reload(lot.id)
    assert [p.id for p in lot.positions] == [first.id]
    assert lot.status == "completed"
    assert lot.completed_at is not None
    assert [e.lot_id for e in floor.bus.published if isinstance(e, LotCompleted)] == [lot.id]


async def test_a_created_lot_with_a_qa_position_planned_from_birth_is_partially_planned() -> None:
    floor = Floor(positions=2, inspection_last=True)

    lot = await floor.lot(10.0)

    assert [(p.kind, p.status) for p in lot.positions] == [
        ("unassigned", "pending"),
        ("internal", "ordered_or_queued"),
    ]
    assert lot.status == "partially_planned"


async def test_a_position_with_pieces_made_keeps_its_place_after_its_order_is_canceled() -> None:
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=10.0)
    order = await floor.order(second, processed=3.0)
    order.status = ProductionOrderStatus.CANCELED
    order.canceled_at = NOW
    await floor.settle(lot.id)
    steps = await floor.lots.get_steps(lot.id)

    with pytest.raises(LotPositionAlreadyAssignedError):
        await _reorder(floor).execute(
            floor.planner,
            lot.id,
            ReorderLotStepsCommand(ordered_step_ids=[s.id for s in reversed(steps)]),
        )

    assert [p.id for p in await floor.positions(lot.id)] == [first.id, second.id]


async def test_unassigned_positions_may_move() -> None:
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    steps = await floor.lots.get_steps(lot.id)

    await _reorder(floor).execute(
        floor.planner,
        lot.id,
        ReorderLotStepsCommand(ordered_step_ids=[s.id for s in reversed(steps)]),
    )

    positions = await floor.positions(lot.id)
    assert [(p.id, p.sequence) for p in positions] == [(second.id, 1), (first.id, 2)]


async def test_a_new_step_joins_its_position_after_the_positions_last_step() -> None:
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)

    added = await AddLotStep(
        floor.lots,
        FakeFabricationMethodRepository([make_fabrication_method(1)]),
        floor.inspection_methods,
        order_repo=FakeProductionOrderRepository(),
        uow=FakeUnitOfWork(),
        reconciler=lot_reconciler(floor.lots, floor.orders, bus=floor.bus),
    ).execute(
        floor.planner,
        lot.id,
        AddLotStepCommand(position_id=first.id, fabrication_method_id=1),
    )

    steps = await floor.lots.get_steps(lot.id)
    assert [(s.position_id, s.sequence) for s in steps] == [
        (first.id, 1),
        (first.id, 2),
        (second.id, 3),
    ]
    assert added.sequence == 2


async def test_deleting_a_positions_last_step_numbers_the_positions_again() -> None:
    floor = Floor(positions=3)
    lot = await floor.lot(10.0)
    first, second, third = await floor.positions(lot.id)
    [middle] = [s for s in await floor.lots.get_steps(lot.id) if s.position_id == second.id]

    await _delete(floor).execute(floor.planner, middle.id)

    positions = await floor.positions(lot.id)
    assert [(p.id, p.sequence) for p in positions] == [(first.id, 1), (third.id, 2)]
    assert [s.sequence for s in await floor.lots.get_steps(lot.id)] == [1, 2]
