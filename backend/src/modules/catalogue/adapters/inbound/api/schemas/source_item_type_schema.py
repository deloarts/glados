"""HTTP schemas for source item type operations: creating and updating item categories
with label styling and descriptions."""

from datetime import datetime
from datetime import tzinfo
from typing import Generic

from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LabeledCatalogueFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LabeledCatalogueWriteRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import TLabel
from src.modules.catalogue.ports.outbound.repositories.source_item_type_repository import (
    SourceItemTypeFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import ResolvedLabel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ── Request schemas ───────────────────────────────────────────────────


class SourceItemTypeCreateRequest(LabeledCatalogueWriteRequest):
    pass


class SourceItemTypeUpdateRequest(LabeledCatalogueWriteRequest):
    pass


# ── Response schemas ──────────────────────────────────────────────────


class _SourceItemTypeFields(EntityResponse, Generic[TLabel]):
    created: datetime
    changed: datetime
    archived: bool
    name: TLabel
    label_color: str
    label_font_color: str
    description: TLabel
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None


# The pat shape: `name` and `description` in the request's label languages.
class SourceItemTypeResponse(_SourceItemTypeFields[ResolvedLabel]):
    # Place in the hand-kept order the pickers offer the entries in. The
    # add-in's cached lookups arrive in id order, so it sorts by this; the
    # web lists come in this order already and need no field for it.
    sort_order: int = 0


class SourceItemTypeWebResponse(_SourceItemTypeFields[dict[str, str]]):
    """The web shape: `name` and `description` as language maps."""


# ── Filter params ─────────────────────────────────────────────────────


class SourceItemTypeFilterParams(LabeledCatalogueFilterParams):
    def to_dto(self, zone: tzinfo, languages: tuple[str, ...] = ()) -> SourceItemTypeFilterDto:
        return SourceItemTypeFilterDto(
            **expand_change_window(self.model_dump(), zone), languages=languages
        )
