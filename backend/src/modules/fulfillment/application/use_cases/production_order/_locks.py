"""Row locks for a write to a production order, shared by its lifecycle use
cases so all of them take them in the same order: the order's lot first,
then the order, through the request's lock plan. Nothing here commits.
"""

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.services.lot_cascades import lot_work_lock_targets
from src.modules.fulfillment.application.services.time_budget_propagation import budget_order_locks
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise


async def lock_lot_and_order(
    reconciler: LifecycleReconciler,
    lot_repo: IProductionLotRepository,
    order_repo: IProductionOrderRepository,
    position: LotPosition,
    production_order_id: int,
    *,
    lot_work: IOrderItemRepository | None = None,
    budget_orders: bool = False,
) -> tuple[ProductionLot, ProductionOrder, LotPosition]:
    """Registers the order with the reconciler, locks the lot of `position`
    and then the order through the reconciler's lock plan, and returns the
    lot, the order and the lot's own object for the position, all read
    again under the locks.

    With `lot_work`, the order line repository, the write may be followed by
    a disposition, which cuts or cancels the lot's other production orders
    and order lines: the lot is then locked alone first, and its production
    orders and live lines with their orders are locked together with the
    order, in the acquisition after it, since the lock order puts every
    production order before any order or line; the demands a disposition
    may write join that acquisition (lot_work_lock_targets). With
    `budget_orders` as well, a disposition that shrinks the lot recomputes
    its project's time budgets, so the project's queued and paused orders,
    whose duration that recompute may snapshot again, join it too.

    The reads refresh what the session already held, so the caller checks
    and writes only what this returns, never the copies it read to find the
    lot. Every write to a production order of one lot then serializes on
    the lot, its checks and totals are read after both locks, and a
    disposition shrinks the same position object the caller updates."""
    the_lot = AggregateIds.of({LifecycleAggregate.LOTS: [position.lot_id]})
    if lot_work is None:
        reconciler.touch_production_orders([production_order_id])
        await reconciler.lock_touched(also=the_lot)
        lot = await lot_repo.get_by_id_for_update(position.lot_id)
    else:
        await reconciler.lock_touched(also=the_lot)
        lot = await lot_repo.get_by_id_for_update(position.lot_id)
        work = AggregateIds()
        if lot:
            work = await lot_work_lock_targets(reconciler, lot, order_repo, lot_work)
            if budget_orders:
                work = work.union(await budget_order_locks([lot.project_id], lot_repo, order_repo))
        reconciler.touch_production_orders([production_order_id])
        await reconciler.lock_touched(also=work)
    if not lot:
        raise LotNotFoundError(f"Lot #{position.lot_id} not found.")
    order = found_or_raise(
        await order_repo.get_by_id_for_update(production_order_id),
        ProductionOrderNotFoundError,
        f"Production order #{production_order_id} not found.",
    )
    locked_position = next((p for p in lot.positions if p.id == position.id), None)
    if locked_position is None:
        raise LotPositionNotFoundError(f"Position #{position.id} not found on lot #{lot.id}.")
    return lot, order, locked_position
