"""
Immutable quantity breakdown for a single DemandItem.
Computed from live allocation + delivery data, never stored in the DB.

Terminology:
  total               = demand.quantity (what the project needs)
  allocated           = sum of all order-sourced allocation.quantity for this demand
                        (linked to any order item, regardless of its status)
  fulfilled_from_stock = sum of stock-sourced allocation.quantity for this demand
                        (already on hand, no order involved)
  ordered             = sum of allocation.quantity where the order item is ORDERED,
                        PARTIALLY_DELIVERED, or DELIVERED (a purchase order was placed)
  delivered           = sum of allocation.quantity, scaled per allocation by the
                        linked order item's quantity_delivered / quantity ratio
  remaining           = total - delivered - fulfilled_from_stock  (still needs to arrive)
  unallocated         = total - allocated - fulfilled_from_stock  (not yet covered at all)
  pending             = allocated - ordered  (in order items that are still PENDING)
  in_transit          = ordered - delivered  (placed with supplier, not yet arrived)
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.platform.domain.services.quantities import quantity_ge


@dataclass(frozen=True)
class DemandQuantitySummary:
    demand_item_id: int
    unit: str
    total: float
    allocated: float
    ordered: float  # units in order items with status ORDERED/PARTIALLY_DELIVERED/DELIVERED
    delivered: float
    fulfilled_from_stock: float
    order_ids: tuple[int, ...] = field(default=())

    @property
    def remaining(self) -> float:
        """Units still needed after deducting deliveries and stock fulfillment."""
        return max(0.0, self.total - self.delivered - self.fulfilled_from_stock)

    @property
    def unallocated(self) -> float:
        """Units not yet linked to any order item nor covered from stock."""
        return max(0.0, self.total - self.allocated - self.fulfilled_from_stock)

    @property
    def pending(self) -> float:
        """Units linked to order items that are still PENDING (not yet placed)."""
        return max(0.0, self.allocated - self.ordered)

    @property
    def in_transit(self) -> float:
        """Units in placed orders (ORDERED/PARTIALLY_DELIVERED) but not yet delivered."""
        return max(0.0, self.ordered - self.delivered)

    @property
    def is_fully_allocated(self) -> bool:
        """Compared with the lifecycle tolerance, as the demand's derived
        status compares, so the flag and the status agree."""
        return quantity_ge(self.allocated + self.fulfilled_from_stock, self.total)

    @property
    def is_fully_delivered(self) -> bool:
        """Compared with the lifecycle tolerance, see is_fully_allocated."""
        return quantity_ge(self.delivered + self.fulfilled_from_stock, self.total)
