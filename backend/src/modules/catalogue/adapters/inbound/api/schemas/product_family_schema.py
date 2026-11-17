"""
HTTP schemas for product family (category) creation, updates, filtering,
and responses.
"""

from datetime import datetime
from datetime import tzinfo

from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LabeledCatalogueFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    NamedCatalogueWriteRequest,
)
from src.modules.catalogue.ports.outbound.catalogue_queries import ProductFamilyFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ── Request schemas ───────────────────────────────────────────────────


class ProductFamilyCreateRequest(NamedCatalogueWriteRequest):
    pass


class ProductFamilyUpdateRequest(NamedCatalogueWriteRequest):
    pass


# ── Response schemas ──────────────────────────────────────────────────


class ProductFamilyResponse(EntityResponse):
    created: datetime
    changed: datetime
    archived: bool
    name: str
    label_color: str
    label_font_color: str
    description: str
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None


# ── Filter params ─────────────────────────────────────────────────────


class ProductFamilyFilterParams(LabeledCatalogueFilterParams):
    def to_dto(self, zone: tzinfo) -> ProductFamilyFilterDto:
        return ProductFamilyFilterDto(**expand_change_window(self.model_dump(), zone))
