"""Table tests for the lot position derivations
(src/modules/fulfillment/domain/services/lifecycle/lot_position.py): kind, completed count,
remaining quantity and status, one or more cases per row, then every fact
combination of a small domain against a transcription of the target tables."""

import pytest

from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_KIND
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot_position import derive_position_kind
from src.modules.fulfillment.domain.services.lifecycle.lot_position import (
    derive_position_quantity_completed,
)
from src.modules.fulfillment.domain.services.lifecycle.lot_position import derive_position_status
from src.modules.fulfillment.domain.services.lifecycle.lot_position import position_remaining
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.lifecycle.small_domains import lot_position_facts

EPS = 1e-6


def _line(
    status: OrderItemStatus, quantity: float = 10.0, delivered: float = 0.0
) -> PositionLineFacts:
    return PositionLineFacts(status=status, quantity=quantity, delivered=delivered)


def _order(
    status: ProductionOrderStatus, quantity: float = 10.0, completed: float = 0.0
) -> PositionOrderFacts:
    return PositionOrderFacts(status=status, quantity=quantity, quantity_completed=completed)


def _position(
    line: PositionLineFacts | None = None,
    *orders: PositionOrderFacts,
    quantity: float = 10.0,
    lot_canceled: bool = False,
) -> LotPositionFacts:
    return LotPositionFacts(quantity=quantity, line=line, orders=orders, lot_canceled=lot_canceled)


# ── Kind ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("facts", "kind", "row"),
    [
        (
            _position(
                _line(OrderItemStatus.ORDERED, 4.0), _order(ProductionOrderStatus.QUEUED, 6.0)
            ),
            LotPositionKind.MIXED,
            1,
        ),
        (
            _position(
                _line(OrderItemStatus.ORDERED, 4.0),
                _order(ProductionOrderStatus.CANCELED, 6.0, completed=2.0),
            ),
            LotPositionKind.MIXED,
            1,
        ),
        (_position(_line(OrderItemStatus.PENDING)), LotPositionKind.EXTERNAL, 2),
        (
            _position(_line(OrderItemStatus.ORDERED), _order(ProductionOrderStatus.CANCELED)),
            LotPositionKind.EXTERNAL,
            2,
        ),
        (
            _position(_line(OrderItemStatus.CANCELED), _order(ProductionOrderStatus.QUEUED)),
            LotPositionKind.INTERNAL,
            3,
        ),
        (
            _position(None, _order(ProductionOrderStatus.CANCELED, completed=3.0)),
            LotPositionKind.INTERNAL,
            3,
        ),
        (
            _position(None, _order(ProductionOrderStatus.COMPLETED, completed=10.0)),
            LotPositionKind.INTERNAL,
            3,
        ),
        (_position(_line(OrderItemStatus.CANCELED)), LotPositionKind.UNASSIGNED, 4),
        (_position(None, _order(ProductionOrderStatus.CANCELED)), LotPositionKind.UNASSIGNED, 4),
        (_position(), LotPositionKind.UNASSIGNED, 4),
    ],
)
def test_derive_position_kind_rows(facts, kind, row):
    derivation = derive_position_kind(facts)
    assert (derivation.value, derivation.rule) == (kind, row)


# ── Completed count and remaining quantity ──────────────────────────────


def test_completed_count_adds_the_live_line_and_every_order():
    facts = _position(
        _line(OrderItemStatus.PARTIALLY_DELIVERED, 4.0, delivered=3.0),
        _order(ProductionOrderStatus.IN_PROGRESS, 4.0, completed=2.0),
        _order(ProductionOrderStatus.CANCELED, 2.0, completed=1.0),
    )
    assert derive_position_quantity_completed(facts) == 6.0


def test_completed_count_ignores_a_canceled_line():
    facts = _position(_line(OrderItemStatus.CANCELED, delivered=5.0))
    assert derive_position_quantity_completed(facts) == 0.0


def test_remaining_subtracts_live_commitments_and_what_canceled_orders_made():
    facts = _position(
        _line(OrderItemStatus.ORDERED, 4.0),
        _order(ProductionOrderStatus.QUEUED, 2.0),
        _order(ProductionOrderStatus.COMPLETED, 1.0, completed=1.0),
        _order(ProductionOrderStatus.CANCELED, 3.0, completed=2.0),
    )
    assert position_remaining(facts) == 10.0 - 4.0 - 2.0 - 1.0 - 2.0


def test_remaining_frees_what_a_canceled_order_did_not_make():
    facts = _position(None, _order(ProductionOrderStatus.CANCELED, 10.0, completed=4.0))
    assert position_remaining(facts) == 6.0


def test_remaining_ignores_a_canceled_line():
    facts = _position(_line(OrderItemStatus.CANCELED, 10.0))
    assert position_remaining(facts) == 10.0


def _after_a_line_closed_short(line: PositionLineFacts | None) -> LotPositionFacts:
    """A position of 10 whose first line was closed short at 6, beside
    `line`, the line that took the rest."""
    return LotPositionFacts(
        quantity=10.0,
        line=line,
        closed_lines=(_line(OrderItemStatus.DELIVERED, 6.0, delivered=6.0),),
        orders=(),
        lot_canceled=False,
    )


def test_a_line_closed_short_counts_beside_the_line_that_takes_the_rest():
    pending = _after_a_line_closed_short(_line(OrderItemStatus.PENDING, 4.0))
    assert position_remaining(pending) == 0.0
    assert derive_position_quantity_completed(pending) == 6.0
    assert derive_position_kind(pending).value == LotPositionKind.EXTERNAL
    assert derive_position_status(pending).value == LotPositionStatus.PARTIALLY_COMPLETED

    arrived = _after_a_line_closed_short(_line(OrderItemStatus.DELIVERED, 4.0, delivered=4.0))
    assert derive_position_quantity_completed(arrived) == 10.0
    assert derive_position_status(arrived).value == LotPositionStatus.COMPLETED


