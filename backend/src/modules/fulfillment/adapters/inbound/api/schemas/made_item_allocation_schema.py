"""
Mirror of allocation_schema.py, trimmed to the stock-only surface made
items currently support.
"""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity


class MadeItemStockAllocationUpdateRequest(BaseModel):
    quantity: PositiveQuantity


class MadeItemAllocationResponse(ResponseModel):
    demand_item_id: int
    lot_id: int | None
    source: MadeItemAllocationSource
    quantity: float

    model_config = ConfigDict(from_attributes=True)


class MadeItemDemandSummaryResponse(ResponseModel):
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


class MadeItemFulfillFromStockRequest(BaseModel):
    quantity: PositiveQuantity


class MadeItemFulfillFromStockResponse(ResponseModel):
    demand_item_id: int
    quantity_fulfilled: float
    total_fulfilled_from_stock: float
    remaining_unallocated: float
    demand_status_changed_to: MadeItemDemandStatus | None
