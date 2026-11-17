"""
An extra cost on a supplier order, such as shipping, packaging or a
surcharge, charged beside the prices of its lines. It has no status and is
never received, so it never holds an order back from DELIVERED. It belongs
to the whole order unless it names one line, as tooling does for one
external fabrication step.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.shared_kernel.domain.entities.base import Entity


@dataclass(kw_only=True)
class OrderExtraCost(Entity):
    order_id: int
    kind: ExtraCostKind
    amount: int  # net, in EUR cents, always positive; a discount is subtracted
    position: int  # display order within the order, starts at 1
    label: str | None = None
    note: str | None = None
    order_item_id: int | None = None  # the line it belongs to, None for the whole order
