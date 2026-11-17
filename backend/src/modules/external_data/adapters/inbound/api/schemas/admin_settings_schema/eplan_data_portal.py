"""
HTTP schemas for the EPLAN Data Portal settings and the connection test.
The token is write-only: requests may carry it, responses only say whether
one is stored.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class UpdateEdpSettingsRequest(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=300)
    # None keeps the stored token, "" clears it.
    pat: str | None = Field(default=None, max_length=1000)
    default_article_group_ids: list[int] | None = None
    language: Literal["de_DE", "en_US"] | None = None


class VerifyEdpConnectionRequest(BaseModel):
    base_url: str | None = Field(default=None, max_length=300)
    pat: str | None = Field(default=None, max_length=1000)


class AdminEdpSettingsResponse(EntityResponse):
    enabled: bool
    base_url: str
    pat_configured: bool
    default_article_group_ids: list[int]
    language: str
    is_configured: bool


class EdpConnectionTestResponse(ResponseModel):
    authenticated: bool
