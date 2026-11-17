"""
Domain events for the production-lot lifecycle: a lot being created, held,
resumed, canceled or completed, a position being assigned or getting a
delivery recorded, pieces being scrapped, and every status change of a lot
or a position.

The lifecycle reconciler publishes LotStatusChanged for every lot status it
writes and LotCompleted besides when the new status is COMPLETED, and
LotPositionStatusChanged for every position status it writes. Canceled,
OnHold and Resumed come from the use cases that record those intents.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.shared_kernel.domain.events.base import DomainEvent


@dataclass(frozen=True)
class LotCreated(DomainEvent):
    lot_id: int
    made_item_id: int
    creator_id: int


@dataclass(frozen=True)
class LotCompleted(DomainEvent):
    lot_id: int
    lot_number: str
    creator_id: int
    # Denormalized so the made_item_completed print trigger can resolve its
    # root without a lookup.
    made_item_id: int


@dataclass(frozen=True)
class LotCanceled(DomainEvent):
    lot_id: int
    lot_number: str
    actor_id: int
    creator_id: int


@dataclass(frozen=True)
class LotSupplierLinesToSettle(DomainEvent):
    """A lot was canceled, force-completed or scrapped to nothing (`ended`:
    canceled, force_completed or scrapped) while supplier lines
    of its work or its raw material were already placed: `open_lines` still
    expect pieces nobody needs, `canceled_lines` were canceled after they
    were ordered. Purchasing settles both with the suppliers. The lines are
    named by order number and position, and `order_id` is the first one's
    order, so the notification needs no lookup of its own."""

    lot_id: int
    lot_number: str
    ended: str
    open_lines: list[str]
    canceled_lines: list[str]
    order_id: int | None
    actor_id: int


@dataclass(frozen=True)
class LotEndedShort(DomainEvent):
    """A force-complete closed the lot at `quantity` of `original_quantity`
    pieces and cut the allocations of `demand_ids`, which are now short of
    what they need. Planners decide how to cover the rest."""

    lot_id: int
    lot_number: str
    quantity: float
    original_quantity: float
    demand_ids: list[int]
    actor_id: int


@dataclass(frozen=True)
class LotPositionAssigned(DomainEvent):
    lot_id: int
    position_id: int
    order_id: int
    order_item_id: int
    actor_id: int


@dataclass(frozen=True)
class LotPositionDeliveryRecorded(DomainEvent):
    lot_id: int
    position_id: int
    order_item_id: int
    quantity_completed: float
    actor_id: int


@dataclass(frozen=True)
class LotOnHold(DomainEvent):
    lot_id: int
    lot_number: str
    actor_id: int
    creator_id: int


@dataclass(frozen=True)
class LotResumed(DomainEvent):
    lot_id: int
    lot_number: str
    actor_id: int
    creator_id: int


@dataclass(frozen=True)
class PiecesScrapped(DomainEvent):
    """A scrap disposition recorded against a lot: internal scrap during
    production (scrap_production_pieces.py) today, QA/inspection scrap and
    lost-at-receipt share the same disposition machinery but keep their
    own existing/future events. lot_number and replacement_lot_number are
    denormalized (same precedent as LotCanceled.lot_number) so the
    notification handler can build its message without a repository
    lookup of its own."""

    lot_id: int
    lot_number: str
    position_id: int
    production_order_id: int | None
    quantity: float
    reason: str
    replacement_lot_id: int | None
    replacement_lot_number: str | None
    actor_id: int
    # The completion row this occurrence was recorded on, so the
    # pieces_scrapped print trigger can resolve the scrap_tag classifier's
    # root without a lookup (same precedent as LotCompleted.made_item_id).
    completion_id: int


@dataclass(frozen=True)
class LotStatusChanged(DomainEvent):
    """A lot's derived status changed. `actor_id` is the user whose action
    led to the change."""

    lot_id: int
    lot_number: str
    creator_id: int
    old_status: LotStatus
    new_status: LotStatus
    actor_id: int


@dataclass(frozen=True)
class LotPositionStatusChanged(DomainEvent):
    """A lot position's derived status changed. `actor_id` is the user whose
    action led to the change."""

    lot_id: int
    position_id: int
    old_status: LotPositionStatus
    new_status: LotPositionStatus
    actor_id: int
