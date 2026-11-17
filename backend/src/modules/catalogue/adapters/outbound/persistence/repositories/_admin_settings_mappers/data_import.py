"""
Row mapping for the admin_data_import_settings singleton. The profiles JSON
is read leniently: a value of the wrong shape falls back to the profile
default instead of failing every import, since a broken row can only come
from a hand edit and the settings tab shows and saves the repaired profile.
"""

from typing import Any

from src.modules.catalogue.adapters.outbound.persistence.models.admin_settings_model.data_import import (
    AdminDataImportSettingsOrmModel,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import DEFAULT_DATA_OFFSET
from src.modules.catalogue.domain.entities.admin_settings.data_import import DEFAULT_MAX_ROWS
from src.modules.catalogue.domain.entities.admin_settings.data_import import AdminDataImportSettings
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile


def _int_or(value: Any, default: int | None) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def profile_from_json(raw: Any) -> DataImportProfile:
    if not isinstance(raw, dict):
        return DataImportProfile()
    names_raw = raw.get("column_names")
    column_names: dict[str, list[str]] = {}
    if isinstance(names_raw, dict):
        for field_key, names in names_raw.items():
            if isinstance(field_key, str) and isinstance(names, list):
                column_names[field_key] = [n for n in names if isinstance(n, str)]
    return DataImportProfile(
        header_row=_int_or(raw.get("header_row"), None),
        data_offset=_int_or(raw.get("data_offset"), DEFAULT_DATA_OFFSET) or DEFAULT_DATA_OFFSET,
        max_rows=_int_or(raw.get("max_rows"), DEFAULT_MAX_ROWS) or DEFAULT_MAX_ROWS,
        column_names=column_names,
    )


def profile_to_json(profile: DataImportProfile) -> dict[str, Any]:
    return {
        "header_row": profile.header_row,
        "data_offset": profile.data_offset,
        "max_rows": profile.max_rows,
        "column_names": {key: list(names) for key, names in profile.column_names.items()},
    }


def to_entity(o: AdminDataImportSettingsOrmModel) -> AdminDataImportSettings:
    raw = o.profiles if isinstance(o.profiles, dict) else {}
    return AdminDataImportSettings(
        id=o.id,
        public_id=o.public_id,
        profiles={key: profile_from_json(value) for key, value in raw.items()},
    )


def to_dict(s: AdminDataImportSettings) -> dict[str, Any]:
    return {
        "profiles": {key: profile_to_json(profile) for key, profile in s.profiles.items()},
    }


def empty_defaults() -> AdminDataImportSettings:
    """What a database without the row reads as: no stored profile, so every
    import type falls back to the empty default profile."""
    return AdminDataImportSettings(id=1, profiles={})
