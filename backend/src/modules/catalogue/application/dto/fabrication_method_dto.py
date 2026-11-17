"""
Input commands and output results for fabrication method use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateFabricationMethodCommand(BaseModel):
    name: dict[str, str]
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: dict[str, str] = Field(default_factory=dict)
    requires_machine: bool = True
    required_external: bool = False
    default_supplier_id: int | None = None
    lead_time_days: int | None = None
    default_for_assemblies: bool = False


class UpdateFabricationMethodCommand(BaseModel):
    name: dict[str, str]
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: dict[str, str] = Field(default_factory=dict)
    requires_machine: bool = True
    required_external: bool = False
    default_supplier_id: int | None = None
    lead_time_days: int | None = None
    default_for_assemblies: bool = False


# ── Results (outbound) ────────────────────────────────────────────────


class FabricationMethodResult(ResultBase):
    created: datetime
    changed: datetime
    name: dict[str, str]
    label_color: str
    label_font_color: str
    description: dict[str, str]
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    requires_machine: bool = True
    required_external: bool = False
    default_supplier_id: int | None = None
    lead_time_days: int | None = None
    default_for_assemblies: bool = False
    archived: bool = False
    sort_order: int
