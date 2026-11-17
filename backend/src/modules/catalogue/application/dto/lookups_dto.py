"""
Result DTO for GET /pat/lookups: the add-in's offline lookup cache, one
call instead of six capped list requests. Reuses the existing
per-resource result DTOs unchanged; this is purely an aggregate wrapper.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.dto.fabrication_method_dto import FabricationMethodResult
from src.modules.catalogue.application.dto.inspection_method_dto import InspectionMethodResult
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.application.dto.source_item_type_dto import SourceItemTypeResult
from src.modules.catalogue.application.dto.supplier_dto import SupplierResult


class CustomerLookupResult(BaseModel):
    """A customer as the add-in's picker needs it: no address, contact or
    VAT data leaves the web surface through the `pat` API."""

    id: int
    name: str
    archived: bool


class LookupsResult(BaseModel):
    server_time: datetime
    suppliers: list[SupplierResult] = Field(default_factory=list)
    article_groups: list[ArticleGroupResult] = Field(default_factory=list)
    fabrication_methods: list[FabricationMethodResult] = Field(default_factory=list)
    inspection_methods: list[InspectionMethodResult] = Field(default_factory=list)
    source_item_types: list[SourceItemTypeResult] = Field(default_factory=list)
    source_items: list[SourceItemResult] = Field(default_factory=list)
    customers: list[CustomerLookupResult] = Field(default_factory=list)
