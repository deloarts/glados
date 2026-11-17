"""
Shared ProductionOrder construction, used by the manual internal-assignment
flow (AssignInternalPosition, caller-supplied machine/pool per order) and by
the auto-queuing call site (CreateLot, born-internal QA inspection
positions), keeps the entity shape and the order-number/queue-sequence
sourcing in one place.
"""

from datetime import datetime

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_order_rules import (
    compute_estimated_duration_minutes,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.changelog_service import append_changelog


async def build_queued_production_order(
    actor: User,
    position: LotPosition,
    quantity: float,
    priority: UrgencyClass,
    *,
    machine_id: int | None,
    machine_pool_id: int | None,
    order_repo: IProductionOrderRepository,
    number_template: str,
    now: datetime,
    changelog_note: str,
) -> ProductionOrder:
    """Builds and persists (no_commit) one QUEUED ProductionOrder against a
    lot position. Caller owns the transaction (commits, events, schedule
    recompute, position.kind flip)."""
    estimated_duration = compute_estimated_duration_minutes(position.steps, quantity)
    order = ProductionOrder(
        id=0,
        created=now,
        changed=now,
        changes=append_changelog([], actor.full_name, changelog_note),
        production_order_number=await order_repo.next_production_order_number(number_template),
        status=ProductionOrderStatus.default(),
        priority=priority,
        pinned=False,
        # Pool-scoped when this order is being queued straight onto a pool
        # (machine_id None, machine_pool_id set), part of pool-first planning:
        # without the pool scope here, a freshly pool-assigned
        # order would draw its queue_sequence from the shared
        # no-machine-no-pool space instead of its own pool's queue,
        # risking a duplicate sequence number within that pool.
        queue_sequence=await order_repo.next_queue_sequence(machine_id, machine_pool_id),
        quantity=quantity,
        quantity_completed=0.0,
        estimated_duration_minutes=estimated_duration,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=actor.id,
        machine_id=machine_id,
        machine_pool_id=machine_pool_id,
        lot_position_id=position.id,
    )
    return await order_repo.save(order)
