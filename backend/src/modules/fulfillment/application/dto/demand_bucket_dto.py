"""
Shared command and result shapes for the bought-item, made-item, and
source-item demand bucket DTOs. Each family's create/update commands and
result are identical apart from name; this module holds the one definition
they all inherit, so every family keeps its own class name for use cases,
endpoints, and tests to import.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase

# ── Commands (inbound) ────────────────────────────────────────────────


class DemandBucketCommandBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: str


# ── Results (outbound) ────────────────────────────────────────────────


class DemandBucketResultBase(ResultBase):
    created: datetime
    name: str
    color: str
    creator_id: int
