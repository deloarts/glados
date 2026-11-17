"""
HTTP schemas for allocation requests and responses covering demand item
allocations, auto-allocation, and stock fulfillment.
"""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.allocation_dto import SubstitutionDetail
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity


class AllocationCreateRequest(BaseModel):
    demand_item_id: int = Field(..., gt=0)
    order_item_id: int = Field(..., gt=0)
    quantity: PositiveQuantity
    substitute_item_id: int | None = None
    substitute_reason: str | None = None


class AllocationUpdateRequest(BaseModel):
    quantity: PositiveQuantity


class StockAllocationUpdateRequest(BaseModel):
    quantity: PositiveQuantity


class AllocationResponse(ResponseModel):
    demand_item_id: int
    order_item_id: int | None
    source: AllocationSource
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

    model_config = ConfigDict(from_attributes=True)


class DemandSummaryResponse(ResponseModel):
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


class AutoAllocateResponse(ResponseModel):
    demand_item_id: int
    allocations_created: int
    allocations_updated: int
    total_newly_allocated: float
    remaining_unallocated: float
    demand_status_changed_to: BoughtItemDemandStatus | None
    # Lines used whose unit differs from the demand's; nothing converts units.
    unit_mismatches: int = 0


class FulfillFromStockRequest(BaseModel):
    quantity: PositiveQuantity


class FulfillFromStockResponse(ResponseModel):
    demand_item_id: int
    quantity_fulfilled: float
    total_fulfilled_from_stock: float
    remaining_unallocated: float
    demand_status_changed_to: BoughtItemDemandStatus | None
