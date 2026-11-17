"""
Input commands and output results for product family use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateProductFamilyCommand(BaseModel):
    name: str = Field(..., min_length=1)
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: str = ""


class UpdateProductFamilyCommand(BaseModel):
    name: str = Field(..., min_length=1)
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: str = ""


# ── Results (outbound) ────────────────────────────────────────────────


class ProductFamilyResult(ResultBase):
    created: datetime
    changed: datetime
    archived: bool
    name: str
    label_color: str
    label_font_color: str
    description: str
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
