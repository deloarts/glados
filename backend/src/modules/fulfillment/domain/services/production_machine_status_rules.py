"""
Pure resolution of a production machine's status from its open downtime
and its currently active production orders. No I/O, no ORM: callers batch
both inputs elsewhere (see get_active_by_machine_ids and
get_open_by_machine_ids) and this only applies the precedence rule.
"""

from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.production_machine_status import (
    ProductionMachineStatus,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus


def resolve_machine_status(
    active_orders: list[ProductionOrder], has_open_downtime: bool
) -> ProductionMachineStatus:
    """down when an open downtime exists (regardless of any order state);
    otherwise running when at least one active order is in progress;
    otherwise paused when at least one active order is paused; otherwise
    idle. An archived machine resolves through the same precedence, the
    client renders the tag muted for it."""
    if has_open_downtime:
        return ProductionMachineStatus.DOWN
    if any(o.status == ProductionOrderStatus.IN_PROGRESS for o in active_orders):
        return ProductionMachineStatus.RUNNING
    if any(o.status == ProductionOrderStatus.PAUSED for o in active_orders):
        return ProductionMachineStatus.PAUSED
    return ProductionMachineStatus.IDLE
