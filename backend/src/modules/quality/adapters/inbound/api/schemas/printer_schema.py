"""
HTTP schemas for the Printer catalogue aggregate.
"""

from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind
from src.modules.quality.domain.value_objects.printer_kind import PrinterTransport
from src.modules.quality.ports.outbound.repositories.printer_repository import PrinterFilterDto

# ══════════════════════════════════════════════════════════════════════
# Printer (catalogue)
# ══════════════════════════════════════════════════════════════════════


class PrinterCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    internal_name: str | None = Field(default=None, min_length=1)
    kind: Literal["zpl_label", "ipp_document"]
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    timeout_seconds: float = Field(default=5.0, gt=0)
    transport: Literal["raw", "ipp"]
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


class PrinterUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    internal_name: str | None = Field(default=None, min_length=1)
    kind: Literal["zpl_label", "ipp_document"] | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    timeout_seconds: float | None = Field(default=None, gt=0)
    transport: Literal["raw", "ipp"] | None = None
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


class PrinterResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    archived: bool
    name: str
    internal_name: str | None
    kind: PrinterKind
    host: str
    port: int
    timeout_seconds: float
    transport: PrinterTransport
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


class PrinterStatusResponse(ResponseModel):
    identity: str
    status_lines: list[str] = Field(default_factory=list)


class PrinterFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    name: str | None = Query(default=None)
    kind: Literal["zpl_label", "ipp_document"] | None = Query(default=None)
    enabled: bool | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    order_by: Literal["id", "name", "changed", "created"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> PrinterFilterDto:
        return PrinterFilterDto(**self.model_dump())
