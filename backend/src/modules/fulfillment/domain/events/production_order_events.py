"""
No separate ProductionOrderQueued event, a new order is QUEUED by
construction (redundant with Created), and queue reorder is silent
bookkeeping: no listener needs it, since queue reorder is a pure
date-recompute, never a status change.

The lifecycle reconciler publishes ProductionOrderStatusChanged for every
status it writes, and ProductionOrderCompleted or ProductionOrderCanceled
besides when the new status is COMPLETED or CANCELED. Started, Paused,
Resumed and CompletionRecorded come from the use cases that record those
intents and facts.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ProductionOrderCreated(DomainEvent):
    production_order_id: int
    machine_id: int | None
    lot_position_id: int
    creator_id: int
    # → MachinePool, mirrors ProductionOrder.machine_pool_id (pool-first
    # planning): set when this order was created pool-assigned rather
    # than routed to one specific machine.
    machine_pool_id: int | None


@dataclass(frozen=True)
class ProductionOrderStarted(DomainEvent):
    production_order_id: int
    # None for a pure-manual position, which starts without a machine.
    machine_id: int | None
    actor_id: int
    # → MachinePool, mirrors ProductionOrder.machine_pool_id: set when
    # this order was resolved from a pool at Start time (or already
    # carried one), None for a direct machine assignment or a pure-manual
    # position.
    machine_pool_id: int | None


@dataclass(frozen=True)
class ProductionOrderPaused(DomainEvent):
    production_order_id: int
    actor_id: int


@dataclass(frozen=True)
class ProductionOrderResumed(DomainEvent):
    production_order_id: int
    actor_id: int
    # None for a pure-manual position; mirrors ProductionOrderStarted's
    # own machine_id, a resume goes through StartProductionOrder again.
    machine_id: int | None


@dataclass(frozen=True)
class ProductionOrderCompletionRecorded(DomainEvent):
    production_order_id: int
    lot_position_id: int
    quantity_completed: float
    actor_id: int


@dataclass(frozen=True)
class ProductionOrderCompletionReversed(DomainEvent):
    """A reversal took back a completion of the order. It never triggers
    what a recorded completion triggers, such as printing labels."""

    production_order_id: int
    completion_id: int
    reversal_id: int
    actor_id: int


@dataclass(frozen=True)
class ProductionOrderCompleted(DomainEvent):
    production_order_id: int
    # None for orders on pure-manual positions (never assigned a machine).
    machine_id: int | None
    creator_id: int


@dataclass(frozen=True)
class ProductionOrderCanceled(DomainEvent):
    production_order_id: int
    actor_id: int
    creator_id: int


@dataclass(frozen=True)
class ProductionOrderStatusChanged(DomainEvent):
    production_order_id: int
    old_status: ProductionOrderStatus
    new_status: ProductionOrderStatus
    actor_id: int
    creator_id: int
