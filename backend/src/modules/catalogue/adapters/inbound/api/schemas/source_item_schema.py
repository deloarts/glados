"""
HTTP schemas for the SourceItem catalogue aggregate.
"""

from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Generic
from typing import Literal
from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.delivery_tolerance_schema import (
    DeliveryToleranceFields,
)
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import ResolvedLabel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

TLabel = TypeVar("TLabel")

# ══════════════════════════════════════════════════════════════════════
# SourceItem (catalogue)
# ══════════════════════════════════════════════════════════════════════


class SourceItemCreateRequest(BaseModel):
    type_id: int
    dimension: str | None = None
    material: str = Field(..., min_length=1)
    mass: int | None = None
    note: str | None = None
    order_code_1: str | None = None
    order_code_2: str | None = None
    status: SourceItemCatalogueStatus = SourceItemCatalogueStatus.ACTIVE
    manufacturer_id: int | None = None


class SourceItemWebCreateRequest(SourceItemCreateRequest, DeliveryToleranceFields):
    """The web form's create, which also sets the item's delivery tolerances."""


class SourceItemUpdateRequest(DeliveryToleranceFields):
    type_id: int
    dimension: str | None = None
    material: str = Field(..., min_length=1)
    mass: int | None = None
    note: str | None = None
    order_code_1: str | None = None
    order_code_2: str | None = None
    # No default: an update that leaves the status out is refused instead of
    # setting the item active again.
    status: SourceItemCatalogueStatus
    manufacturer_id: int | None = None
    approver_id: int | None = None
    successor_item_id: int | None = None
    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


class _SourceItemFields(EntityResponse, Generic[TLabel]):
    status: SourceItemCatalogueStatus
    created: datetime
    changed: datetime
    archived: bool
    type_id: int
    type_name: TLabel
    dimension: str | None
    material: str
    mass: int | None
    note: str | None
    order_code_1: str | None
    order_code_2: str | None
    successor_item_id: int | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    approver_id: int | None
    manufacturer_id: int | None
    manufacturer_name: str
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


# The pat shape: catalogue labels in the request's label languages.
class SourceItemResponse(_SourceItemFields[ResolvedLabel]):
    pass


class SourceItemWebResponse(_SourceItemFields[dict[str, str]]):
    """The web shape: catalogue labels as language maps."""


class SourceItemFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    status: SourceItemCatalogueStatus | None = Query(default=None)
    type_id: int | None = Query(default=None)
    material: str | None = Query(default=None)
    dimension: str | None = Query(default=None)
    note: str | None = Query(default=None)
    order_code_1: str | None = Query(default=None)
    order_code_2: str | None = Query(default=None)
    successor_item_id: int | None = Query(default=None)
    manufacturer_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    approver_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    created_from: date | datetime | None = Query(default=None)
    created_to: date | datetime | None = Query(default=None)
    changed_from: date | datetime | None = Query(default=None)
    changed_to: date | datetime | None = Query(default=None)
    order_by: Literal["id", "changed", "created"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self, zone: tzinfo) -> SourceItemFilterDto:
        return SourceItemFilterDto(**expand_change_window(self.model_dump(), zone))


class SourceItemWebFilterParams(SourceItemFilterParams):
    """The web catalogue's list filter. It adds `ids`, with which live
    row-sync refetches the rows a signal names, and stays off the `pat` list
    so its frozen snapshot does not change. Bound as `Annotated[...,
    Query()]`, since only that binds `ids` from repeated query keys, see the
    note on DemandItemFilterParams in bought_item_demand_schema.py."""

    ids: list[int] | None = Query(default=None, max_length=200)
