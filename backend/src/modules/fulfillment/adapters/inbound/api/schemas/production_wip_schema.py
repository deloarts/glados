"""
HTTP response schemas for the live WIP overview (GET /production-wip).
Mirrors production_lot_schema.py's conventions.
"""

from pydantic import ConfigDict
from pydantic import Field

from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel

# ══════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════


class WipStageResponse(ResponseModel):
    position_id: int
    sequence: int
    kind: LotPositionKind
    status: LotPositionStatus
    quantity: float
    quantity_completed: float
    machine_names: list[str] = Field(default_factory=list)
    supplier_name: str = ""

    model_config = ConfigDict(from_attributes=True)


class WipLotResponse(EntityResponse):
    lot_number: str
    quantity: float
    status: LotStatus
    priority: UrgencyClass
    made_item_id: int
    made_item_part_number: str
    made_item_revision: str
    made_item_article_name: str
    raw_count: float
    finished_count: float
    stages: list[WipStageResponse] = Field(default_factory=list)
