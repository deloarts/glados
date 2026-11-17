"""
Schedule recompute hooks shared by the write use cases.

recompute_downstream_position_machines decides whether a changed MADE or
SOURCE line's dates warrant a global recompute; update_order_item.py and
mark_order_item_ready_for_pickup.py call it. Completion recording does not,
because it already runs a full recompute itself.

The guard every write use case runs after its own commit,
recompute_schedule_after_commit, and its ScheduleRecompute type live in
schedule_recompute_port.py, since code below Planning & fulfillment runs
it too.
"""

from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.application.services.schedule_recompute_port import (
    recompute_schedule_after_commit,
)


async def recompute_downstream_position_machines(
    position_id: int,
    lot_repo: IProductionLotRepository,
    order_repo: IProductionOrderRepository,
    recompute_schedule: ScheduleRecompute,
) -> None:
    """Runs one global schedule recompute when a live production order sits on
    any position after `position_id` in the lot's sequence. Like
    recompute_schedule_after_commit, it runs after the caller's commit and
    logs a failed walk instead of raising it.

    Every later position counts, not just the next one, because the predecessor
    walk in _context.resolve_predecessor_ready_at follows the whole chain. Which
    machine the order sits on does not matter, since the recompute is global.
    Completed and canceled orders do not count.
    """
    position = await lot_repo.get_position_by_id(position_id)
    if position is None:
        return
    lot = await lot_repo.get_by_id(position.lot_id)
    if lot is None:
        return
    later_position_ids = [p.id for p in lot.positions if p.sequence > position.sequence]
    if not later_position_ids:
        return
    # One query for every later position rather than one per position.
    later_orders = await order_repo.get_by_lot_position_ids(later_position_ids)
    machine_ids: set[int | None] = {
        o.machine_id for o in later_orders if o.status not in TERMINAL_PRODUCTION_ORDER_STATUSES
    }
    if not machine_ids:
        return
    await recompute_schedule_after_commit(
        recompute_schedule,
        after=f"a date change on position #{position_id}; the change itself is committed.",
    )
