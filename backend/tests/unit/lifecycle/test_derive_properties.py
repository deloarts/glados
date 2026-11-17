"""Property tests of the lifecycle derivations and intent tables with
Hypothesis: each derivation is pure (its facts are unchanged afterwards),
deterministic (equal facts give equal results), total (any facts, including
negative, infinite and NaN quantities, give a value of the right enum without
raising), and reports the first row whose condition holds. The intent tables
are deterministic and `check` agrees with `allowed_actions`."""

import copy
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from enum import Enum

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.intents import DEMAND_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import DemandContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotPositionContext
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemContext
from src.modules.fulfillment.domain.services.lifecycle.intents import ProductionOrderContext
from src.modules.fulfillment.domain.services.lifecycle.lot import LOT_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot import derive_lot_status
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_KIND
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot_position import derive_position_kind
from src.modules.fulfillment.domain.services.lifecycle.lot_position import derive_position_status
from src.modules.fulfillment.domain.services.lifecycle.order import ORDER_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order import derive_order_status
from src.modules.fulfillment.domain.services.lifecycle.order_item import ORDER_ITEM_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order_item import derive_order_item_status
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    PRODUCTION_ORDER_STATUS,
)
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    derive_production_order_status,
)
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit.lifecycle import strategies as s


@dataclass(frozen=True)
class _Derivation:
    """One derivation under test: its function, its table, the enum it
    returns, and how to build facts from a quantity strategy."""

    name: str
    derive: Callable[[object], Derivation[Enum]]
    table: DerivationTable[object, Enum]
    enum: type[Enum]
    facts: Callable[[s.FloatStrategy], st.SearchStrategy[object]]


DERIVATIONS = [
    _Derivation(
        "order_item",
        derive_order_item_status,
        ORDER_ITEM_STATUS,
        OrderItemStatus,
        s.order_item_facts,
    ),
    _Derivation(
        "order", derive_order_status, ORDER_STATUS, OrderStatus, lambda _q: s.order_facts()
    ),
    _Derivation(
        "production_order",
        derive_production_order_status,
        PRODUCTION_ORDER_STATUS,
        ProductionOrderStatus,
        s.production_order_facts,
    ),
    _Derivation(
        "position_kind", derive_position_kind, POSITION_KIND, LotPositionKind, s.lot_position_facts
    ),
    _Derivation(
        "position_status",
        derive_position_status,
        POSITION_STATUS,
        LotPositionStatus,
        s.lot_position_facts,
    ),
    _Derivation("lot", derive_lot_status, LOT_STATUS, LotStatus, s.lot_facts),
    _Derivation(
        "bought_demand",
        BOUGHT_DEMAND_STATUS.derive,
        BOUGHT_DEMAND_STATUS,
        BoughtItemDemandStatus,
        s.demand_facts,
    ),
    _Derivation(
        "made_demand",
        MADE_DEMAND_STATUS.derive,
        MADE_DEMAND_STATUS,
        MadeItemDemandStatus,
        s.demand_facts,
    ),
    _Derivation(
        "source_demand",
        SOURCE_DEMAND_STATUS.derive,
        SOURCE_DEMAND_STATUS,
        SourceItemDemandStatus,
        s.demand_facts,
    ),
]
_IDS = [d.name for d in DERIVATIONS]


@pytest.mark.parametrize("case", DERIVATIONS, ids=_IDS)
@given(data=st.data())
def test_derivation_is_pure_and_deterministic(case, data):
    facts = data.draw(case.facts(s.quantities))
    before = copy.deepcopy(facts)
    first = case.derive(facts)
    assert case.derive(facts) == first
    assert case.derive(copy.deepcopy(facts)) == first
    assert facts == before


@pytest.mark.parametrize("case", DERIVATIONS, ids=_IDS)
@given(data=st.data())
def test_derivation_reports_the_first_row_that_holds(case, data):
    facts = data.draw(case.facts(s.quantities))
    derivation = case.derive(facts)
    expected = next((row for row in case.table.rules if row.applies(facts)), case.table.fallback)
    assert derivation.rule == expected.number
    assert derivation.value in expected.results


@pytest.mark.parametrize("case", DERIVATIONS, ids=_IDS)
@given(data=st.data())
def test_derivation_is_total_over_any_quantities(case, data):
    facts = data.draw(case.facts(s.wild_quantities))
    derivation = case.derive(facts)
    assert isinstance(derivation.value, case.enum)
    assert derivation.rule in {row.number for row in case.table.rows}


# ── What the tables promise for every input ─────────────────────────────


@given(s.order_item_facts())
def test_a_canceled_order_item_is_canceled(facts):
    assert (derive_order_item_status(facts).value == OrderItemStatus.CANCELED) == (
        facts.canceled_at is not None
    )


@given(s.order_facts())
def test_a_canceled_order_stays_canceled_whatever_its_lines(facts):
    if facts.canceled_at is not None:
        assert derive_order_status(facts).value == OrderStatus.CANCELED


@given(s.production_order_facts())
def test_a_canceled_production_order_is_canceled(facts):
    assert (derive_production_order_status(facts).value == ProductionOrderStatus.CANCELED) == (
        facts.canceled_at is not None
    )


@given(s.lot_position_facts())
def test_a_position_is_canceled_exactly_when_its_lot_is(facts):
    assert (derive_position_status(facts).value == LotPositionStatus.CANCELED) == facts.lot_canceled


