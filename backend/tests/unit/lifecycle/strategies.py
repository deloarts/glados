"""Hypothesis strategies for lifecycle facts.

`quantities` mixes the fractional values that expose rounding (0.1, 0.7, a
hair below one) with arbitrary non-negative floats; `wild_quantities` adds
negative, infinite and NaN values, which a derivation must survive without
raising although valid facts never hold them.
"""

from datetime import UTC
from datetime import datetime

from hypothesis import strategies as st

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

FloatStrategy = st.SearchStrategy[float]

quantities: FloatStrategy = st.one_of(
    st.sampled_from([0.0, 0.1, 0.2, 0.3, 0.7, 1.0 - 1e-7, 1.0, 2.0, 10.0]),
    st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
wild_quantities: FloatStrategy = st.one_of(quantities, st.floats())

intents = st.one_of(
    st.none(),
    st.datetimes(
        min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1), timezones=st.just(UTC)
    ),
)


def order_item_facts(q: FloatStrategy = quantities) -> st.SearchStrategy[OrderItemFacts]:
    return st.builds(
        OrderItemFacts,
        quantity=q,
        delivered=q,
        lost=q,
        requested_at=intents,
        ordered_date=intents,
        canceled_at=intents,
    )


def order_facts() -> st.SearchStrategy[OrderFacts]:
    return st.builds(
        OrderFacts,
        requested_at=intents,
        ordered_date=intents,
        canceled_at=intents,
        line_statuses=st.lists(st.sampled_from(OrderItemStatus), max_size=5).map(tuple),
    )


def production_order_facts(
    q: FloatStrategy = quantities,
) -> st.SearchStrategy[ProductionOrderFacts]:
    return st.builds(
        ProductionOrderFacts,
        quantity=q,
        processed=q,
        actual_start=intents,
        canceled_at=intents,
        open_interruption=st.one_of(st.none(), st.sampled_from(InterruptionReason)),
    )


def lot_position_facts(q: FloatStrategy = quantities) -> st.SearchStrategy[LotPositionFacts]:
    line = st.builds(
        PositionLineFacts, status=st.sampled_from(OrderItemStatus), quantity=q, delivered=q
    )
    order = st.builds(
        PositionOrderFacts,
        status=st.sampled_from(ProductionOrderStatus),
        quantity=q,
        quantity_completed=q,
    )
    return st.builds(
        LotPositionFacts,
        quantity=q,
        line=st.one_of(st.none(), line),
        orders=st.lists(order, max_size=4).map(tuple),
        lot_canceled=st.booleans(),
    )


def lot_facts(q: FloatStrategy = quantities) -> st.SearchStrategy[LotFacts]:
    return st.builds(
        LotFacts,
        quantity=q,
        position_statuses=st.lists(st.sampled_from(LotPositionStatus), max_size=5).map(tuple),
        held_at=intents,
        canceled_at=intents,
        force_completed_at=intents,
    )


def allocation_facts(q: FloatStrategy = quantities) -> st.SearchStrategy[AllocationFacts]:
    line = st.builds(
        CoveringLineFacts,
        status=st.sampled_from(OrderItemStatus),
        quantity=q,
        delivered=q,
        lost=q,
    )
    lot = st.builds(
        CoveringLotFacts, status=st.sampled_from(LotStatus), quantity=q, quantity_completed=q
    )
    return st.one_of(
        q.map(AllocationFacts.stock),
        st.builds(AllocationFacts.on_line, q, line),
        st.builds(AllocationFacts.on_lot, q, lot),
        q.map(
            lambda quantity: AllocationFacts(
                quantity=quantity, from_stock=False, line=None, lot=None
            )
        ),
    )


def demand_facts(q: FloatStrategy = quantities) -> st.SearchStrategy[DemandFacts]:
    return st.builds(
        DemandFacts,
        quantity=q,
        allocations=st.lists(allocation_facts(q), max_size=4).map(tuple),
        canceled_at=intents,
        fulfilled_manually_at=intents,
    )
