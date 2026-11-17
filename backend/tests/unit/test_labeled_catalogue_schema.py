"""
Unit tests for the shared schema pieces of the labeled catalogue families
(src/modules/catalogue/adapters/inbound/api/schemas/labeled_catalogue_schema.py) and for
expand_change_window in schemas/base.py, which every list filter with a
created and changed window uses. No database, no HTTP.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupFilterParams,
)
from src.modules.catalogue.adapters.inbound.api.schemas.fabrication_method_schema import (
    FabricationMethodUpdateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.inspection_method_schema import (
    InspectionMethodCreateRequest,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    LABEL_FIELD_DEFAULTS,
)
from src.modules.catalogue.adapters.inbound.api.schemas.labeled_catalogue_schema import (
    coerce_null_defaults,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_type_schema import (
    SourceItemTypeUpdateRequest,
)
from src.modules.catalogue.ports.outbound.catalogue_queries import ArticleGroupFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window

# ── coerce_null_defaults ────────────────────────────────────────────────


class TestCoerceNullDefaults:
    def test_coerce_null_defaults_fills_none_and_missing_keys(self):
        data = {"label_color": None, "description": "kept"}
        result = coerce_null_defaults(data, LABEL_FIELD_DEFAULTS)
        assert result is data
        assert data == {
            "label_color": "#999999",
            "label_font_color": "#000000",
            "description": "kept",
        }

    def test_coerce_null_defaults_keeps_falsy_non_null_values(self):
        data = {"flag": False, "text": ""}
        coerce_null_defaults(data, {"flag": True, "text": "default"})
        assert data == {"flag": False, "text": ""}


# ── write requests ──────────────────────────────────────────────────────


class TestLabeledCatalogueWriteRequest:
    @pytest.mark.parametrize("cls", [ArticleGroupCreateRequest, SourceItemTypeUpdateRequest])
    def test_write_request_null_label_fields_become_defaults(self, cls):
        body = cls.model_validate(
            {
                "name": {"enGB": "N"},
                "label_color": None,
                "label_font_color": None,
                "description": None,
            }
        )
        assert body.model_dump() == {
            "name": {"enGB": "N"},
            "label_color": "#999999",
            "label_font_color": "#000000",
            "description": {},
        }

    def test_write_request_inspection_method_coerces_its_own_default(self):
        body = InspectionMethodCreateRequest.model_validate(
            {"name": {"enGB": "N"}, "requires_evidence": None, "default_setup_minutes": None}
        )
        assert body.requires_evidence is False
        assert body.default_setup_minutes is None
        assert body.label_color == "#999999"

    def test_write_request_fabrication_method_coerces_its_own_defaults(self):
        body = FabricationMethodUpdateRequest.model_validate(
            {
                "name": {"enGB": "N"},
                "requires_machine": None,
                "required_external": None,
                "default_for_assemblies": None,
                "lead_time_days": None,
            }
        )
        assert body.requires_machine is True
        assert body.required_external is False
        assert body.default_for_assemblies is False
        assert body.lead_time_days is None

    def test_write_request_family_defaults_do_not_leak_into_the_base(self):
        body = ArticleGroupCreateRequest.model_validate({"name": {"enGB": "N"}})
        assert "requires_evidence" not in body.model_dump()
        assert "requires_evidence" not in LABEL_FIELD_DEFAULTS


# ── expand_change_window ────────────────────────────────────────────────


class TestExpandChangeWindow:
    def test_expand_change_window_expands_dates_to_day_bounds_in_the_tenant_timezone(self):
        data = {
            "created_from": date(2026, 6, 15),
            "created_to": date(2026, 6, 15),
            "changed_from": None,
            "changed_to": None,
        }
        result = expand_change_window(data, ZoneInfo("Europe/Vienna"))
        assert result is data
        # Vienna is UTC+2 in June.
        assert data["created_from"] == datetime(2026, 6, 14, 22, 0, tzinfo=UTC)
        assert data["created_to"] == datetime(2026, 6, 15, 21, 59, 59, 999999, tzinfo=UTC)
        assert data["changed_from"] is None
        assert data["changed_to"] is None

    def test_expand_change_window_passes_datetimes_through(self):
        value = datetime(2026, 6, 15, 8, 30, tzinfo=UTC)
        data = {
            "created_from": None,
            "created_to": None,
            "changed_from": value,
            "changed_to": value,
        }
        expand_change_window(data, ZoneInfo("Europe/Vienna"))
        assert data["changed_from"] == value
        assert data["changed_to"] == value


# ── filter params ───────────────────────────────────────────────────────


class TestLabeledCatalogueFilterParams:
    def test_filter_params_to_dto_builds_the_family_dto_with_expanded_window(self):
        params = ArticleGroupFilterParams(
            skip=0, limit=10, name="x", changed_to=date(2026, 1, 1), order_by="name"
        )
        dto = params.to_dto(UTC)
        assert isinstance(dto, ArticleGroupFilterDto)
        assert dto.name == "x"
        assert dto.limit == 10
        assert dto.include_archived is False
        assert dto.changed_to == datetime(2026, 1, 1, 23, 59, 59, 999999, tzinfo=UTC)
        assert dto.created_from is None
