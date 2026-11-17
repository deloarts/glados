"""
Shared request and filter building blocks for the labeled catalogue
families: article groups, source item types, fabrication methods and
inspection methods. Each family keeps its own named Create, Update, Response
and FilterParams classes, since the class names are the OpenAPI component
names and the `pat` contract exposes them; these bases only carry the fields,
defaults and validation the four have in common. Response schemas stay per
family because their field sets and required fields differ.

`name` and `description` are language maps. Each family's response is a
generic base over the type those two fields have, with two concrete classes:
`<Family>Response` resolves them to one string in the request's label
languages for the `pat` surface (the SolidWorks add-in writes that string
into the vault), and `<Family>WebResponse` carries the whole map for the web
frontend, which edits every language and resolves the rest itself. The pat
class keeps the historical name and field order, so the `pat` contract does
not change.
"""

from datetime import date
from datetime import datetime
from typing import Any
from typing import ClassVar
from typing import Literal
from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import (
    LocalizedLongTextIn,
)
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import LocalizedTextIn
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams

# The type of `name` and `description` in a response: `ResolvedLabel` on the
# pat surface, the language map on the web surface.
TLabel = TypeVar("TLabel")

# What a null label or description field of a write request becomes.
LABEL_FIELD_DEFAULTS: dict[str, Any] = {
    "label_color": "#999999",
    "label_font_color": "#000000",
    "description": {},
}


def coerce_null_defaults(data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Replace every key of `defaults` that is missing or None in `data` with
    its default, in place, so a client may send null for an optional field
    and still get the documented default. Returns `data`."""
    for field, default in defaults.items():
        if data.get(field) is None:
            data[field] = default
    return data


class LabeledCatalogueWriteRequest(BaseModel):
    """Name, label colours and description of a create or update request.
    A subclass adds its own fields and widens `_null_defaults` with those of
    them whose null means "use the default"."""

    _null_defaults: ClassVar[dict[str, Any]] = LABEL_FIELD_DEFAULTS

    name: LocalizedTextIn
    label_color: str | None = "#999999"
    label_font_color: str | None = "#000000"
    description: LocalizedLongTextIn | None = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data: dict[str, Any]) -> dict[str, Any]:
        return coerce_null_defaults(data, cls._null_defaults)


class NamedCatalogueWriteRequest(BaseModel):
    """The same request for a family whose name and description are one
    plain string (product families)."""

    _null_defaults: ClassVar[dict[str, Any]] = {**LABEL_FIELD_DEFAULTS, "description": ""}

    name: str = Field(..., min_length=1)
    label_color: str | None = "#999999"
    label_font_color: str | None = "#000000"
    description: str | None = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_nulls(cls, data: dict[str, Any]) -> dict[str, Any]:
        return coerce_null_defaults(data, cls._null_defaults)


class LabeledCatalogueFilterParams(PageParams):
    """List query parameters of a labeled catalogue family. A subclass adds
    `to_dto`, building its own filter DTO from `model_dump()` passed through
    `expand_change_window`."""

    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    name: str | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    created_from: date | datetime | None = Query(default=None)
    created_to: date | datetime | None = Query(default=None)
    changed_from: date | datetime | None = Query(default=None)
    changed_to: date | datetime | None = Query(default=None)
    order_by: Literal["id", "name", "created", "changed"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)
