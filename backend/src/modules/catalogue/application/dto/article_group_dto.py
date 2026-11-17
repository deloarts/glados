"""
Input commands and output results for article group use cases.
These cross the application boundary, not the same as API schemas.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ── Commands (inbound) ────────────────────────────────────────────────


class CreateArticleGroupCommand(BaseModel):
    name: dict[str, str]
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: dict[str, str] = Field(default_factory=dict)


class UpdateArticleGroupCommand(BaseModel):
    name: dict[str, str]
    label_color: str = "#999999"
    label_font_color: str = "#000000"
    description: dict[str, str] = Field(default_factory=dict)


# ── Results (outbound) ────────────────────────────────────────────────


class ArticleGroupResult(ResultBase):
    created: datetime
    changed: datetime
    archived: bool
    sort_order: int
    name: dict[str, str]
    label_color: str
    label_font_color: str
    description: dict[str, str]
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
