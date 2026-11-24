"""The latest day external work can leave for the supplier: counted back
from the lot's target date, less the safety margin, over the positions after
it and its own lead days, the way Auto-Plan dates positions."""

from datetime import date

from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkChain
from src.modules.fulfillment.domain.services.scheduling.external_work import forecast_external_work
from src.modules.fulfillment.domain.services.scheduling.external_work import latest_pickup_dates
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind

_MILLING, _HARDENING, _QA = 10, 20, 30


def _position(
    position_id: int,
    sequence: int,
    kind: LotPositionKind,
    *,
    lead_days: int | None = None,
    outsourced_unassigned: bool = False,
) -> PredecessorPosition:
    return PredecessorPosition(
        position_id=position_id,
        sequence=sequence,
        kind=kind,
        external_ready_at=None,
        stored_internal_ready_at=None,
        lead_days=lead_days,
        outsourced_unassigned=outsourced_unassigned,
    )


def _chain(
    *positions: PredecessorPosition,
    target_date: date | None,
    minutes: dict[int, int] | None = None,
    external: frozenset[int] = frozenset({_HARDENING}),
) -> ExternalWorkChain:
    return ExternalWorkChain(
        lot_id=1,
        positions=tuple(positions),
        external_position_ids=external,
        target_date=target_date,
        remaining_minutes_by_position=minutes or {},
    )


def test_hardening_before_qa_leaves_its_lead_days_before_qa_must_start():
    """Target the 20th, 2 days margin: QA (20 minutes, one day) must start
    on the 17th, so the hardening is back by then and leaves 4 days
    earlier, on the 13th."""
    chain = _chain(
        _position(_MILLING, 1, LotPositionKind.INTERNAL),
        _position(_HARDENING, 2, LotPositionKind.EXTERNAL, lead_days=4),
        _position(_QA, 3, LotPositionKind.INTERNAL),
        target_date=date(2026, 8, 20),
        minutes={_MILLING: 200, _QA: 20},
    )

    assert latest_pickup_dates(chain, safety_margin_days=2) == {_HARDENING: date(2026, 8, 13)}


def test_a_longer_internal_step_after_the_hardening_moves_it_earlier():
    """QA of 1000 minutes takes three days of eight hours."""
    chain = _chain(
        _position(_HARDENING, 1, LotPositionKind.EXTERNAL, lead_days=4),
        _position(_QA, 2, LotPositionKind.INTERNAL),
        target_date=date(2026, 8, 20),
        minutes={_QA: 1000},
    )

    assert latest_pickup_dates(chain, safety_margin_days=0) == {_HARDENING: date(2026, 8, 13)}


def test_hardening_that_ends_the_lot_leaves_its_lead_days_before_the_target():
    chain = _chain(
        _position(_MILLING, 1, LotPositionKind.INTERNAL),
        _position(
            _HARDENING, 2, LotPositionKind.UNASSIGNED, lead_days=4, outsourced_unassigned=True
        ),
        target_date=date(2026, 8, 20),
    )

    assert latest_pickup_dates(chain, safety_margin_days=2) == {_HARDENING: date(2026, 8, 14)}


def test_a_lot_without_a_target_date_has_no_latest_pickup():
    chain = _chain(
        _position(_HARDENING, 1, LotPositionKind.EXTERNAL, lead_days=4), target_date=None
    )

    assert latest_pickup_dates(chain, safety_margin_days=2) == {}


def test_two_external_steps_in_a_row_each_get_their_own_latest_pickup():
    """Hardening (4 days) then galvanizing (3 days) at the end of the lot:
    galvanizing leaves 3 days before the 18th, hardening 4 days before
    that."""
    galvanizing = 25
    chain = _chain(
        _position(_HARDENING, 1, LotPositionKind.EXTERNAL, lead_days=4),
        _position(galvanizing, 2, LotPositionKind.EXTERNAL, lead_days=3),
        target_date=date(2026, 8, 20),
        external=frozenset({_HARDENING, galvanizing}),
    )

    assert latest_pickup_dates(chain, safety_margin_days=2) == {
        galvanizing: date(2026, 8, 15),
        _HARDENING: date(2026, 8, 11),
    }


def test_the_forecast_carries_the_latest_pickup_next_to_the_ready_date():
    chain = _chain(
        _position(_MILLING, 1, LotPositionKind.INTERNAL),
        _position(_HARDENING, 2, LotPositionKind.EXTERNAL, lead_days=4),
        target_date=date(2026, 8, 20),
    )

    [forecast] = forecast_external_work(
        [chain], {_MILLING: date(2026, 8, 3)}, response_time_days=1, safety_margin_days=2
    )

    assert forecast.position_id == _HARDENING
    assert forecast.planned_pickup_date == date(2026, 8, 4)
    assert forecast.planned_delivery_date == date(2026, 8, 8)
    assert forecast.latest_pickup_date == date(2026, 8, 14)
    assert forecast.latest_delivery_date == date(2026, 8, 18)
