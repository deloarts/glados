"""
The import profile rules (data_import_profiles.validate_profile), the row
limit guard, and the shipped seed: every import type gets a profile whose
column names pass the same rules an admin's save would.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.admin_settings_seed import _data_import_defaults
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.errors import DataImportRowLimitExceededError
from src.modules.catalogue.domain.errors import DataImportSettingsInvalidError
from src.modules.catalogue.domain.services.data_import_profiles import IMPORT_FIELDS
from src.modules.catalogue.domain.services.data_import_profiles import assert_row_count_within_limit
from src.modules.catalogue.domain.services.data_import_profiles import normalize_column_name
from src.modules.catalogue.domain.services.data_import_profiles import validate_profile
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType

_DEMAND = DataImportType.BOUGHT_ITEM_DEMAND


def test_data_import_normalize_column_name_trims_lowers_and_collapses_spaces() -> None:
    assert normalize_column_name("  Order   Code ") == "order code"


def test_data_import_validate_profile_cleans_names_in_field_order() -> None:
    profile = validate_profile(
        _DEMAND,
        DataImportProfile(
            column_names={
                "quantity": [" Qty ", "qty", "Menge"],
                "project_number": ["Project  number"],
            }
        ),
    )

    assert list(profile.column_names) == ["project_number", "quantity"]
    assert profile.column_names["quantity"] == ["Qty", "Menge"]
    assert profile.column_names["project_number"] == ["Project number"]


def test_data_import_validate_profile_drops_fields_without_names() -> None:
    profile = validate_profile(_DEMAND, DataImportProfile(column_names={"note": []}))

    assert profile.column_names == {}


@pytest.mark.parametrize(
    "profile",
    [
        DataImportProfile(header_row=0),
        DataImportProfile(data_offset=0),
        DataImportProfile(max_rows=0),
        DataImportProfile(max_rows=1001),
        DataImportProfile(column_names={"revision": ["Rev"]}),
        DataImportProfile(column_names={"note": ["  "]}),
        DataImportProfile(column_names={"note": ["x" * 121]}),
        DataImportProfile(column_names={"note": ["Note"], "article_name": ["note"]}),
    ],
    ids=[
        "header-row-zero",
        "offset-zero",
        "limit-zero",
        "limit-above-cap",
        "field-of-another-import",
        "blank-name",
        "overlong-name",
        "name-on-two-fields",
    ],
)
def test_data_import_validate_profile_refuses_invalid_profiles(
    profile: DataImportProfile,
) -> None:
    with pytest.raises(DataImportSettingsInvalidError):
        validate_profile(_DEMAND, profile)


def test_data_import_row_limit_allows_exactly_the_limit() -> None:
    # Must not raise: the limit itself is allowed.
    assert_row_count_within_limit(_DEMAND, DataImportProfile(max_rows=3), 3)


def test_data_import_row_limit_refuses_one_row_more() -> None:
    with pytest.raises(DataImportRowLimitExceededError):
        assert_row_count_within_limit(_DEMAND, DataImportProfile(max_rows=3), 4)


def test_data_import_seed_has_a_valid_profile_for_every_import_type() -> None:
    settings = _data_import_defaults()

    assert set(settings.profiles) == set(DataImportType.values())
    for import_type in DataImportType:
        profile = settings.profile(import_type)
        assert profile.header_row is None
        assert profile.data_offset == 1
        assert profile.max_rows == 100
        assert set(profile.column_names) <= set(IMPORT_FIELDS[import_type])
        assert validate_profile(import_type, profile) == profile


def test_data_import_seed_carries_no_column_names() -> None:
    """Column names are imported by an admin, never seeded."""
    for import_type in DataImportType:
        assert _data_import_defaults().profile(import_type).column_names == {}


def test_data_import_missing_profile_reads_as_the_empty_default() -> None:
    settings = _data_import_defaults()
    settings.profiles.pop(DataImportType.MADE_ITEM_DEMAND.value)

    assert settings.profile(DataImportType.MADE_ITEM_DEMAND) == DataImportProfile()
