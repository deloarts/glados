"""
A piece disposition that cuts a paused production order back to the pieces
it already processed ends the order, so its open pause is closed as a cut:
no work follows it, unlike a resume. A cut that leaves open pieces keeps the
order paused. The cut runs against in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.application.services.piece_disposition import DispositionRepositories
from src.modules.fulfillment.application.services.piece_disposition import _cut_order
from src.modules.fulfillment.domain.services.lot_rules import Commitment
from src.modules.fulfillment.domain.services.lot_rules import CommitmentCut
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import production_order_reconciler

_NOW = datetime(2026, 3, 2, 13, 0, tzinfo=UTC)


async def _cut_paused_order(
    done: float, cut_to: float
) -> FakeProductionOrderInterruptionRepository:
    """Cuts paused order #1 of ten pieces, which processed `done`, to
    `cut_to` pieces, and returns its interruptions."""
    position = make_position(id=1, quantity=10.0)
    lot = make_lot(positions=[position])
    order = make_order(id=1, status=ProductionOrderStatus.PAUSED, quantity=10.0)
    order_repo = FakeProductionOrderRepository([order])
    lot_repo = FakeProductionLotRepository([lot])
    interruptions = FakeProductionOrderInterruptionRepository(order_repo._orders)
    bus = FakeEventBus()
    work = DispositionRepositories(
        production_orders=order_repo,  # type: ignore[arg-type]
        order_items=None,  # type: ignore[arg-type]
        orders=None,  # type: ignore[arg-type]
        interruptions=interruptions,  # type: ignore[arg-type]
        source_item_demands=None,  # type: ignore[arg-type]
        source_item_allocations=None,  # type: ignore[arg-type]
        reconciler=production_order_reconciler(order_repo, lot_repo, bus),
    )
    await _cut_order(
        lot_repo,  # type: ignore[arg-type]
        work,
        make_user(id=5, permissions=[Permission.WRITE_LOTS]),
        lot,
        position,
        order,
        CommitmentCut(Commitment(id=1, is_line=False, quantity=10.0, done=done), cut_to),
        "scrapped at inspection",
        _NOW,
    )
    return interruptions


async def test_a_cut_to_the_processed_pieces_closes_the_pause_as_a_cut() -> None:
    interruptions = await _cut_paused_order(done=4.0, cut_to=4.0)

    [row] = interruptions.rows
    assert row.resumed_at == _NOW
    assert row.ended_by is InterruptionEndedBy.CUT
    assert row.resumed_operator_id is None


async def test_a_cut_that_leaves_open_pieces_keeps_the_pause_open() -> None:
    interruptions = await _cut_paused_order(done=4.0, cut_to=6.0)

    [row] = interruptions.rows
    assert row.resumed_at is None
    assert row.ended_by is None
