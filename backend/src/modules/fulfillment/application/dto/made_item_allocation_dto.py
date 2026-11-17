"""
DTOs for the MadeItemDemandAllocation aggregate. Mirror of allocation_dto.py,
trimmed to a stock-only surface: no order-item-equivalent CRUD/auto-allocate
yet since ProductionLot doesn't exist yet, and no substitution support.
"""

from pydantic import BaseModel
from pydantic import Field

# ── Commands ──────────────────────────────────────────────────────────


class UpdateMadeItemStockAllocationCommand(BaseModel):
    """Directly set the stock-sourced allocation quantity for a demand (manual override)."""

    quantity: float = Field(..., gt=0)


class FulfillMadeItemFromStockCommand(BaseModel):
    """
    Cover (part of) a demand directly from stock, no lot involved.
    No stock level is tracked here, that ledger lives in another service.
    """

    demand_item_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


# ── Results ───────────────────────────────────────────────────────────


class MadeItemAllocationResult(BaseModel):
    demand_item_id: int
    lot_id: int | None
    source: str
    quantity: float

    model_config = {"from_attributes": True}


class MadeItemDemandSummaryResult(BaseModel):
    demand_item_id: int
    unit: str
    total: float
    allocated: float
    fulfilled_from_stock: float
    ordered: float
    delivered: float
    remaining: float
    unallocated: float
    pending: float
    in_transit: float
    is_fully_allocated: bool
    is_fully_delivered: bool
    lot_ids: list[int] = Field(default_factory=list)


class FulfillMadeItemFromStockResult(BaseModel):
    demand_item_id: int
    quantity_fulfilled: float
    total_fulfilled_from_stock: float
    remaining_unallocated: float
    demand_status_changed_to: str | None
