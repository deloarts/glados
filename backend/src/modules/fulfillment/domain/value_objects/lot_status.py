"""Status enums for the ProductionLot aggregate.

A lot's status, and the kind and status of each of its positions, are
derived from recorded facts and intents (src/domain/services/lifecycle/)
and stored for querying. ON_HOLD pauses a lot for urgent work: its queued
orders stop consuming capacity and running ones are paused. Assigning
positions advances a lot through PARTIALLY_PLANNED and PLANNED. SCRAPPED is
terminal like COMPLETED and is derived once dispositions leave the lot with
nothing to produce.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class LotStatus(StrValueEnum):
    """Status of a ProductionLot."""

    DRAFT = "draft"
    PARTIALLY_PLANNED = "partially_planned"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELED = "canceled"
    SCRAPPED = "scrapped"

    @classmethod
    def default(cls) -> "LotStatus":
        return cls.DRAFT


# The statuses a lot never leaves; filters and guards that exclude finished
# lots read this one set.
TERMINAL_LOT_STATUSES: frozenset[str] = frozenset(
    {LotStatus.COMPLETED, LotStatus.CANCELED, LotStatus.SCRAPPED}
)


@unique
class LotPositionKind(StrValueEnum):
    # Derived in src/modules/fulfillment/domain/services/lifecycle/lot_position.py.
    """Who executes a lot position, derived from its live order line and its
    production orders.

    UNASSIGNED means nothing is committed: no live line, no live production
    order and no pieces made in house. EXTERNAL means a live line buys the
    position from a supplier, INTERNAL that live production orders or pieces
    already made in house cover it, and MIXED that both do.
    """

    UNASSIGNED = "unassigned"
    EXTERNAL = "external"
    INTERNAL = "internal"
    # Part of the quantity bought externally, the rest made in house.
    MIXED = "mixed"

    @classmethod
    def default(cls) -> "LotPositionKind":
        return cls.UNASSIGNED


@unique
class LotPositionStatus(StrValueEnum):
    # Derived in src/modules/fulfillment/domain/services/lifecycle/lot_position.py.
    """Status of a lot position. Derived and stored for querying, never set
    by a user directly.

    A position whose only side is a supplier line goes from PENDING to
    ORDERED_OR_QUEUED once the line is ordered, to PARTIALLY_COMPLETED with
    its first accepted delivery and to COMPLETED when its pieces are in.
    IN_PROGRESS needs a running production order, since a supplier reports
    no start.
    """

    PENDING = "pending"
    ORDERED_OR_QUEUED = "ordered_or_queued"
    IN_PROGRESS = "in_progress"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    # Every position of a canceled lot.
    CANCELED = "canceled"

    @classmethod
    def default(cls) -> "LotPositionStatus":
        return cls.PENDING
