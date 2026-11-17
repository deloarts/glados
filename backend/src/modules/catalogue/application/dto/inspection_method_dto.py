"""
Input commands and output results for inspection method use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateInspectionMethodCommand(BaseModel):
    name: dict[str, str]
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: dict[str, str] = Field(default_factory=dict)
    # Optional: seeded onto steps created against this method (see
    # inspection_method_rules.seed_inspection_estimates).
    default_setup_minutes: int | None = Field(default=None, ge=0)
    default_minutes_per_piece: float | None = Field(default=None, ge=0)
    requires_evidence: bool = False
    # Optional QA machine pre-filled onto this method's steps at lot
    # creation (see create_lot.py). None = genuinely machine-less manual
    # QA work.
    default_machine_id: int | None = None


class UpdateInspectionMethodCommand(BaseModel):
    name: dict[str, str]
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: dict[str, str] = Field(default_factory=dict)
    # Optional: seeded onto steps created against this method (see
    # inspection_method_rules.seed_inspection_estimates).
    default_setup_minutes: int | None = Field(default=None, ge=0)
    default_minutes_per_piece: float | None = Field(default=None, ge=0)
    requires_evidence: bool = False
    # Optional QA machine pre-filled onto this method's steps at lot
    # creation (see create_lot.py). None = genuinely machine-less manual
    # QA work.
    default_machine_id: int | None = None


# ── Results (outbound) ────────────────────────────────────────────────


class InspectionMethodResult(ResultBase):
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
    default_setup_minutes: int | None = None
    default_minutes_per_piece: float | None = None
    requires_evidence: bool = False
    archived: bool = False
    sort_order: int
    default_machine_id: int | None = None
    default_machine_name: str | None = None
