"""Turns raw PDM datacard variables into the values ingest writes.

Only the "@" file-level configuration is read, never whichever
configuration the Web API returned first. Only mapped fields present in
the payload come through; `kind`, the write-back fields, labels and the
feature-tree field never do. The coercions return None instead of raising,
so one malformed variable never fails a whole ingest.

parse_processes mirrors the SolidWorks add-in's JSON encoding and drops a
bad step individually. A step without `role` is malformed rather than
fabrication, so process_entry_missing_role lets callers reject the payload.
"""

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.domain.policies.item_field_ownership import BOUGHT_ITEM_MAPPABLE_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import MADE_ITEM_MAPPABLE_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import WRITEBACK_MAPPABLE_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import addin_written_fields
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables

# One reason text so every caller reports this condition identically.
NO_FILE_LEVEL_CONFIGURATION = "no file-level datacard configuration"

# What SolidWorks shows for a part without an assigned material, such as
# "Material <not specified>" or its translation. A real material name never
# ends in an angle-bracketed placeholder, so the whole value is dropped.
_MATERIAL_PLACEHOLDER = re.compile(r"^\s*(?:\S+\s+)?<[^<>]*>\s*$")


def _field_value(field: str, value: str) -> str:
    """The value ingest writes for a field. A SolidWorks material
    placeholder becomes empty, so it is not stored as a material that
    every raw stock then mismatches."""
    if field == "material" and _MATERIAL_PLACEHOLDER.match(value):
        return ""
    return value


# ── Configuration and field-mapping selection ───────────────────────────


def select_configuration(configs: list[PdmConfigVariables]) -> dict[str, str] | None:
    """The values of the "@" configuration. An empty list maps nothing;
    a non-empty list without "@" returns None, because every SolidWorks
    file has one and guessing another would read the wrong values."""
    if not configs:
        return {}
    for config in configs:
        if config.configuration_name == "@":
            return config.variables
    return None


def map_variables(
    kind: str, variable_map: dict[str, str], variables: dict[str, str]
) -> dict[str, str]:
    """Field values for every mappable field whose variable name is set
    and present in `variables`; the value itself may be empty. The `kind`
    entry, write-back and add-in-written fields are always excluded."""
    mappable = MADE_ITEM_MAPPABLE_FIELDS if kind == "made" else BOUGHT_ITEM_MAPPABLE_FIELDS
    addin_only = addin_written_fields(kind)
    mapped: dict[str, str] = {}
    for field in mappable:
        if field == "kind" or field in WRITEBACK_MAPPABLE_FIELDS or field in addin_only:
            continue
        variable_name = variable_map.get(field, "")
        if not variable_name:
            continue
        if variable_name not in variables:
            continue
        mapped[field] = _field_value(field, variables[variable_name])
    return mapped


def kind_variable_name(settings: AdminPdmSettings) -> str:
    """The kind variable name from the made map (both maps must agree)."""
    return settings.made_item_variable_map["kind"]


@dataclass(frozen=True)
class FileKindResolution:
    kind: str | None  # resolved "made"/"bought"; None when unresolved
    raw: str  # the raw kind variable value read, "" when absent/blank
    conflict: str | None  # set only for an explicit-folder disagreement


def resolve_file_kind(
    *, folder_kind: str, variables: dict[str, str], settings: AdminPdmSettings
) -> FileKindResolution:
    """A by_kind folder takes the kind from the datacard, and anything but
    "made" or "bought" leaves it unresolved. An explicit folder's kind
    wins, but a disagreeing datacard value is reported as a conflict."""
    variable_name = kind_variable_name(settings)
    raw = (variables.get(variable_name) or "").strip()
    if folder_kind == "by_kind":
        resolved = raw if raw in ("made", "bought") else None
        return FileKindResolution(kind=resolved, raw=raw, conflict=None)
    if raw and raw != folder_kind:
        return FileKindResolution(
            kind=None, raw=raw, conflict=f"kind variable says {raw}, folder says {folder_kind}"
        )
    return FileKindResolution(kind=folder_kind, raw=raw, conflict=None)


# ── Coercions ────────────────────────────────────────────────────────────


def _round_half_away_from_zero(value: float) -> int:
    """Matches the SolidWorks add-in's own ParseMassGrams rounding
    (Math.Round(..., MidpointRounding.AwayFromZero)) rather than Python's
    round-half-to-even, so the same mass string rounds identically on
    both sides of the integration."""
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def parse_mass(raw: str | None) -> int | None:
    """A mass with comma or dot decimals, rounded to grams. Unparsable input
    is None rather than 0, so no mass and zero mass stay distinct."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None
    return _round_half_away_from_zero(value)


def parse_date(raw: str | None) -> date | None:
    """ISO (`YYYY-MM-DD`) or German-style (`DD.MM.YYYY`) date text. Empty
    or unrecognised input returns None."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    return None


def parse_int_list(raw: str | None) -> list[int]:
    """Comma-separated integer ids; bad tokens are skipped individually."""
    if raw is None:
        return []
    result: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            result.append(int(token))
        except ValueError:
            continue
    return result


def parse_int(raw: str | None) -> int | None:
    """A single integer id, None when unparsable."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_edp_part_id(raw: str | None) -> int | None:
    """An EPLAN Data Portal part id. Blank, unparsable and non-positive
    values all read as no part."""
    value = parse_int(raw)
    return value if value is not None and value > 0 else None


def _parsed_process_entries(raw: str | None) -> list[dict[str, Any]] | None:
    """The dict entries of the Glados.Processes array, or None when it is
    not a parseable array."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    return [entry for entry in data if isinstance(entry, dict)]


def _entry_role(entry: dict[str, Any]) -> str | None:
    role = entry.get("role")
    return role.strip() if isinstance(role, str) and role.strip() else None


def parse_processes(raw: str | None) -> list[CreateMadeItemProcessCommand]:
    """Parses the routing. Top-level garbage yields an empty list, and a
    malformed or role-less step is dropped on its own."""
    entries = _parsed_process_entries(raw)
    if entries is None:
        return []

    steps: list[CreateMadeItemProcessCommand] = []
    for entry in entries:
        role = _entry_role(entry)
        if role is None:
            continue
        try:
            steps.append(
                CreateMadeItemProcessCommand(
                    role=role,
                    fabrication_method_id=entry.get("fabrication_method_id"),
                    inspection_method_id=entry.get("inspection_method_id"),
                    note=entry.get("note"),
                    estimated_setup_minutes=entry.get("estimated_setup_minutes"),
                    estimated_minutes_per_piece=entry.get("estimated_minutes_per_piece"),
                    group_index=entry.get("group_index"),
                )
            )
        except (TypeError, ValidationError):
            continue
    return steps


def process_entry_missing_role(raw: str | None) -> bool:
    """True when a routing entry has no `role`. The add-in always writes it,
    so callers reject such a payload instead of losing the step."""
    entries = _parsed_process_entries(raw)
    if entries is None:
        return False
    return any(_entry_role(entry) is None for entry in entries)
