"""
The locks of an allocation writer. An allocation write checks the capacity
of the order line or lot it allocates on and the open quantity and state of
its demand, so it locks the line or lot and then the demand before it reads
what it checks, in one acquisition through the request's lock plan
(lifecycle_lock_plan.py), which puts lots and lines before every demand.
The demand is touched with the reconciler first, so the reconciler's own
locks are part of that acquisition and its run finds them held.

The writers keep their repositories' locked reads after this call, as reads
of the current rows; a lock the transaction already holds is not taken
again.
"""

from collections.abc import Iterable

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate


async def lock_for_allocation(
    reconciler: LifecycleReconciler,
    family: LifecycleAggregate,
    demand_ids: Iterable[int],
    *,
    order_item_ids: Iterable[int] = (),
    lot_ids: Iterable[int] = (),
) -> None:
    """Touches the demands of one family and locks the given lines and lots
    together with them, in the one lock order. Every demand allocated on
    those lines and lots is locked and derived too
    (LifecycleReconciler.touch_allocations_on)."""
    order_item_ids = list(order_item_ids)
    lot_ids = list(lot_ids)
    reconciler.touch_demands(family, list(demand_ids))
    reconciler.touch_allocations_on(order_item_ids=order_item_ids, lot_ids=lot_ids)
    await reconciler.lock_touched(
        also=AggregateIds.of(
            {
                LifecycleAggregate.ORDER_ITEMS: list(order_item_ids),
                LifecycleAggregate.LOTS: list(lot_ids),
            }
        )
    )
