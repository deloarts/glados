"""
Junction entity mapping a BoughtItemDemandItem to the OrderItem that covers
part of it, so one demand can be split across order lines and one line can
cover several demands. A demand covered from stock has one STOCK row with no
order item, topped up in place; stock levels live elsewhere.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource


@dataclass
class BoughtItemDemandAllocation:
    demand_item_id: int  # → BoughtItemDemandItem
    order_item_id: int | None  # → OrderItem; None when source is STOCK
    quantity: float  # how many units satisfy this demand
    source: AllocationSource = AllocationSource.ORDER
    # When the buyer orders a different catalogue item to satisfy this demand,
    # substitute_item_id records what was actually ordered (= order_item.bought_item_id).
    # Its presence is the authoritative signal that this is a substitution.
    substitute_item_id: int | None = None
    substitute_reason: str | None = None

    # Who created the row and when, and when it last changed; read back from
    # the row. The creator is empty for a system write and for rows from
    # before it was recorded; the actor of each manual change is on the
    # demand's changelog.
    created_by_id: int | None = None
    created_at: datetime | None = None
    changed_at: datetime | None = None

    @property
    def coverage_ref_id(self) -> int | None:
        """Generic id used by the allocation-coverage protocol."""
        return self.order_item_id
