"""
HTTP schemas for fabrication method (production process) creation,
updates, filtering, and responses.
"""

from datetime import datetime
from datetime import tzinfo
from typing import Any
from typing import ClassVar
from typing import Generic

from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LABEL_FIELD_DEFAULTS,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LabeledCatalogueFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LabeledCatalogueWriteRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import TLabel
from src.modules.catalogue.ports.outbound.repositories.fabrication_method_repository import (
    FabricationMethodFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import ResolvedLabel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ── Request schemas ───────────────────────────────────────────────────


class _FabricationMethodWriteRequest(LabeledCatalogueWriteRequest):
    """Fields shared by the fabrication method create and update requests."""

    _null_defaults: ClassVar[dict[str, Any]] = {
        **LABEL_FIELD_DEFAULTS,
        "requires_machine": True,
        "required_external": False,
        "default_for_assemblies": False,
    }

    requires_machine: bool | None = True
    required_external: bool | None = False
    default_supplier_id: int | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    default_for_assemblies: bool | None = False


class FabricationMethodCreateRequest(_FabricationMethodWriteRequest):
    pass


class FabricationMethodUpdateRequest(_FabricationMethodWriteRequest):
    pass


# ── Response schemas ──────────────────────────────────────────────────


class _FabricationMethodFields(EntityResponse, Generic[TLabel]):
    created: datetime
    changed: datetime
    name: TLabel
    label_color: str
    label_font_color: str
    description: TLabel
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    requires_machine: bool = True
    required_external: bool = False
    default_supplier_id: int | None = None
    default_for_assemblies: bool = False
    archived: bool = False


# The pat shape: `name` and `description` in the request's label languages.
class FabricationMethodResponse(_FabricationMethodFields[ResolvedLabel]):
    # Place in the hand-kept order the pickers offer the entries in. The
    # add-in's cached lookups arrive in id order, so it sorts by this; the
    # web lists come in this order already and need no field for it.
    sort_order: int = 0


class FabricationMethodWebResponse(_FabricationMethodFields[dict[str, str]]):
    """The web shape: `name` and `description` as language maps, plus
    lead_time_days, which feeds the scheduler's external lead-time forecast
    and has no pat use (the SolidWorks add-in never reads or sets it)."""

    lead_time_days: int | None = None


# ── Filter params ─────────────────────────────────────────────────────


class FabricationMethodFilterParams(LabeledCatalogueFilterParams):
    def to_dto(self, zone: tzinfo, languages: tuple[str, ...] = ()) -> FabricationMethodFilterDto:
        return FabricationMethodFilterDto(
            **expand_change_window(self.model_dump(), zone), languages=languages
        )
