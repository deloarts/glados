"""HTTP schemas for personal access token (PAT) management and usage logging."""

from datetime import date
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.application.dto.pat_dto import CreatedPatResult
from src.modules.platform.application.dto.pat_dto import PatResult
from src.modules.platform.application.dto.pat_dto import PatUsageLogEntryResult
from src.modules.platform.application.dto.pat_dto import RevokeAllPatsResult
from src.modules.platform.ports.outbound.repositories.pat_repository import PatFilterDto

__all__ = [
    "CreatedPatResult",
    "PatCreateRequest",
    "PatFilterParams",
    "PatResult",
    "PatUsageLogEntryResult",
    "RevokeAllPatsResult",
]


class PatCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    permissions: list[str] = Field(default_factory=list)
    # None = never expires (the web UI should warn on non-expiring tokens).
    # Mirrored on CreatePatCommand: le=36500 is the wire-boundary ceiling
    # only, see that field's comment for the actually enforced cap.
    expires_in_days: int | None = Field(default=None, gt=0, le=36500)
    # The acting user's current password. A token outlives the session that
    # created it, so a session alone must not be enough to mint one.
    password: str = Field(min_length=1)


# ── Filter params ─────────────────────────────────────────────────────


class PatFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    include_revoked: bool = Query(default=False)
    order_by: Literal["id", "name", "created", "expires_at"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)
    token_prefix: str | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    expiry: Literal["never", "expired", "active", "unexpired"] | None = Query(default=None)

    def to_dto(self) -> PatFilterDto:
        return PatFilterDto(**self.model_dump())
