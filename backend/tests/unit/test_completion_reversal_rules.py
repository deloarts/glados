"""
assert_completion_reversible: a reversal takes back only pieces that are
still at the position. A reversal itself, a completion reversed already, one
that rejected pieces and one whose pieces the next position already used
are refused; everything else passes. A finished lot is the production order
intent table's refusal (tests/unit/lifecycle/test_intents.py).
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import CompletionAlreadyReversedError
from src.modules.fulfillment.domain.errors import CompletionNotReversibleError
from src.modules.fulfillment.domain.services.production_order_rules import (
    assert_completion_reversible,
)

_COMPLETION = ProductionOrderCompletion(
    id=7,
    production_order_id=1,
    quantity=4.0,
    quantity_accepted=4.0,
    quantity_rejected=0.0,
    completion_date=date(2026, 10, 25),
    note=None,
    operator_id=1,
    recorded_by_id=1,
    created=datetime(2026, 10, 25, tzinfo=UTC),
)


def _check(completion: ProductionOrderCompletion = _COMPLETION, **overrides: object) -> None:
    arguments: dict[str, object] = {
        "reversed_already": False,
        "completed_after": 6.0,
        "used_downstream": 6.0,
    }
    arguments.update(overrides)
    assert_completion_reversible(completion, **arguments)  # type: ignore[arg-type]


def test_pieces_still_at_the_position_can_be_taken_back() -> None:
    _check()


def test_a_reversal_is_not_reversed_again() -> None:
    with pytest.raises(CompletionNotReversibleError, match="a reversal itself"):
        _check(
            replace(_COMPLETION, quantity=-4.0, quantity_accepted=-4.0, reverses_completion_id=3)
        )


def test_a_completion_is_reversed_once() -> None:
    with pytest.raises(CompletionAlreadyReversedError):
        _check(reversed_already=True)


def test_a_completion_that_rejected_pieces_is_refused() -> None:
    rejecting = replace(_COMPLETION, quantity_accepted=3.0, quantity_rejected=1.0)

    with pytest.raises(CompletionNotReversibleError, match="disposition"):
        _check(rejecting)


def test_pieces_the_next_position_already_used_are_refused() -> None:
    with pytest.raises(CompletionNotReversibleError, match="next position"):
        _check(completed_after=6.0, used_downstream=7.0)
