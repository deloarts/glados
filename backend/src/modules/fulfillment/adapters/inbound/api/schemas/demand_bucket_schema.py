"""
HTTP schemas for demand bucket creation, updates, filtering and responses,
shared by the bought-item, made-item and source-item bucket endpoints. The
wire shape is the same for every family, so all three routers use these
classes and the OpenAPI document carries one component per schema.
"""

from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams

TFilter = TypeVar("TFilter")

# ── Request schemas ───────────────────────────────────────────────────


class DemandBucketCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: str = Field(..., pattern="^#[0-9a-fA-F]{6}$")


class DemandBucketUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: str = Field(..., pattern="^#[0-9a-fA-F]{6}$")


# ── Response schemas ──────────────────────────────────────────────────


class DemandBucketResponse(EntityResponse):
    created: datetime
    name: str
    color: str
    creator_id: int


# ── Filter params ─────────────────────────────────────────────────────


class DemandBucketFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across the bucket name")

    def to_dto(self, dto_cls: Callable[..., TFilter]) -> TFilter:
        """Builds the family's filter DTO, whose fields match these params."""
        return dto_cls(**self.model_dump())
