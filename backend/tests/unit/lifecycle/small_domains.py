"""Exhaustive small domains of lifecycle facts.

Each generator yields every combination of a few representative values per
field: an intent present or absent, quantities on both sides of the tolerance
(1e-7 counts as zero, 1 - 1e-7 as one), every status of the enums involved,
and up to two or three children. The derivation tests run each table over
these products to show that it is total, that every row is reached, and that
it agrees with a transcription of the target table.
"""

from collections.abc import Iterator
from collections.abc import Sequence
from datetime import UTC
from datetime import datetime
from itertools import product

from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLotFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import DemandFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import LotFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderItemFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import ProductionOrderFacts
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus

T0 = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
INTENT_VALUES: tuple[datetime | None, ...] = (None, T0)


def sequences[T](values: Sequence[T], max_length: int) -> Iterator[tuple[T, ...]]:
    """Every tuple of `values` of length 0 to max_length, order included."""
    for length in range(max_length + 1):
        yield from product(values, repeat=length)


def order_item_facts() -> Iterator[OrderItemFacts]:
    for quantity, delivered, lost, requested_at, ordered_date, canceled_at in product(
        (0.0, 1.0, 2.0),
        (0.0, 1e-7, 0.5, 1.0 - 1e-7, 1.0),
        (0.0, 0.5),
        INTENT_VALUES,
        INTENT_VALUES,
        INTENT_VALUES,
    ):
        yield OrderItemFacts(
            quantity=quantity,
            delivered=delivered,
            lost=lost,
            requested_at=requested_at,
            ordered_date=ordered_date,
            canceled_at=canceled_at,
        )


def order_facts() -> Iterator[OrderFacts]:
    for line_statuses in sequences(list(OrderItemStatus), 3):
        for requested_at, ordered_date, canceled_at in product(INTENT_VALUES, repeat=3):
            yield OrderFacts(
                requested_at=requested_at,
                ordered_date=ordered_date,
                canceled_at=canceled_at,
                line_statuses=line_statuses,
            )


def production_order_facts() -> Iterator[ProductionOrderFacts]:
    for quantity, processed, actual_start, canceled_at, open_interruption in product(
        (0.0, 1.0),
        (0.0, 0.5, 1.0 - 1e-7, 1.0),
        INTENT_VALUES,
        INTENT_VALUES,
        (None, *InterruptionReason),
    ):
        yield ProductionOrderFacts(
            quantity=quantity,
            processed=processed,
            actual_start=actual_start,
            canceled_at=canceled_at,
            open_interruption=open_interruption,
        )


_POSITION_LINES: tuple[PositionLineFacts | None, ...] = (
    None,
    *(
        PositionLineFacts(status=status, quantity=1.0, delivered=delivered)
        for status, delivered in product(OrderItemStatus, (0.0, 0.5, 1.0))
    ),
)
_POSITION_ORDERS = tuple(
    PositionOrderFacts(status=status, quantity=1.0, quantity_completed=completed)
    for status, completed in product(ProductionOrderStatus, (0.0, 0.5, 1.0))
)


def lot_position_facts() -> Iterator[LotPositionFacts]:
    for orders in sequences(_POSITION_ORDERS, 2):
        for quantity, line, lot_canceled in product((0.0, 1.0), _POSITION_LINES, (False, True)):
            yield LotPositionFacts(
                quantity=quantity, line=line, orders=orders, lot_canceled=lot_canceled
            )


def lot_facts() -> Iterator[LotFacts]:
    for position_statuses in sequences(list(LotPositionStatus), 3):
        for quantity, held_at, canceled_at, force_completed_at in product(
            (0.0, 1e-7, 1.0), INTENT_VALUES, INTENT_VALUES, INTENT_VALUES
        ):
            yield LotFacts(
                quantity=quantity,
                position_statuses=position_statuses,
                held_at=held_at,
                canceled_at=canceled_at,
                force_completed_at=force_completed_at,
            )


_ALLOCATIONS: tuple[AllocationFacts, ...] = (
    AllocationFacts.stock(0.5),
    AllocationFacts.stock(1.0),
    AllocationFacts(quantity=1.0, from_stock=False, line=None, lot=None),
    # Zero-quantity rows, such as a full scrap leaves behind.
    AllocationFacts.on_lot(
        0.0, CoveringLotFacts(status=LotStatus.SCRAPPED, quantity=0.0, quantity_completed=0.0)
    ),
    AllocationFacts.on_line(
        0.0,
        CoveringLineFacts(status=OrderItemStatus.PENDING, quantity=1.0, delivered=0.0, lost=0.0),
    ),
    *(
        AllocationFacts.on_line(
            1.0,
            CoveringLineFacts(status=status, quantity=1.0, delivered=delivered, lost=lost),
        )
        for status, (delivered, lost) in product(
            OrderItemStatus, ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
        )
    ),
    *(
        AllocationFacts.on_lot(
            1.0, CoveringLotFacts(status=status, quantity=1.0, quantity_completed=completed)
        )
        for status, completed in product(LotStatus, (0.0, 1.0))
    ),
)


def demand_facts() -> Iterator[DemandFacts]:
    for allocations in sequences(_ALLOCATIONS, 2):
        for quantity, canceled_at, fulfilled_manually_at in product(
            (0.0, 1.0, 2.0), INTENT_VALUES, INTENT_VALUES
        ):
            yield DemandFacts(
                quantity=quantity,
                allocations=allocations,
                canceled_at=canceled_at,
                fulfilled_manually_at=fulfilled_manually_at,
            )
