"""Table tests for the lot status derivation
(src/modules/fulfillment/domain/services/lifecycle/lot.py): one or more cases per row, then every
fact combination of a small domain against a transcription of the target
table."""

from dataclasses import replace

import pytest

from src.modules.fulfillment.domain.services.lifecycle.facts import LotFacts
from src.modules.fulfillment.domain.services.lifecycle.lot import LOT_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot import derive_lot_quantity_completed
from src.modules.fulfillment.domain.services.lifecycle.lot import derive_lot_status
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from tests.unit.lifecycle.small_domains import T0
from tests.unit.lifecycle.small_domains import lot_facts

EPS = 1e-6

PENDING = LotPositionStatus.PENDING
QUEUED = LotPositionStatus.ORDERED_OR_QUEUED
RUNNING = LotPositionStatus.IN_PROGRESS
PARTIAL = LotPositionStatus.PARTIALLY_COMPLETED
DONE = LotPositionStatus.COMPLETED

_DRAFT_LOT = LotFacts(
    quantity=10.0, position_statuses=(), held_at=None, canceled_at=None, force_completed_at=None
)


def _facts(*positions: LotPositionStatus, **changes: object) -> LotFacts:
    return replace(_DRAFT_LOT, position_statuses=positions, **changes)


@pytest.mark.parametrize(
    ("facts", "status", "row"),
    [
        (_facts(DONE, DONE, canceled_at=T0), LotStatus.CANCELED, 1),
        (_facts(canceled_at=T0, quantity=0.0), LotStatus.CANCELED, 1),
        (_facts(DONE, quantity=0.0, force_completed_at=T0), LotStatus.SCRAPPED, 2),
        (_facts(QUEUED, quantity=1e-7), LotStatus.SCRAPPED, 2),
        (_facts(DONE, DONE, DONE), LotStatus.COMPLETED, 3),
        (_facts(DONE, DONE, held_at=T0), LotStatus.COMPLETED, 3),
        (_facts(DONE, PARTIAL, force_completed_at=T0), LotStatus.COMPLETED, 3),
        (_facts(force_completed_at=T0), LotStatus.COMPLETED, 3),
        (_facts(RUNNING, held_at=T0), LotStatus.ON_HOLD, 4),
        (_facts(PENDING, held_at=T0), LotStatus.ON_HOLD, 4),
        (_facts(held_at=T0), LotStatus.ON_HOLD, 4),
        (_facts(PARTIAL, DONE), LotStatus.IN_PROGRESS, 5),
        (_facts(DONE, PENDING), LotStatus.IN_PROGRESS, 5),
        (_facts(QUEUED, RUNNING, PENDING), LotStatus.IN_PROGRESS, 5),
        (_facts(QUEUED, QUEUED), LotStatus.PLANNED, 6),
        (_facts(QUEUED, PENDING), LotStatus.PARTIALLY_PLANNED, 7),
        (_facts(PENDING, PENDING), LotStatus.DRAFT, 8),
        (_facts(), LotStatus.DRAFT, 8),
    ],
)
def test_derive_lot_status_rows(facts, status, row):
    derivation = derive_lot_status(facts)
    assert (derivation.value, derivation.rule) == (status, row)


def test_lot_completes_only_when_every_position_is_complete():
    # A completed last position does not complete the lot while an earlier
    # position is short.
    assert derive_lot_status(_facts(PARTIAL, DONE)).value == LotStatus.IN_PROGRESS


def test_held_lot_completes_when_its_positions_complete():
    assert derive_lot_status(_facts(DONE, held_at=T0)).value == LotStatus.COMPLETED


@pytest.mark.parametrize(
    ("completed", "expected"),
    [((), 0.0), ((10.0,), 10.0), ((10.0, 8.0, 7.5), 7.5), ((3.0, 9.0), 9.0)],
)
def test_lot_quantity_completed_is_the_last_positions(completed, expected):
    assert derive_lot_quantity_completed(completed) == expected


def _transcribed(f: LotFacts) -> tuple[LotStatus, int]:
    """The target table, written out independently of the module."""
    positions = f.position_statuses
    if f.canceled_at is not None:
        return LotStatus.CANCELED, 1
    if abs(f.quantity) <= EPS:
        return LotStatus.SCRAPPED, 2
    if f.force_completed_at is not None or (positions and all(s == DONE for s in positions)):
        return LotStatus.COMPLETED, 3
    if f.held_at is not None:
        return LotStatus.ON_HOLD, 4
    if any(s in (RUNNING, PARTIAL, DONE) for s in positions):
        return LotStatus.IN_PROGRESS, 5
    if positions and all(s != PENDING for s in positions):
        return LotStatus.PLANNED, 6
    if any(s != PENDING for s in positions):
        return LotStatus.PARTIALLY_PLANNED, 7
    return LotStatus.DRAFT, 8


def test_derive_lot_status_matches_the_table_on_every_small_case():
    reached = set()
    for facts in lot_facts():
        derivation = derive_lot_status(facts)
        assert isinstance(derivation.value, LotStatus)
        assert (derivation.value, derivation.rule) == _transcribed(facts), facts
        reached.add(derivation.rule)
    assert reached == {row.number for row in LOT_STATUS.rows}
