"""
HTTP schemas for inspection (QA) method creation, updates, filtering, and
responses.
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
from src.modules.catalogue.ports.outbound.repositories.inspection_method_repository import (
    InspectionMethodFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import ResolvedLabel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

# ── Request schemas ───────────────────────────────────────────────────


class _InspectionMethodWriteRequest(LabeledCatalogueWriteRequest):
    """Fields shared by the inspection method create and update requests."""

    _null_defaults: ClassVar[dict[str, Any]] = {
        **LABEL_FIELD_DEFAULTS,
        "requires_evidence": False,
    }

    # Left out of _null_defaults on purpose: null means "this method has no
    # default duration"/"no default QA machine", which is meaningful, not a
    # missing value to coerce.
    default_setup_minutes: int | None = Field(default=None, ge=0)
    default_minutes_per_piece: float | None = Field(default=None, ge=0)
    wait_after_minutes: int | None = Field(default=None, ge=0)
    requires_evidence: bool | None = False
    default_machine_id: int | None = None


class InspectionMethodCreateRequest(_InspectionMethodWriteRequest):
    pass


class InspectionMethodUpdateRequest(_InspectionMethodWriteRequest):
    pass


# ── Response schemas ──────────────────────────────────────────────────


class _InspectionMethodFields(EntityResponse, Generic[TLabel]):
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
    default_setup_minutes: int | None = None
    default_minutes_per_piece: float | None = None
    requires_evidence: bool = False
    archived: bool = False
    default_machine_id: int | None = None
    default_machine_name: str | None = None


# The pat shape: `name` and `description` in the request's label languages.
class InspectionMethodResponse(_InspectionMethodFields[ResolvedLabel]):
    # Place in the hand-kept order the pickers offer the entries in. The
    # add-in's cached lookups arrive in id order, so it sorts by this; the
    # web lists come in this order already and need no field for it.
    sort_order: int = 0


class InspectionMethodWebResponse(_InspectionMethodFields[dict[str, str]]):
    """The web shape: `name` and `description` as language maps, plus
    wait_after_minutes, the wait the scheduler adds after a check of the
    method, which has no pat use."""

    wait_after_minutes: int | None = None


# ── Filter params ─────────────────────────────────────────────────────


class InspectionMethodFilterParams(LabeledCatalogueFilterParams):
    def to_dto(self, zone: tzinfo, languages: tuple[str, ...] = ()) -> InspectionMethodFilterDto:
        return InspectionMethodFilterDto(
            **expand_change_window(self.model_dump(), zone), languages=languages
        )
