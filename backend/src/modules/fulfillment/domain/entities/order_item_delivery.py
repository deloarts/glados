"""
A single delivery event against an OrderItem. An order item can
be delivered in several partial shipments, each one gets its own
immutable record here, forming the audit trail. The order item's
`quantity_delivered` is the running total kept in sync with these rows.
Never updated or deleted; correcting a mistaken booking means recording a
new, compensating event.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.quantities import quantity_gt
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class OrderItemDelivery(Entity):
    order_item_id: int  # → OrderItem
    quantity: float  # amount accepted in this event
    delivery_date: datetime
    storage_place: str | None
    receiver_id: int | None
    created: datetime

    # How many pieces of THIS delivery event were rejected, the classified
    # reason (ScrapReason value object) and free-text note, and what
    # happens to them (RejectionOutcome value object). All default to
    # "nothing rejected" so most delivery rows never set them.
    quantity_rejected: float = 0.0
    rejection_reason: str | None = None
    rejection_note: str | None = None
    rejection_outcome: RejectionOutcome | None = None

    # A correction is a compensating row: `quantity` is the negative of the
    # accepted pieces it takes back, `corrects_delivery_id` names the row it
    # corrects and `correction_reason` says why. Both are None on a delivery.
    # A correction that rejects the pieces it takes back, damage found after
    # receipt, carries them in the rejection fields above and no correction
    # reason, so the line's rejected totals stay the sums over its rows.
    corrects_delivery_id: int | None = None
    correction_reason: str | None = None

    # Where the received material comes from, for its genealogy into the
    # lot that consumes it: the supplier's batch or heat number, the
    # delivery note and the inspection certificate (an EN 10204 3.1 one for
    # steel). All optional; a correction carries none.
    supplier_batch: str | None = None
    delivery_note_number: str | None = None
    certificate_reference: str | None = None

    # Whether the receiver noted damage on the carrier's delivery note when
    # the goods were handed over, which a transport damage claim depends on.
    damage_noted_on_delivery_note: bool = False

    # ── Denormalized (read-only, populated by repository mapper) ──────
    receiver: User | None = None


def latest_arrival(rows: list[OrderItemDelivery]) -> datetime | None:
    """When goods last arrived on a line by its delivery rows: the latest
    delivery that still has accepted pieces after its corrections, or that
    rejected pieces at receipt or after it, which arrived as well. None when
    every accepted piece was taken back as a miscount and nothing was
    rejected, so a line corrected back to nothing shows no delivery date."""
    taken_back: dict[int, float] = {}
    rejected_later: set[int] = set()
    for row in rows:
        if row.corrects_delivery_id is not None:
            taken_back[row.corrects_delivery_id] = (
                taken_back.get(row.corrects_delivery_id, 0.0) - row.quantity
            )
            if quantity_gt(row.quantity_rejected, 0.0):
                rejected_later.add(row.corrects_delivery_id)
    standing = [
        row.delivery_date
        for row in rows
        if row.corrects_delivery_id is None
        and (
            quantity_gt(row.quantity - taken_back.get(row.id, 0.0), 0.0)
            or quantity_gt(row.quantity_rejected, 0.0)
            or row.id in rejected_later
        )
    ]
    return max(standing, default=None)