@given(s.lot_facts())
def test_a_canceled_lot_is_canceled_and_a_zero_lot_is_scrapped(facts):
    status = derive_lot_status(facts).value
    if facts.canceled_at is not None:
        assert status == LotStatus.CANCELED
    elif facts.quantity == 0.0:
        assert status == LotStatus.SCRAPPED


@given(s.demand_facts())
def test_demand_intents_win_over_the_allocations(facts):
    status = BOUGHT_DEMAND_STATUS.derive(facts).value
    if facts.canceled_at is not None:
        assert status == BoughtItemDemandStatus.CANCELED
    elif facts.fulfilled_manually_at is not None:
        assert status == BoughtItemDemandStatus.FULFILLED


# ── Intent tables ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Subject:
    status: str
    line_type: str = OrderLineType.BOUGHT.value
    quantity_delivered: float = 0.0
    quantity_rejected: float = 0.0
    quantity_rejected_lost: float = 0.0
    kind: str = LotPositionKind.UNASSIGNED.value
    creator_id: int = 1
    closed_short_at: datetime | None = None
    canceled_at: datetime | None = None


def _actor(user_id: int, permissions: list[str]) -> User:
    return User(
        id=user_id,
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        email=f"user{user_id}@example.com",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=permissions,
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


actors = st.builds(
    _actor,
    st.integers(min_value=1, max_value=3),
    st.lists(st.sampled_from([Permission.MANAGE_ORDERS, Permission.MANAGE_LOTS]), unique=True),
)


def _subjects(statuses: type[Enum], q: s.FloatStrategy) -> st.SearchStrategy[_Subject]:
    return st.builds(
        _Subject,
        status=st.sampled_from([str(m.value) for m in statuses]),
        line_type=st.sampled_from([t.value for t in OrderLineType]),
        quantity_delivered=q,
        quantity_rejected=q,
        quantity_rejected_lost=q,
        kind=st.sampled_from([k.value for k in LotPositionKind]),
        closed_short_at=st.sampled_from([None, datetime(2026, 1, 1, tzinfo=UTC)]),
        creator_id=st.integers(min_value=1, max_value=3),
        canceled_at=st.sampled_from([None, datetime(2026, 1, 1, tzinfo=UTC)]),
    )


def _intent_cases(q: s.FloatStrategy) -> list[tuple[object, st.SearchStrategy, st.SearchStrategy]]:
    """Each intent table with strategies for its subjects and contexts."""
    return [
        (
            ORDER_ITEM_INTENTS,
            _subjects(OrderItemStatus, q),
            st.builds(
                OrderItemContext,
                order_status=st.sampled_from(OrderStatus),
                lot_canceled=st.booleans(),
                target_order_canceled=st.booleans(),
            ),
        ),
        (ORDER_INTENTS, _subjects(OrderStatus, q), st.none()),
        (
            PRODUCTION_ORDER_INTENTS,
            _subjects(ProductionOrderStatus, q),
            st.builds(
                ProductionOrderContext,
                lot_held=st.booleans(),
                lot_terminal=st.booleans(),
                machine_resolvable=st.booleans(),
                input_available=st.booleans(),
                open_interruption=st.one_of(st.none(), st.sampled_from(InterruptionReason)),
            ),
        ),
        (
            LOT_POSITION_INTENTS,
            _subjects(LotPositionStatus, q),
            st.builds(
                LotPositionContext,
                live_line_status=st.one_of(st.none(), st.sampled_from(OrderItemStatus)),
                remaining=q,
                lot_terminal=st.booleans(),
            ),
        ),
        (LOT_INTENTS, _subjects(LotStatus, q), st.builds(LotContext, produced=q)),
        (
            DEMAND_INTENTS,
            _subjects(BoughtItemDemandStatus, q),
            st.builds(DemandContext, has_allocations=st.booleans()),
        ),
    ]


INTENT_CASES = _intent_cases(s.quantities)
WILD_INTENT_CASES = _intent_cases(s.wild_quantities)
_INTENT_IDS = [case[0].key for case in INTENT_CASES]


@pytest.mark.parametrize(("table", "subjects", "contexts"), INTENT_CASES, ids=_INTENT_IDS)
@given(data=st.data())
def test_intent_table_is_pure_and_deterministic_and_check_agrees(table, subjects, contexts, data):
    subject = data.draw(subjects)
    context = data.draw(contexts)
    actor = data.draw(actors)
    before = (copy.deepcopy(subject), copy.deepcopy(context))
    allowed = table.allowed_actions(subject, context, actor)
    assert table.allowed_actions(copy.deepcopy(subject), copy.deepcopy(context), actor) == allowed
    for rule in table.rules:
        assert (table.check(rule.action, subject, context, actor) is None) == (
            rule.action in allowed
        )
    assert (subject, context) == before


@pytest.mark.parametrize(("table", "subjects", "contexts"), WILD_INTENT_CASES, ids=_INTENT_IDS)
@given(data=st.data())
def test_intent_table_is_total_over_any_quantities(table, subjects, contexts, data):
    subject = data.draw(subjects)
    context = data.draw(contexts)
    actor = data.draw(actors)
    allowed = table.allowed_actions(subject, context, actor)
    assert set(allowed) <= {rule.action for rule in table.rules}
