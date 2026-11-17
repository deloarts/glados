"""
HTTP schemas for API key creation, listing, filtering, and usage logs.
"""

from datetime import date
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.application.dto.api_key_dto import ApiKeyResult
from src.modules.platform.application.dto.api_key_dto import ApiKeyUsageLogEntryResult
from src.modules.platform.application.dto.api_key_dto import CreatedApiKeyResult
from src.modules.platform.application.dto.api_key_dto import RevokeAllApiKeysResult
from src.modules.platform.ports.outbound.repositories.api_key_repository import ApiKeyFilterDto

__all__ = [
    "ApiKeyCreateRequest",
    "ApiKeyFilterParams",
    "ApiKeyResult",
    "ApiKeyUsageLogEntryResult",
    "CreatedApiKeyResult",
    "RevokeAllApiKeysResult",
]


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    permissions: list[str] = Field(default_factory=list)
    # None = never expires (the web UI should warn on non-expiring keys).
    # Mirrored on CreateApiKeyCommand: le=36500 is the wire-boundary ceiling
    # only, see that field's comment for the actually enforced cap.
    expires_in_days: int | None = Field(default=None, gt=0, le=36500)


# ── Filter params ─────────────────────────────────────────────────────


class ApiKeyFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    include_revoked: bool = Query(default=False)
    order_by: Literal["id", "name", "created", "expires_at"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)
    token_prefix: str | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    expiry: Literal["never", "expired", "active", "unexpired"] | None = Query(default=None)
    kind: Literal["standard", "terminal"] | None = Query(default=None)

    def to_dto(self) -> ApiKeyFilterDto:
        return ApiKeyFilterDto(**self.model_dump())
