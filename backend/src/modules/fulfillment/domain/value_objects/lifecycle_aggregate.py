"""The aggregates whose lifecycle status is derived from facts and intents.

Each member's value is the plural table name the lifecycle drift report
prints and its `--only` option accepts. LIFECYCLE_INPUTS lists, for each
aggregate, the other aggregates its derivation reads, and DEPENDENTS the
reverse: the aggregates whose derived value reads it. The reconciler widens
a touched set along DEPENDENTS only, so it recomputes exactly what a change
can alter.
"""

from collections.abc import Mapping
from enum import Enum
from enum import unique


@unique
class LifecycleAggregate(str, Enum):
    """A lifecycle aggregate, named as the drift report names its table."""

    ORDER_ITEMS = "order_items"
    ORDERS = "orders"
    PRODUCTION_ORDERS = "production_orders"
    LOT_POSITIONS = "lot_positions"
    LOTS = "lots"
    BOUGHT_DEMANDS = "bought_demands"
    MADE_DEMANDS = "made_demands"
    SOURCE_DEMANDS = "source_demands"
    QUOTE_REQUESTS = "quote_requests"


DEMAND_AGGREGATES: tuple[LifecycleAggregate, ...] = (
    LifecycleAggregate.BOUGHT_DEMANDS,
    LifecycleAggregate.MADE_DEMANDS,
    LifecycleAggregate.SOURCE_DEMANDS,
)

# What a derivation reads besides the aggregate's own row. A lot position
# reads its lot because a canceled lot cancels its positions; a lot reads
# the derived statuses of its positions; a quote request reads whether the
# order lines its awards created are still live.
LIFECYCLE_INPUTS: Mapping[LifecycleAggregate, frozenset[LifecycleAggregate]] = {
    LifecycleAggregate.ORDER_ITEMS: frozenset(),
    LifecycleAggregate.ORDERS: frozenset({LifecycleAggregate.ORDER_ITEMS}),
    LifecycleAggregate.PRODUCTION_ORDERS: frozenset(),
    LifecycleAggregate.LOT_POSITIONS: frozenset(
        {
            LifecycleAggregate.ORDER_ITEMS,
            LifecycleAggregate.PRODUCTION_ORDERS,
            LifecycleAggregate.LOTS,
        }
    ),
    LifecycleAggregate.LOTS: frozenset({LifecycleAggregate.LOT_POSITIONS}),
    LifecycleAggregate.BOUGHT_DEMANDS: frozenset({LifecycleAggregate.ORDER_ITEMS}),
    LifecycleAggregate.MADE_DEMANDS: frozenset({LifecycleAggregate.LOTS}),
    LifecycleAggregate.SOURCE_DEMANDS: frozenset({LifecycleAggregate.ORDER_ITEMS}),
    LifecycleAggregate.QUOTE_REQUESTS: frozenset({LifecycleAggregate.ORDER_ITEMS}),
}

DEPENDENTS: Mapping[LifecycleAggregate, frozenset[LifecycleAggregate]] = {
    aggregate: frozenset(
        reader for reader, inputs in LIFECYCLE_INPUTS.items() if aggregate in inputs
    )
    for aggregate in LifecycleAggregate
}
