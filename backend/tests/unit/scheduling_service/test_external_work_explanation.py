"""The terms the procurement list shows on hover for the three dates of a
position of external work, and that they end on the dates the schedule walk
stores, so the tooltip never explains a different date than the cell shows."""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    DateTermKind,
)
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    ExplanationInputs,
)
from src.modules.fulfillment.domain.services.scheduling.external_work_explanation import (
    explain_external_work,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit.scheduling_service.test_external_work_forecasts import _BEFORE_THE_FIXTURES
from tests.unit.scheduling_service.test_external_work_forecasts import _hardening
from tests.unit.scheduling_service.test_external_work_forecasts import _hardening_line
from tests.unit.scheduling_service.test_external_work_forecasts import _inspection
from tests.unit.scheduling_service.test_external_work_forecasts import _inspection_order
from tests.unit.scheduling_service.test_external_work_forecasts import _lot
from tests.unit.scheduling_service.test_external_work_forecasts import _milling
from tests.unit.scheduling_service.test_external_work_forecasts import _milling_order
from tests.unit.scheduling_service.test_external_work_forecasts import _recompute

_TARGET = date(2026, 8, 20)


def _inputs(target: date | None = _TARGET, demand_id: int | None = None) -> ExplanationInputs:
    return ExplanationInputs(
        target_date=target,
        target_demand_id=demand_id,
        response_time_days=1,
        safety_margin_days=2,
        default_external_lead_days=3,
        zone=UTC,
        today=_BEFORE_THE_FIXTURES.date(),
    )


def _scenario():
    """Milling done on Monday the 3rd, hardening (4 days) without a
    supplier date, QA of 20 minutes, the lot due on the 20th."""
    milling, hardening, inspection = _milling(), _hardening(LotPositionKind.EXTERNAL), _inspection()
    milling_order = _milling_order()
    milling_order.planned_end = datetime(2026, 8, 3, 11, 20, tzinfo=UTC)
    milling.production_orders = [milling_order]
    inspection.production_orders = [_inspection_order()]
    lot = _lot(milling, hardening, inspection)
    lot.required_delivery_date = _TARGET
    return lot, hardening


def _kinds(terms) -> list[str]:
    return [term.kind.value for term in terms]


def test_ready_from_is_the_step_before_plus_the_response_time():
    lot, hardening = _scenario()

    terms = explain_external_work(hardening, lot, _inputs(), ready_now=False).ready_from

    assert _kinds(terms) == ["after_step", "response_time", "result"]
    assert terms[0].date == date(2026, 8, 3)
    assert len(terms[0].methods) == 1
    assert terms[1].days == 1
    assert terms[2].date == date(2026, 8, 4)


def test_latest_pickup_counts_back_over_margin_later_steps_and_lead_time():
    lot, hardening = _scenario()

    terms = explain_external_work(hardening, lot, _inputs(), ready_now=False).latest_pickup

    assert _kinds(terms) == [
        "target_lot",
        "safety_margin",
        "later_step",
        "back_by",
        "lead_time",
        "result",
    ]
    assert terms[0].date == _TARGET
    assert terms[1].days == 2
    assert (terms[2].days, terms[2].minutes) == (1, 20)
    assert terms[3].date == date(2026, 8, 17)
    assert (terms[4].days, terms[4].source) == (4, "method")
    assert terms[5].date == date(2026, 8, 13)


def test_a_demand_target_names_the_demand():
    lot, hardening = _scenario()

    terms = explain_external_work(
        hardening, lot, _inputs(demand_id=7), ready_now=False
    ).latest_pickup

    assert terms[0].kind == DateTermKind.TARGET_DEMAND
    assert terms[0].reference == "7"


def test_back_by_is_the_supplier_date_once_the_line_has_one():
    lot, hardening = _scenario()
    hardening.order_item_id = 1
    hardening.order_number = "ORD-26-00007"
    hardening.expected_delivery_date = date(2026, 8, 12)

    terms = explain_external_work(hardening, lot, _inputs(), ready_now=False).back_by

    assert _kinds(terms) == ["supplier_date"]
    assert (terms[0].date, terms[0].reference) == (date(2026, 8, 12), "ORD-26-00007")


def test_back_by_without_a_supplier_date_is_the_latest_pickup_plus_the_lead_time():
    lot, hardening = _scenario()
    hardening.latest_pickup_date = date(2026, 8, 13)

    terms = explain_external_work(hardening, lot, _inputs(), ready_now=False).back_by

    assert _kinds(terms) == ["latest_pickup", "lead_time", "result"]
    assert terms[2].date == date(2026, 8, 17)


def test_a_lot_without_a_target_date_explains_no_latest_pickup():
    lot, hardening = _scenario()

    explanation = explain_external_work(hardening, lot, _inputs(target=None), ready_now=False)

    assert explanation.latest_pickup == ()
    assert explanation.back_by == ()


def test_terms_that_miss_the_stored_date_mark_the_explanation_stale():
    lot, hardening = _scenario()
    hardening.planned_pickup_date = date(2026, 8, 4)
    hardening.latest_pickup_date = date(2026, 8, 13)
    assert explain_external_work(hardening, lot, _inputs(), ready_now=False).stale is False

    hardening.latest_pickup_date = date(2026, 8, 12)
    assert explain_external_work(hardening, lot, _inputs(), ready_now=False).stale is True


async def test_the_explanation_ends_on_the_dates_the_walk_stores(monkeypatch):
    """The walk dates the lot; the explanation, read from the same data,
    lands on the very same days."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    milling, hardening, inspection = _milling(), _hardening(LotPositionKind.EXTERNAL), _inspection()
    lot = _lot(milling, hardening, inspection)
    lot.required_delivery_date = _TARGET
    recompute, orders = _recompute(
        lot, [_milling_order(), _inspection_order()], [_hardening_line()]
    )

    await recompute.execute_all()
    # The read model hands each position its orders.
    for position in lot.positions:
        position.production_orders = [
            o for o in orders.orders.values() if o.lot_position_id == position.id
        ]

    explanation = explain_external_work(hardening, lot, _inputs(), ready_now=False)

    assert explanation.stale is False
    assert explanation.ready_from[-1].date == hardening.planned_pickup_date
    assert explanation.latest_pickup[-1].date == hardening.latest_pickup_date
    assert hardening.latest_delivery_date == hardening.latest_pickup_date + timedelta(days=4)


async def test_the_explanation_counts_the_waits_as_the_walk_does(monkeypatch):
    """The milling's pieces cure a day before they can leave, and the QA
    check after the hardening waits two days for its result: the walk and
    the explanation count both waits alike."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    milling, hardening, inspection = _milling(), _hardening(LotPositionKind.EXTERNAL), _inspection()
    milling.steps[0].method_wait_after_minutes = 1440
    inspection.steps[0].method_wait_after_minutes = 2000
    lot = _lot(milling, hardening, inspection)
    lot.required_delivery_date = _TARGET
    recompute, orders = _recompute(
        lot, [_milling_order(), _inspection_order()], [_hardening_line()]
    )

    await recompute.execute_all()
    for position in lot.positions:
        position.production_orders = [
            o for o in orders.orders.values() if o.lot_position_id == position.id
        ]

    explanation = explain_external_work(hardening, lot, _inputs(), ready_now=False)

    assert explanation.stale is False
    milling_end = orders.orders[1].planned_end
    assert milling_end is not None
    # Ready a day after the milling ends, plus the day of response time.
    assert explanation.ready_from[0].date == milling_end.date() + timedelta(days=1)
    assert hardening.planned_pickup_date == milling_end.date() + timedelta(days=2)
    waits = [t for t in explanation.latest_pickup if t.kind == DateTermKind.WAIT_AFTER]
    assert [(t.days, t.minutes) for t in waits] == [(2, 2000)]
    assert explanation.latest_pickup[-1].date == hardening.latest_pickup_date
