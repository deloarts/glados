"""
compute_wip_summary after pieces were removed further down the chain: the
lot shrinks while position 1 keeps its larger quantity and may complete
more pieces than the lot now holds, and the raw count stays at zero then
instead of turning negative.
"""

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.services.production_wip_service import compute_wip_summary
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from tests.unit.lifecycle.fake_world import make


def _lot(quantity: float, completed: list[tuple[float, float]]) -> ProductionLot:
    """A lot whose positions have the given (quantity, completed) pairs."""
    lot = make(ProductionLot, id=1, quantity=quantity, status=LotStatus.IN_PROGRESS)
    lot.positions = [
        make(
            LotPosition,
            id=10 + sequence,
            sequence=sequence,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.PARTIALLY_COMPLETED,
            quantity=position_quantity,
            quantity_completed=done,
            lot_id=1,
        )
        for sequence, (position_quantity, done) in enumerate(completed, start=1)
    ]
    return lot


def test_raw_count_is_zero_when_position_one_completed_more_than_the_shrunk_lot() -> None:
    summary = compute_wip_summary(_lot(8.0, [(10.0, 10.0), (8.0, 3.0)]))

    assert summary.raw_count == 0.0
    assert summary.finished_count == 3.0


def test_raw_count_is_what_position_one_has_not_completed_yet() -> None:
    summary = compute_wip_summary(_lot(10.0, [(10.0, 4.0), (10.0, 1.0)]))

    assert summary.raw_count == 6.0
    assert [s.quantity_completed for s in summary.stages] == [4.0, 1.0]


def test_a_lot_without_positions_is_all_raw() -> None:
    summary = compute_wip_summary(_lot(5.0, []))

    assert (summary.raw_count, summary.finished_count, summary.stages) == (5.0, 0.0, [])
