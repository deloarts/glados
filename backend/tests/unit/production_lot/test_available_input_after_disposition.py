"""
After a downstream disposition the lot shrinks while position 1 keeps its
quantity, since its output also fed the removed pieces. Position 1's
available input is its own quantity, capped by the arrived raw material, so
it can still finish every piece it was planned for: a lot of 10 with
position 1 at 9 of 10 and two pieces scrapped at position 2 is a lot of 8,
and position 1 can still record, start on, deliver, scrap and provision up
to its tenth piece.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import (
    RecordLotPositionProvisionCommand,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    _resolve_upstream_input_available,
)
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    RecordLotPositionProvision,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.services.lot_rules import assert_completion_within_available
from src.modules.fulfillment.domain.services.lot_rules import assert_position_has_available_input
from src.modules.fulfillment.domain.services.lot_rules import available_input
from src.modules.fulfillment.domain.services.lot_rules import scrap_capacity
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot.fakes import FakeUnitOfWork


async def _scrapped_downstream() -> tuple[Floor, ProductionLot, int]:
    """The lot of 8 described in the module docstring and the id of its
    position 1 order."""
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    upstream = await floor.order(first, processed=9.0)
    downstream = await floor.order(second)
    await floor.settle(lot.id)
    await floor.scrap(downstream.id, 2.0)
    lot = await floor.reload(lot.id)
    assert lot.quantity == 8.0
    assert [(p.quantity, p.quantity_completed) for p in lot.positions] == [(10.0, 9.0), (8.0, 0.0)]
    return floor, lot, upstream.id


async def test_position_one_can_record_its_tenth_piece() -> None:
    floor, lot, upstream = await _scrapped_downstream()

    await floor.complete(upstream, 1.0)

    lot = await floor.reload(lot.id)
    assert (lot.positions[0].quantity_completed, lot.positions[0].status) == (10.0, "completed")


async def test_position_one_has_input_to_start_and_resume_on() -> None:
    _, lot, _ = await _scrapped_downstream()
    first = lot.positions[0]

    assert available_input(lot.positions, lot.quantity, 1, raw_material_arrived=10.0) == 10.0
    assert_position_has_available_input(first, lot.positions, lot.quantity, 10.0)


async def test_the_arrived_raw_material_still_caps_position_one() -> None:
    _, lot, _ = await _scrapped_downstream()

    with pytest.raises(LotPositionOverflowError):
        assert_position_has_available_input(lot.positions[0], lot.positions, lot.quantity, 9.0)


async def test_position_one_can_scrap_its_last_piece_and_no_more() -> None:
    _, lot, _ = await _scrapped_downstream()

    assert scrap_capacity(lot, lot.positions[0], raw_material_arrived=10.0) == 1.0


async def test_a_made_line_on_an_external_position_one_can_deliver_up_to_ten() -> None:
    _, lot, _ = await _scrapped_downstream()
    first = lot.positions[0]
    first.kind = LotPositionKind.EXTERNAL

    assert_completion_within_available(first, lot.positions, lot.quantity, 1.0)
    with pytest.raises(LotPositionOverflowError):
        assert_completion_within_available(first, lot.positions, lot.quantity, 2.0)


async def test_a_provision_on_position_one_can_reach_ten() -> None:
    floor, lot, _ = await _scrapped_downstream()
    first = lot.positions[0]
    first.kind = LotPositionKind.EXTERNAL
    await floor.lots.save_position(first)
    provisions = RecordLotPositionProvision(floor.lots, uow=FakeUnitOfWork())

    await provisions.execute(
        floor.planner,
        lot.id,
        first.id,
        RecordLotPositionProvisionCommand(quantity=10.0, provision_date=date(2026, 1, 3)),
    )

    assert [p.quantity for p in await floor.lots.get_provisions(first.id)] == [10.0]


async def test_the_scheduler_says_position_one_has_input() -> None:
    floor, lot, _ = await _scrapped_downstream()
    assert lot.input_demand_id is not None

    available = await _resolve_upstream_input_available(
        lot.positions[0],
        lot,
        SimpleNamespace(lots=floor.lots),  # type: ignore[arg-type]
        {lot.input_demand_id: 10.0},
    )

    assert available is True
