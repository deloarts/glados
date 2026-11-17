"""Input commands and output results for allocation use cases."""

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultModel

# ── Commands ──────────────────────────────────────────────────────────


class CreateAllocationCommand(BaseModel):
    demand_item_id: int = Field(..., gt=0)
    order_item_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    substitute_item_id: int | None = None
    substitute_reason: str | None = None


class UpdateAllocationCommand(BaseModel):
    quantity: float = Field(..., gt=0)


class UpdateStockAllocationCommand(BaseModel):
    """Directly set the stock-sourced allocation quantity for a demand (manual override)."""

    quantity: float = Field(..., gt=0)


class AutoAllocateCommand(BaseModel):
    """
    Trigger the automatic allocation engine for a single demand item.
    The engine finds all eligible open order items (same catalogue item,
    ORDERED or PARTIALLY_DELIVERED status) and allocates greedily.
    """

    demand_item_id: int = Field(..., gt=0)


class FulfillFromStockCommand(BaseModel):
    """
    Cover (part of) a demand directly from stock, no order involved.
    No stock level is tracked here, that ledger lives in another service.
    """

    demand_item_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


# ── Results ───────────────────────────────────────────────────────────


class AllocationResult(BaseModel):
    demand_item_id: int
    order_item_id: int | None
    source: str
    quantity: float
    substitute_item_id: int | None = None
    substitute_reason: str | None = None
    order_number: str | None = None
    order_supplier_name: str | None = None
    item_order_code_1: str | None = None
    item_article_name: str | None = None
    project_number: str | None = None
    order_item_quantity: float | None = None
    # The line's unit and the demand's, and whether they differ, which the
    # clients warn on; the demand unit is filled where the demand was read.
    order_item_unit: str | None = None
    demand_unit: str | None = None
    unit_mismatch: bool = False

    model_config = {"from_attributes": True}


class SubstitutionDetail(ResultModel):
    substitute_item_id: int
    substitute_item_order_code_1: str
    substitute_item_article_name: str
    substitute_reason: str | None
    quantity: float


class DemandSummaryResult(BaseModel):
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
    # Whether a line the demand draws on names another unit than the demand.
    unit_mismatch: bool = False
    order_ids: list[int] = Field(default_factory=list)
    order_numbers: list[str] = Field(default_factory=list)
    substitutions: list[SubstitutionDetail] = Field(default_factory=list)


class AutoAllocateResult(BaseModel):
    demand_item_id: int
    allocations_created: int
    allocations_updated: int
    total_newly_allocated: float
    remaining_unallocated: float
    demand_status_changed_to: str | None
    # Lines used whose unit differs from the demand's; nothing converts units.
    unit_mismatches: int = 0


class FulfillFromStockResult(BaseModel):
    demand_item_id: int
    quantity_fulfilled: float
    total_fulfilled_from_stock: float
    remaining_unallocated: float
    demand_status_changed_to: str | None
