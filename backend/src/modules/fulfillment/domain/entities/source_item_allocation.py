"""
Junction entity mapping a SourceItemDemandItem to the OrderItem that covers
part of it, so one demand can be split across order lines and one bulk
purchase can cover several demands. Like BoughtItemDemandAllocation it allows
substitution (SourceItemAllocationRules.assert_material_matches), but only for
demands sourced from a source item. A demand covered from stock has one STOCK
row with no order item, topped up in place; stock levels live elsewhere.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)


@dataclass
class SourceItemDemandAllocation:
    demand_item_id: int  # → SourceItemDemandItem
    order_item_id: int | None  # → OrderItem; None when source is STOCK
    quantity: float  # how many units satisfy this demand
    source: SourceItemAllocationSource = SourceItemAllocationSource.ORDER
    # The source item actually ordered when the buyer substitutes one; its
    # presence is what marks a substitution.
    substitute_source_item_id: int | None = None
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
