"""
Junction entity mapping a MadeItemDemandItem to the ProductionLot that covers
part of it, like BoughtItemDemandAllocation but without substitution. A
demand covered from stock has one STOCK row with no lot, topped up in place.
`lot_id` has no FK constraint.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource


@dataclass
class MadeItemDemandAllocation:
    demand_item_id: int  # → MadeItemDemandItem
    lot_id: int | None  # → ProductionLot; None when source is STOCK
    quantity: float  # how many units satisfy this demand
    source: MadeItemAllocationSource = MadeItemAllocationSource.LOT

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
        return self.lot_id
