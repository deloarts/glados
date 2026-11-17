"""
DTOs for the SourceItem catalogue aggregate.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# SourceItem (catalogue)
# ══════════════════════════════════════════════════════════════════════


class CreateSourceItemCommand(BaseModel):
    type_id: int
    dimension: str | None = None
    material: str = Field(..., min_length=1)
    mass: int | None = None
    note: str | None = None
    order_code_1: str | None = None
    order_code_2: str | None = None
    status: str = "active"
    manufacturer_id: int | None = None
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None


class UpdateSourceItemCommand(BaseModel):
    type_id: int
    dimension: str | None = None
    material: str = Field(..., min_length=1)
    mass: int | None = None
    note: str | None = None
    order_code_1: str | None = None
    order_code_2: str | None = None
    status: str = "active"
    manufacturer_id: int | None = None
    approver_id: int | None = None
    successor_item_id: int | None = None
    # An update without them keeps the item's.
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


class SourceItemResult(ResultBase):
    status: str
    created: datetime
    changed: datetime
    archived: bool
    type_id: int
    type_name: dict[str, str]
    dimension: str | None
    material: str
    mass: int | None
    note: str | None
    order_code_1: str | None
    order_code_2: str | None
    successor_item_id: int | None
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    approver_id: int | None
    manufacturer_id: int | None
    manufacturer_name: str
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    changes: list[str] = Field(default_factory=list)
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0