def test_a_canceled_rest_line_leaves_the_rest_open_again():
    facts = _after_a_line_closed_short(_line(OrderItemStatus.CANCELED, 4.0))
    assert position_remaining(facts) == 4.0
    assert derive_position_quantity_completed(facts) == 6.0
    assert derive_position_kind(facts).value == LotPositionKind.EXTERNAL


# ── Status ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("facts", "status", "row"),
    [
        (
            _position(
                None, _order(ProductionOrderStatus.COMPLETED, completed=10.0), lot_canceled=True
            ),
            LotPositionStatus.CANCELED,
            1,
        ),
        (
            _position(None, _order(ProductionOrderStatus.COMPLETED, completed=10.0)),
            LotPositionStatus.COMPLETED,
            2,
        ),
        (
            _position(
                _line(OrderItemStatus.PARTIALLY_DELIVERED, 5.0, delivered=5.0),
                _order(ProductionOrderStatus.CANCELED, 5.0, completed=2.0),
                _order(ProductionOrderStatus.COMPLETED, 3.0, completed=3.0),
            ),
            LotPositionStatus.COMPLETED,
            2,
        ),
        (
            _position(
                None,
                _order(ProductionOrderStatus.COMPLETED, 1.0, completed=0.7 + 0.2 + 0.1),
                quantity=1.0,
            ),
            LotPositionStatus.COMPLETED,
            2,
        ),
        (
            _position(None, _order(ProductionOrderStatus.CANCELED, completed=4.0)),
            LotPositionStatus.PARTIALLY_COMPLETED,
            3,
        ),
        (
            _position(_line(OrderItemStatus.DELIVERED, delivered=10.0), quantity=0.0),
            LotPositionStatus.PARTIALLY_COMPLETED,
            3,
        ),
        (_position(None, _order(ProductionOrderStatus.PAUSED)), LotPositionStatus.IN_PROGRESS, 4),
        (
            _position(None, _order(ProductionOrderStatus.IN_PROGRESS)),
            LotPositionStatus.IN_PROGRESS,
            4,
        ),
        (_position(_line(OrderItemStatus.ORDERED)), LotPositionStatus.ORDERED_OR_QUEUED, 5),
        (
            _position(_line(OrderItemStatus.PARTIALLY_DELIVERED)),
            LotPositionStatus.ORDERED_OR_QUEUED,
            5,
        ),
        (
            _position(None, _order(ProductionOrderStatus.QUEUED)),
            LotPositionStatus.ORDERED_OR_QUEUED,
            5,
        ),
        (_position(_line(OrderItemStatus.REQUESTED)), LotPositionStatus.PENDING, 6),
        (_position(_line(OrderItemStatus.CANCELED, delivered=4.0)), LotPositionStatus.PENDING, 6),
        (_position(_line(OrderItemStatus.DELIVERED)), LotPositionStatus.PENDING, 6),
        (_position(), LotPositionStatus.PENDING, 6),
    ],
)
def test_derive_position_status_rows(facts, status, row):
    derivation = derive_position_status(facts)
    assert (derivation.value, derivation.rule) == (status, row)


# ── Every small case against the transcribed tables ─────────────────────


def _transcribed_kind(f: LotPositionFacts) -> tuple[LotPositionKind, int]:
    has_line = f.line is not None and f.line.status != OrderItemStatus.CANCELED
    has_order = any(o.status != ProductionOrderStatus.CANCELED for o in f.orders)
    progress = sum(o.quantity_completed for o in f.orders)
    if has_line and (has_order or progress > EPS):
        return LotPositionKind.MIXED, 1
    if has_line:
        return LotPositionKind.EXTERNAL, 2
    if has_order or progress > EPS:
        return LotPositionKind.INTERNAL, 3
    return LotPositionKind.UNASSIGNED, 4


def _transcribed_status(f: LotPositionFacts) -> tuple[LotPositionStatus, int]:
    line = f.line if f.line is not None and f.line.status != OrderItemStatus.CANCELED else None
    live = [o for o in f.orders if o.status != ProductionOrderStatus.CANCELED]
    completed = (line.delivered if line else 0.0) + sum(o.quantity_completed for o in f.orders)
    if f.lot_canceled:
        return LotPositionStatus.CANCELED, 1
    if f.quantity > EPS and completed >= f.quantity - EPS:
        return LotPositionStatus.COMPLETED, 2
    if completed > EPS:
        return LotPositionStatus.PARTIALLY_COMPLETED, 3
    if any(
        o.status in (ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.PAUSED) for o in live
    ):
        return LotPositionStatus.IN_PROGRESS, 4
    line_placed = line is not None and line.status in (
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
    )
    if line_placed or any(o.status == ProductionOrderStatus.QUEUED for o in live):
        return LotPositionStatus.ORDERED_OR_QUEUED, 5
    return LotPositionStatus.PENDING, 6


def test_position_derivations_match_the_tables_on_every_small_case():
    kinds_reached = set()
    statuses_reached = set()
    for facts in lot_position_facts():
        kind = derive_position_kind(facts)
        status = derive_position_status(facts)
        assert isinstance(kind.value, LotPositionKind)
        assert isinstance(status.value, LotPositionStatus)
        assert (kind.value, kind.rule) == _transcribed_kind(facts), facts
        assert (status.value, status.rule) == _transcribed_status(facts), facts
        kinds_reached.add(kind.rule)
        statuses_reached.add(status.rule)
    assert kinds_reached == {row.number for row in POSITION_KIND.rows}
    assert statuses_reached == {row.number for row in POSITION_STATUS.rows}
