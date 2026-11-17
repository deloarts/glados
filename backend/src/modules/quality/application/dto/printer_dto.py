"""
DTOs for the Printer catalogue aggregate.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.platform.application.dto.base import ResultBase

# ══════════════════════════════════════════════════════════════════════
# Printer (catalogue)
# ══════════════════════════════════════════════════════════════════════


class CreatePrinterCommand(BaseModel):
    name: str = Field(..., min_length=1)
    internal_name: str | None = None
    kind: str
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    timeout_seconds: float = Field(default=5.0, gt=0)
    transport: str
    ipp_uri_path: str = "/"
    head_dpi: int | None = None
    format_convert_factor: int | None = None
    default_media: str | None = None
    location: str | None = None
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    bought_item_ids: list[int] = Field(default_factory=list)
    enabled: bool = True
    is_default: bool = False
    note: str | None = None


class UpdatePrinterCommand(BaseModel):
    name: str | None = None
    internal_name: str | None = None
    kind: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    timeout_seconds: float | None = Field(default=None, gt=0)
    transport: str | None = None
    ipp_uri_path: str | None = None
    head_dpi: int | None = None
    format_convert_factor: int | None = None
    default_media: str | None = None
    location: str | None = None
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    bought_item_ids: list[int] | None = None
    enabled: bool | None = None
    is_default: bool | None = None
    note: str | None = None


class PrinterResult(ResultBase):
    created: datetime
    changed: datetime | None
    archived: bool
    name: str
    internal_name: str | None
    kind: str
    host: str
    port: int
    timeout_seconds: float
    transport: str
    ipp_uri_path: str
    head_dpi: int | None
    format_convert_factor: int | None
    default_media: str | None
    location: str | None
    vendor: str | None
    model: str | None
    firmware: str | None
    bought_item_ids: list[int] = Field(default_factory=list)
    bought_items: list[BoughtItemResult] = Field(default_factory=list)
    enabled: bool
    is_default: bool
    note: str | None
    creator_id: int
    creator_full_name: str = ""
    changed_by_id: int | None
    changed_by_full_name: str
    changes: list[str] = Field(default_factory=list)


class PrinterStatusResult(BaseModel):
    identity: str
    status_lines: list[str] = Field(default_factory=list)
