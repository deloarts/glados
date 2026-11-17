"""
Domain events for the purchase-order lifecycle: creation, submission,
cancellation, and delivery. The status changes of orders and order lines
come from the lifecycle reconciler, which derives both from the recorded
facts and intents.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class OrderCreated(DomainEvent):
    order_id: int
    order_number: str
    creator_id: int
    supplier_id: int


@dataclass(frozen=True)
class OrderRequested(DomainEvent):
    order_id: int
    order_number: str
    actor_id: int
    supplier_id: int


@dataclass(frozen=True)
class OrderSubmitted(DomainEvent):
    order_id: int
    order_number: str
    actor_id: int
    supplier_id: int


@dataclass(frozen=True)
class OrderCanceled(DomainEvent):
    order_id: int
    order_number: str
    actor_id: int
    supplier_id: int
    creator_id: int


@dataclass(frozen=True)
class OrderStatusChanged(DomainEvent):
    """An order's derived status changed. `actor_id` is the user whose
    action led to the change."""

    order_id: int
    order_number: str
    supplier_id: int
    creator_id: int
    old_status: OrderStatus
    new_status: OrderStatus
    actor_id: int


@dataclass(frozen=True)
class OrderItemStatusChanged(DomainEvent):
    """An order line's derived status changed. `lot_position_id` is set for
    a MADE line, the position the line supplies."""

    order_item_id: int
    order_id: int
    line_type: OrderLineType
    lot_position_id: int | None
    old_status: OrderItemStatus
    new_status: OrderItemStatus
    actor_id: int


@dataclass(frozen=True)
class OrderItemDelivered(DomainEvent):
    order_item_id: int
    order_id: int
    # None for every line type except BOUGHT; VIRTUAL/MADE lines have
    # neither this nor source_item_id populated.
    bought_item_id: int | None
    actor_id: int
    # None for every line type except SOURCE.
    source_item_id: int | None
    # How much arrived in THIS delivery, not the running total: a partial
    # delivery publishes its own delta. Drives the per_event_quantity
    # copies rule and the @event_quantity field source.
    quantity: float


@dataclass(frozen=True)
class DeliveryPiecesRejected(DomainEvent):
    """Pieces were rejected while booking a delivery (see
    ProcessOrderItemDelivery). Published whenever quantity_rejected > 0 on
    the delivery event, regardless of outcome (redeliver or lost) or line
    type. supplier_id and reason/outcome are denormalized (same precedent
    as OrderItemDelivered.bought_item_id) so the notification handler can
    build its message without a repository lookup of its own."""

    order_item_id: int
    order_id: int
    supplier_id: int
    quantity: float
    reason: str
    outcome: str
    actor_id: int
