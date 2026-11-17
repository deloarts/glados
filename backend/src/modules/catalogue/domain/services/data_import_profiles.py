"""
The fields of every spreadsheet import and the rules for its import profile.

The field keys are the payload keys of the import's row, so a profile's
column names map straight onto the row the frontend sends. Which fields a
row must carry is the import's own business (the demand imports need a
project and a quantity, the bought-item create needs an order code), so this
catalogue only lists the fields a column can be mapped to.

Column names are compared after normalize_column_name(), the same way the
frontend compares a spreadsheet header, so `Order Code` and ` order  code `
are one name. A name may map to only one field of a profile, otherwise a
header would be ambiguous.
"""

import re

from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.errors import DataImportRowLimitExceededError
from src.modules.catalogue.domain.errors import DataImportSettingsInvalidError
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType

MAX_ROWS_LIMIT = 1000
MAX_HEADER_ROW = 100
MAX_DATA_OFFSET = 100
MAX_COLUMN_NAME_LENGTH = 120
MAX_COLUMN_NAMES_PER_FIELD = 50

IMPORT_FIELDS: dict[DataImportType, tuple[str, ...]] = {
    DataImportType.BOUGHT_ITEM_CREATE: (
        "article_name",
        "order_code_1",
        "manufacturer_name",
        "edp_part_number",
        "order_code_2",
        "gtin",
        "ean",
        "tariff_number",
        "mass",
        "note",
        "weblink",
        "article_group_names",
        "product_family_name",
        "part_number",
    ),
    DataImportType.BOUGHT_ITEM_DEMAND: (
        "project_number",
        "quantity",
        "unit",
        "part_number",
        "article_name",
        "order_code",
        "manufacturer_name",
        "desired_delivery_date",
        "note",
    ),
    DataImportType.MADE_ITEM_DEMAND: (
        "project_number",
        "quantity",
        "part_number",
        "revision",
        "article_name",
        "desired_delivery_date",
        "note",
    ),
}

_WHITESPACE = re.compile(r"\s+")


def normalize_column_name(name: str) -> str:
    """The comparison form of a column name: trimmed, lower case, inner
    whitespace collapsed to one space."""
    return _WHITESPACE.sub(" ", name.strip()).lower()


def validate_profile(import_type: DataImportType, profile: DataImportProfile) -> DataImportProfile:
    """Returns the profile with trimmed, deduplicated column names in the
    catalogue's field order. Raises DataImportSettingsInvalidError for a
    header row, data offset or row limit out of range, an unknown field, an
    empty or overlong name, or a name mapped to two fields."""
    label = import_type.value
    if profile.header_row is not None and not 1 <= profile.header_row <= MAX_HEADER_ROW:
        raise DataImportSettingsInvalidError(
            f"{label}: the header row must be between 1 and {MAX_HEADER_ROW}."
        )
    if not 1 <= profile.data_offset <= MAX_DATA_OFFSET:
        raise DataImportSettingsInvalidError(
            f"{label}: the data offset must be between 1 and {MAX_DATA_OFFSET}."
        )
    if not 1 <= profile.max_rows <= MAX_ROWS_LIMIT:
        raise DataImportSettingsInvalidError(
            f"{label}: the row limit must be between 1 and {MAX_ROWS_LIMIT}."
        )

    fields = IMPORT_FIELDS[import_type]
    unknown = sorted(set(profile.column_names) - set(fields))
    if unknown:
        raise DataImportSettingsInvalidError(f"{label}: unknown field(s) {unknown}.")

    owner_by_name: dict[str, str] = {}
    cleaned: dict[str, list[str]] = {}
    for field_key in fields:
        names: list[str] = []
        seen: set[str] = set()
        for raw in profile.column_names.get(field_key, []):
            name = _WHITESPACE.sub(" ", raw.strip())
            if not name:
                raise DataImportSettingsInvalidError(
                    f"{label}: field {field_key!r} has an empty column name."
                )
            if len(name) > MAX_COLUMN_NAME_LENGTH:
                raise DataImportSettingsInvalidError(
                    f"{label}: column name {name!r} is longer than "
                    f"{MAX_COLUMN_NAME_LENGTH} characters."
                )
            key = normalize_column_name(name)
            if key in seen:
                continue
            owner = owner_by_name.get(key)
            if owner is not None:
                raise DataImportSettingsInvalidError(
                    f"{label}: column name {name!r} is used by both {owner!r} and {field_key!r}."
                )
            seen.add(key)
            owner_by_name[key] = field_key
            names.append(name)
        if len(names) > MAX_COLUMN_NAMES_PER_FIELD:
            raise DataImportSettingsInvalidError(
                f"{label}: field {field_key!r} has more than "
                f"{MAX_COLUMN_NAMES_PER_FIELD} column names."
            )
        if names:
            cleaned[field_key] = names

    return DataImportProfile(
        header_row=profile.header_row,
        data_offset=profile.data_offset,
        max_rows=profile.max_rows,
        column_names=cleaned,
    )


def assert_row_count_within_limit(
    import_type: DataImportType, profile: DataImportProfile, row_count: int
) -> None:
    """Raises DataImportRowLimitExceededError when an upload holds more data
    rows than the import's profile allows. The frontend refuses such a file
    already; this guards the validate and commit endpoints themselves."""
    if row_count > profile.max_rows:
        raise DataImportRowLimitExceededError(
            f"The {import_type.value} import accepts at most {profile.max_rows} rows, "
            f"got {row_count}."
        )
