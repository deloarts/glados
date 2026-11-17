"""
One immutable completion batch against a ProductionOrder, the counterpart of
OrderItemDelivery. An order can be completed in several partial batches, and
its `quantity_completed` is their running total. `operator_id` is who did the
work and `recorded_by_id` the session user, which differ when a shared
shop-floor account records someone's work. `machine_id` is the machine the
batch was booked on, kept although a paused order may move to another one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING

from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.shared_kernel.domain.entities.base import Entity

if TYPE_CHECKING:
    from src.modules.platform.domain.entities.user import User


@dataclass
class ProductionOrderCompletion(Entity):
    production_order_id: int  # → ProductionOrder
    quantity: float  # batch total = quantity_accepted + quantity_rejected
    # QA split of `quantity`; rejected is 0 for an ordinary completion (see
    # production_order_rules.resolve_completion_split).
    quantity_accepted: float
    quantity_rejected: float
    # The business day the work is reported for, picked by the operator; the
    # moment of recording is `created`.
    completion_date: date
    note: str | None
    operator_id: int  # → User, who actually did the work
    recorded_by_id: int  # → User, the authenticated session user
    created: datetime

    # ── Denormalized (read-only, populated by repository mapper) ──────
    operator: User | None = None
    recorded_by: User | None = None

    # Disposition of `quantity_rejected` on an inspection completion, where
    # rework plus scrap must equal it (assert_valid_disposition); both are 0
    # on an ordinary completion.
    quantity_rework: float = 0.0
    quantity_scrap: float = 0.0

    # ScrapReason of the scrapped pieces. The API requires it for a scrap
    # during production (scrap_production_pieces.py) but not on an inspection
    # completion.
    scrap_reason: ScrapReason | None = None

    # ScrapReason the rejected pieces failed for, shown in the inspection
    # report; set only when pieces were rejected.
    reject_reason: ScrapReason | None = None

    # Set on a reversal: the completion it takes back. A reversal books the
    # original's pieces negative, so every sum over an order's completions
    # nets out, and its note carries the reason.
    reverses_completion_id: int | None = None

    # The machine the order was on when the batch was booked, None for
    # manual or inspection work without one and for rows booked before it
    # was recorded. A reversal carries the machine of the batch it takes
    # back.
    machine_id: int | None = None
