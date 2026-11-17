"""
The quote request rules: the status derived from its intents and line
states, the actions it accepts, the comparison of offers and the plan of an
award, with the alternative items a line or a supplier brings in.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.errors import QuoteRequestActionRefusedError
from src.modules.fulfillment.domain.errors import QuoteRequestInvalidError
from src.modules.fulfillment.domain.errors import QuoteRequestLineNotOpenError
from src.modules.fulfillment.domain.services.lifecycle.quote_request import (
    derive_quote_request_status,
)
from src.modules.fulfillment.domain.services.lifecycle.quote_request import quote_request_facts
from src.modules.fulfillment.domain.services.quote_request_rules import (
    allowed_quote_request_actions,
)
from src.modules.fulfillment.domain.services.quote_request_rules import assert_line_substitutable
from src.modules.fulfillment.domain.services.quote_request_rules import assert_quote_request_action
from src.modules.fulfillment.domain.services.quote_request_rules import cheapest_complete_offer
from src.modules.fulfillment.domain.services.quote_request_rules import cheapest_per_line
from src.modules.fulfillment.domain.services.quote_request_rules import offer_totals
from src.modules.fulfillment.domain.services.quote_request_rules import plan_award
from src.modules.fulfillment.domain.services.quote_request_rules import substitute_of_line_kind
from src.modules.fulfillment.domain.services.quote_request_rules import substitute_reason
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.factories import make_user

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def _buyer(*permissions: str) -> User:
    return make_user(permissions=list(permissions or [Permission.WRITE_ORDERS]))


def _line(line_id: int, quantity: float = 2.0, **values: object) -> QuoteRequestLine:
    return QuoteRequestLine(
        id=line_id,
        quote_request_id=1,
        position=line_id,
        line_type=OrderLineType.VIRTUAL,
        quantity=quantity,
        unit="PCS",
        created=NOW,
        virtual_name=f"Part {line_id}",
        **values,  # type: ignore[arg-type]
    )


def _row(row_id: int, prices: dict[int, int | None], **values: object) -> QuoteRequestSupplier:
    return QuoteRequestSupplier(
        id=row_id,
        quote_request_id=1,
        supplier_id=row_id,
        position=row_id,
        supplier_name=f"Supplier {row_id}",
        quotes=[
            Quote(
                id=0,
                supplier_row_id=row_id,
                line_id=line_id,
                unit_price=price,
                no_offer=price is None,
            )
            for line_id, price in prices.items()
        ],
        **values,  # type: ignore[arg-type]
    )


def _request(lines: list[QuoteRequestLine], rows: list[QuoteRequestSupplier]) -> QuoteRequest:
    request = QuoteRequest(
        id=1,
        request_number="RFQ-1",
        created=NOW,
        changed=None,
        changes=[],
        status=QuoteRequestStatus.DRAFT,
        creator_id=1,
        lines=lines,
        suppliers=rows,
    )
    _derive(request)
    return request


def _derive(request: QuoteRequest) -> None:
    """Stores the derived status, as the lifecycle reconciler does."""
    request.status = derive_quote_request_status(quote_request_facts(request)).value


@pytest.mark.parametrize(
    ("lines", "rows", "intents", "status"),
    [
        ([_line(1)], [_row(1, {})], {}, "draft"),
        ([_line(1)], [_row(1, {}, sent_at=NOW)], {}, "sent"),
        ([_line(1, awarded_at=NOW), _line(2, dropped_at=NOW)], [], {}, "awarded"),
        ([_line(1, awarded_at=NOW), _line(2)], [_row(1, {}, sent_at=NOW)], {}, "sent"),
        ([_line(1, dropped_at=NOW)], [], {}, "closed"),
        ([_line(1)], [], {"closed_at": NOW}, "closed"),
        ([_line(1, awarded_at=NOW)], [], {"canceled_at": NOW}, "canceled"),
    ],
    ids=["draft", "sent", "awarded", "partly_awarded", "all_dropped", "closed", "canceled"],
)
def test_quote_request_status_follows_its_intents_and_lines(
    lines: list[QuoteRequestLine],
    rows: list[QuoteRequestSupplier],
    intents: dict[str, datetime],
    status: str,
) -> None:
    request = _request(lines, rows)
    for name, value in intents.items():
        setattr(request, name, value)

    _derive(request)

    assert request.status == status


def test_quote_request_actions_need_lines_suppliers_and_awards() -> None:
    empty = _request([], [])
    open_request = _request([_line(1)], [_row(1, {})])
    awarded = _request([_line(1, awarded_at=NOW), _line(2)], [_row(1, {})])

    assert allowed_quote_request_actions(empty, _buyer()) == ["cancel"]
    assert allowed_quote_request_actions(open_request, _buyer()) == ["send", "award", "cancel"]
    assert allowed_quote_request_actions(awarded, _buyer()) == ["send", "award", "close"]
    assert allowed_quote_request_actions(open_request, _buyer("read:orders")) == []
    with pytest.raises(QuoteRequestActionRefusedError):
        assert_quote_request_action(LifecycleAction.CANCEL, awarded, _buyer())


def _closed(*lines: QuoteRequestLine) -> QuoteRequest:
    request = _request(list(lines), [_row(1, {}, sent_at=NOW)])
    request.closed_at = NOW
    _derive(request)
    return request


def test_quote_request_reopen_needs_a_recorded_close_and_a_voided_open_line() -> None:
    voided = _closed(_line(1, awarded_at=NOW, award_live=False), _line(2, dropped_at=NOW))
    live = _closed(_line(1, awarded_at=NOW), _line(2, dropped_at=NOW))
    voided_then_dropped = _closed(
        _line(1, awarded_at=NOW, award_live=False, dropped_at=NOW), _line(2, awarded_at=NOW)
    )
    all_dropped = _request([_line(1, awarded_at=NOW, award_live=False, dropped_at=NOW)], [])
    canceled = _request([_line(1, awarded_at=NOW, award_live=False)], [])
    canceled.canceled_at = NOW
    _derive(canceled)

    assert voided.status == "closed"
    assert allowed_quote_request_actions(voided, _buyer()) == ["reopen"]
    assert allowed_quote_request_actions(voided, _buyer("read:orders")) == []
    for request in (live, voided_then_dropped, all_dropped, canceled):
        assert "reopen" not in allowed_quote_request_actions(request, _buyer())
        with pytest.raises(QuoteRequestActionRefusedError):
            assert_quote_request_action(LifecycleAction.REOPEN, request, _buyer())


def test_quote_request_compares_lines_and_whole_offers() -> None:
    lines = [_line(1, quantity=2.0), _line(2, quantity=1.0)]
    cheap_lines = _row(1, {1: 100, 2: 500})
    cheap_total = _row(
        2,
        {1: 150, 2: 300},
        extra_costs=[
            QuoteExtraCost(
                id=0, supplier_row_id=2, kind=ExtraCostKind.DISCOUNT, amount=50, position=1
            )
        ],
    )
    partial = _row(3, {1: 50})
    request = _request(lines, [cheap_lines, cheap_total, partial])

    assert cheapest_per_line(request) == {1: 3, 2: 2}
    assert offer_totals(request, cheap_total).total == 550
    assert offer_totals(request, cheap_lines).total == 700
    assert cheapest_complete_offer(request) == 2


def test_quote_request_award_plan_groups_lines_by_winner() -> None:
    lines = [_line(1), _line(2), _line(3)]
    request = _request(lines, [_row(1, {1: 100, 2: 200}), _row(2, {3: 300})])

    plan = plan_award(request, {3: 2, 1: 1, 2: 1})

    assert list(plan) == [1, 2]
    assert [(a.line.id, a.unit_price) for a in plan[1]] == [(1, 100), (2, 200)]
    assert [(a.line.id, a.unit_price) for a in plan[2]] == [(3, 300)]


def test_quote_request_award_plan_refuses_a_declined_or_decided_line() -> None:
    request = _request([_line(1), _line(2, dropped_at=NOW)], [_row(1, {1: None})])

    with pytest.raises(QuoteRequestInvalidError):
        plan_award(request, {1: 1})
    with pytest.raises(QuoteRequestLineNotOpenError):
        plan_award(request, {2: 1})


def _bought_line(line_id: int, **values: object) -> QuoteRequestLine:
    line = _line(line_id, **values)
    line.line_type = OrderLineType.BOUGHT
    line.virtual_name = None
    line.bought_item_id = 10
    return line


def test_quote_request_award_plan_takes_the_winners_alternative() -> None:
    alternative = Quote(
        id=0,
        supplier_row_id=1,
        line_id=1,
        unit_price=90,
        substitute_bought_item_id=11,
        substitute_reason="Discontinued.",
    )
    alternative_row = _row(1, {})
    alternative_row.quotes = [alternative]
    rows = [alternative_row, _row(2, {1: 100})]
    request = _request([_bought_line(1)], rows)

    [by_alternative] = plan_award(request, {1: 1})[1]
    [by_own_item] = plan_award(request, {1: 2})[2]

    assert cheapest_per_line(request) == {1: 1}
    assert (by_alternative.bought_item_id, by_alternative.substitute_reason) == (
        11,
        "Discontinued.",
    )
    assert (by_own_item.bought_item_id, by_own_item.substitute_reason) == (10, None)


def test_quote_request_award_plan_carries_a_replacement_lines_reason() -> None:
    request = _request([_bought_line(1, substitute_reason="Stainless.")], [_row(1, {1: 50})])

    [award] = plan_award(request, {1: 1})[1]

    assert (award.bought_item_id, award.substitute_reason) == (10, "Stainless.")


def test_quote_request_substitute_must_fit_the_line() -> None:
    sourced = _bought_line(
        1,
        demands=[
            QuoteRequestLineDemand(
                id=1,
                line_id=1,
                family=QuoteRequestDemandFamily.SOURCE,
                demand_item_id=5,
                quantity=1,
            )
        ],
    )

    assert substitute_of_line_kind(_bought_line(2), 11, None) == 11
    with pytest.raises(QuoteRequestInvalidError):
        substitute_of_line_kind(_bought_line(2), None, 11)
    with pytest.raises(QuoteRequestInvalidError):
        assert_line_substitutable(_line(3))
    with pytest.raises(QuoteRequestInvalidError):
        assert_line_substitutable(sourced)
    assert substitute_reason("  ") is None
    assert substitute_reason(" Stainless. ") == "Stainless."
