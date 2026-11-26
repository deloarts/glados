"""
A late arrival pushes the steps after it. An expected delivery day, of a
supplier line or of the raw material, that has passed without the delivery
or a ready-for-pickup event counts as today, and the response time is added
on top, so the next step is dated from when the pieces can still arrive
rather than from "now". An actual delivery or pickup event always wins.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import resolve_external_predecessor_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_input_material_ready_at
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    ExplanationInputs,
)
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    explain_external_work,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service.test_external_work_forecasts import _RESPONSE_TIME_DAYS
from tests.unit.scheduling_service.test_external_work_forecasts import _hardening
from tests.unit.scheduling_service.test_external_work_forecasts import _inspection
from tests.unit.scheduling_service.test_external_work_forecasts import _inspection_order
from tests.unit.scheduling_service.test_external_work_forecasts import _lot
from tests.unit.scheduling_service.test_external_work_forecasts import _order_item
from tests.unit.scheduling_service.test_external_work_forecasts import _position
from tests.unit.scheduling_service.test_external_work_forecasts import _recompute
from tests.unit.scheduling_service.test_external_work_forecasts import _step

WEDNESDAY = MONDAY + timedelta(days=2)
# Two days after the expected arrival on MONDAY, which has not happened.
_NOW = datetime.combine(WEDNESDAY, time(10), tzinfo=UTC)


def test_a_passed_expected_delivery_counts_as_today():
    assert (
        resolve_external_predecessor_ready_at(None, None, MONDAY, zone=UTC, today=WEDNESDAY)
        == WEDNESDAY
    )


def test_an_expected_delivery_still_ahead_keeps_its_day():
    ahead = WEDNESDAY + timedelta(days=5)
    assert (
        resolve_external_predecessor_ready_at(None, None, ahead, zone=UTC, today=WEDNESDAY) == ahead
    )


def test_a_delivery_or_pickup_event_in_the_past_still_wins():
    delivered = datetime.combine(MONDAY - timedelta(days=7), time(9), tzinfo=UTC)
    picked_up = datetime.combine(MONDAY - timedelta(days=6), time(9), tzinfo=UTC)
    assert (
        resolve_external_predecessor_ready_at(delivered, None, MONDAY, zone=UTC, today=WEDNESDAY)
        == delivered.date()
    )
    assert (
        resolve_external_predecessor_ready_at(None, picked_up, MONDAY, zone=UTC, today=WEDNESDAY)
        == picked_up.date()
    )


def test_raw_material_expected_on_a_passed_day_counts_as_today():
    delivered = datetime.combine(MONDAY - timedelta(days=7), time(9), tzinfo=UTC)
    assert resolve_input_material_ready_at([(None, MONDAY)], zone=UTC, today=WEDNESDAY) == WEDNESDAY
    # A delivered line keeps its day although its expected day has passed too.
    assert (
        resolve_input_material_ready_at(
            [(delivered, MONDAY - timedelta(days=8))], zone=UTC, today=WEDNESDAY
        )
        == delivered.date()
    )
    # The latest line still wins once the late one counts as today.
    ahead = WEDNESDAY + timedelta(days=3)
    assert (
        resolve_input_material_ready_at([(None, MONDAY), (None, ahead)], zone=UTC, today=WEDNESDAY)
        == ahead
    )


def _inputs(today: date) -> ExplanationInputs:
    return ExplanationInputs(
        target_date=None,
        target_demand_id=None,
        response_time_days=1,
        safety_margin_days=0,
        default_external_lead_days=3,
        zone=UTC,
        today=today,
    )


def _kinds_and_dates(terms) -> list[tuple[str, date | None]]:
    return [(term.kind.value, term.date) for term in terms]


def test_the_tooltip_counts_late_raw_material_from_today():
    hardening = _hardening(LotPositionKind.EXTERNAL, sequence=1)
    lot = _lot(hardening)
    lot.source_expected_delivery_date = MONDAY

    terms = explain_external_work(hardening, lot, _inputs(WEDNESDAY), ready_now=False).ready_from

    assert _kinds_and_dates(terms) == [
        ("raw_material", MONDAY),
        ("late_arrival", WEDNESDAY),
        ("response_time", None),
        ("result", WEDNESDAY + timedelta(days=1)),
    ]


def test_the_tooltip_counts_a_late_step_before_from_today():
    hardening = _hardening(LotPositionKind.EXTERNAL, sequence=1)
    hardening.order_item_id = 1
    hardening.expected_delivery_date = MONDAY
    coating = _position(
        40,
        2,
        LotPositionKind.EXTERNAL,
        [_step(40, 40, method_id=3, lead_days=2, outsourced=True)],
    )
    lot = _lot(hardening, coating)

    terms = explain_external_work(coating, lot, _inputs(WEDNESDAY), ready_now=False).ready_from

    assert _kinds_and_dates(terms) == [
        ("after_step", MONDAY),
        ("late_arrival", WEDNESDAY),
        ("response_time", None),
        ("result", WEDNESDAY + timedelta(days=1)),
    ]


async def test_a_late_supplier_delivery_pushes_the_next_step(monkeypatch):
    """The hardening was expected back on MONDAY and is not, so the QA check
    after it starts the day after today, not today at the current hour."""
    pin_scheduling_clock(monkeypatch, _NOW)
    hardening = _hardening(LotPositionKind.EXTERNAL, sequence=1)
    recompute, orders = _recompute(
        _lot(hardening, _inspection()),
        [_inspection_order()],
        [_order_item(1, lot_position_id=20, expected_delivery_date=MONDAY)],
    )

    await recompute.execute_all()

    qa_order = orders.orders[3]
    assert qa_order.planned_start == datetime.combine(
        WEDNESDAY + timedelta(days=_RESPONSE_TIME_DAYS), time(8), tzinfo=UTC
    )


async def test_late_raw_material_pushes_the_pickup_of_the_first_position(monkeypatch):
    """The raw material was expected on MONDAY and is not in, so the
    hardening can be picked up no earlier than the day after today."""
    pin_scheduling_clock(monkeypatch, _NOW)
    hardening = _hardening(LotPositionKind.EXTERNAL, sequence=1)
    raw_material_line = _order_item(
        99, expected_delivery_date=MONDAY, line_type=OrderLineType.SOURCE
    )
    recompute, _orders = _recompute(
        _lot(hardening),
        [],
        [_order_item(1, lot_position_id=20), raw_material_line],
        with_raw_material=True,
    )

    await recompute.execute_all()

    assert hardening.planned_pickup_date == WEDNESDAY + timedelta(days=_RESPONSE_TIME_DAYS)
