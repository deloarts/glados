"""
The production order rules, the completion request and the lot position
provision compare quantities through the shared helpers in
domain/services/quantities.py, so they agree with the lifecycle on what
counts as reached: a difference within QUANTITY_EPSILON is rounding noise,
and anything beyond it counts.
"""

from datetime import date

import pytest

from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    RecordProductionOrderCompletionRequest,
)
from src.modules.fulfillment.application.dto.production_lot_dto import (
    RecordLotPositionProvisionCommand,
)
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    RecordLotPositionProvision,
)
from src.modules.fulfillment.domain.errors import LotPositionProvisionOverflowError
from src.modules.fulfillment.domain.errors import ProductionOrderCompletionSplitInvalidError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.errors import ProductionOrderSplitMismatchError
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_order_completion_within_order_quantity,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_quantity_within_position,
)
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_split_sums_correctly,
)
from src.modules.fulfillment.domain.services.production_order_rules import assert_valid_disposition
from src.modules.fulfillment.domain.services.production_order_rules import is_position_fully_queued
from src.modules.fulfillment.domain.services.production_order_rules import resolve_completion_split
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order._helpers import make_order

# A difference within QUANTITY_EPSILON, and one beyond it.
_NOISE = 5e-7
_REAL = 1e-5
_DAY = date(2026, 1, 3)


def test_the_queued_total_may_miss_the_position_by_noise_only() -> None:
    assert_quantity_within_position(6.0 + _NOISE, 4.0, 10.0)
    with pytest.raises(ProductionOrderQuantityOverflowError):
        assert_quantity_within_position(6.0 + _REAL, 4.0, 10.0)


def test_a_position_is_fully_queued_within_the_tolerance() -> None:
    orders = [make_order(id=1, quantity=6.0), make_order(id=2, quantity=4.0)]
    assert is_position_fully_queued(orders, 10.0 + _NOISE) is True
    assert is_position_fully_queued(orders, 10.0 + _REAL) is False


def test_split_parts_sum_to_the_order_within_the_tolerance() -> None:
    assert_split_sums_correctly([6.0, 4.0], 10.0 + _NOISE)
    with pytest.raises(ProductionOrderSplitMismatchError):
        assert_split_sums_correctly([6.0, 4.0], 10.0 + _REAL)


def test_an_order_processes_its_quantity_within_the_tolerance() -> None:
    order = make_order(quantity=10.0)
    assert_order_completion_within_order_quantity(order, 9.0, 1.0 + _NOISE)
    with pytest.raises(ProductionOrderQuantityOverflowError):
        assert_order_completion_within_order_quantity(order, 9.0, 1.0 + _REAL)


def test_the_completion_split_sums_to_its_quantity_within_the_tolerance() -> None:
    assert resolve_completion_split(10.0, 6.0, 4.0 + _NOISE) == (6.0, 4.0 + _NOISE)
    with pytest.raises(ProductionOrderCompletionSplitInvalidError):
        resolve_completion_split(10.0, 6.0, 4.0 + _REAL)


def test_the_disposition_sums_to_the_rejected_pieces_within_the_tolerance() -> None:
    assert_valid_disposition(True, 3.0, 1.0, 2.0 + _NOISE)
    with pytest.raises(ProductionOrderCompletionSplitInvalidError):
        assert_valid_disposition(True, 3.0, 1.0, 2.0 + _REAL)


def test_rejected_noise_on_an_ordinary_completion_counts_as_none() -> None:
    assert_valid_disposition(False, _NOISE, 0.0, 0.0)
    with pytest.raises(ProductionOrderCompletionSplitInvalidError):
        assert_valid_disposition(False, _REAL, 0.0, 0.0)


def test_the_completion_request_takes_a_split_whose_sum_carries_float_noise() -> None:
    request = RecordProductionOrderCompletionRequest(
        quantity=0.3, quantity_accepted=0.1, quantity_rejected=0.2, completion_date=_DAY
    )
    assert (request.quantity_accepted, request.quantity_rejected) == (0.1, 0.2)
    with pytest.raises(ValueError, match="must equal quantity"):
        RecordProductionOrderCompletionRequest(
            quantity=0.3, quantity_accepted=0.1, quantity_rejected=0.21, completion_date=_DAY
        )


async def _external_position() -> tuple[Floor, int, int, RecordLotPositionProvision]:
    floor = Floor(positions=1)
    lot = await floor.lot(10.0)
    (position,) = await floor.positions(lot.id)
    position.kind = LotPositionKind.EXTERNAL
    await floor.lots.save_position(position)
    return floor, lot.id, position.id, RecordLotPositionProvision(floor.lots, uow=FakeUnitOfWork())


async def test_a_provision_may_reach_the_input_within_the_tolerance() -> None:
    floor, lot_id, position_id, provisions = await _external_position()
    await provisions.execute(
        floor.planner,
        lot_id,
        position_id,
        RecordLotPositionProvisionCommand(quantity=10.0 + _NOISE, provision_date=date(2026, 1, 3)),
    )
    assert len(await floor.lots.get_provisions(position_id)) == 1


async def test_a_provision_beyond_the_tolerance_is_refused() -> None:
    floor, lot_id, position_id, provisions = await _external_position()
    with pytest.raises(LotPositionProvisionOverflowError):
        await provisions.execute(
            floor.planner,
            lot_id,
            position_id,
            RecordLotPositionProvisionCommand(
                quantity=10.0 + _REAL, provision_date=date(2026, 1, 3)
            ),
        )
