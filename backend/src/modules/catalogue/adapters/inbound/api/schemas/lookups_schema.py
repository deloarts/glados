"""
HTTP schema for GET /pat/lookups. Reuses the six resources' existing
response schemas unchanged; this is purely an aggregate wrapper.
"""

from datetime import datetime

from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import SourceItemResponse
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.supplier_schema import SupplierResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class CustomerLookupResponse(ResponseModel):
    """The slim customer the add-in's customer-item picker needs."""

    id: int
    name: str
    archived: bool


class LookupsResponse(ResponseModel):
    server_time: datetime
    suppliers: list[SupplierResponse] = Field(default_factory=list)
    article_groups: list[ArticleGroupResponse] = Field(default_factory=list)
    fabrication_methods: list[FabricationMethodResponse] = Field(default_factory=list)
    inspection_methods: list[InspectionMethodResponse] = Field(default_factory=list)
    source_item_types: list[SourceItemTypeResponse] = Field(default_factory=list)
    source_items: list[SourceItemResponse] = Field(default_factory=list)
    customers: list[CustomerLookupResponse] = Field(default_factory=list)
