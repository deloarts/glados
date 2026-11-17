"""Read-only enforcement on PDM-owned (CAD) catalogue rows and the part
number space the CAD source reserves for ingest, per
docs/FIELD_OWNERSHIP.md. Turns the ownership table into the owned fields,
the blocked changes and the fields locked for display.

The caller decides whether to enforce at all, from the CAD source's policy
(`CadPolicy.enforces_ownership_for`); this module never reads settings or
an actor.
"""

import re

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.errors import PartNumberReservedForPdmError
from src.modules.catalogue.domain.errors import PdmOwnedFieldReadOnlyError
from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.catalogue.domain.value_objects.data_source import DataSource

# Dual-owned fields (owner "addin_web": source_item_id, edp_part_id) are
# deliberately excluded: principle 7 lets a web edit stand until the CAD
# value itself changes, so field-level enforcement must not block it.
_OWNED_BY_PDM = frozenset({"pdm", "addin"})


def pdm_owned_fields(kind: str) -> frozenset[str]:
    """Fields of `kind` owned by "pdm" or "addin"."""
    return frozenset(f.field for f in item_fields()[kind] if f.owner in _OWNED_BY_PDM)


def blocked_pdm_owned_changes(
    kind: str, item: MadeItem | BoughtItem, changes: dict[str, object]
) -> set[str]:
    """PDM-owned fields in `changes` whose value differs from `item`'s.
    Unknown fields are ignored, so a whole command dict can be passed;
    lists compare as sets."""
    owned = pdm_owned_fields(kind)
    blocked: set[str] = set()
    for field, new_value in changes.items():
        if field not in owned or not hasattr(item, field):
            continue
        old_value = getattr(item, field)
        if isinstance(old_value, list) and isinstance(new_value, list):
            changed = set(old_value) != set(new_value)
        else:
            changed = old_value != new_value
        if changed:
            blocked.add(field)
    return blocked


def pdm_locked_fields(*, kind: str, enforce: bool, item_data_source: str) -> list[str]:
    """The sorted fields a write would currently refuse, for display.
    Decided exactly like assert_cad_row_writable, so the two cannot drift."""
    if not enforce or item_data_source != DataSource.CAD.value:
        return []
    return sorted(pdm_owned_fields(kind))


def assert_cad_row_writable(*, enforce: bool, item_data_source: str, blocked: set[str]) -> None:
    """Raises when enforcement is on, the row is CAD-owned and a blocked
    field changed."""
    if enforce and item_data_source == DataSource.CAD.value and blocked:
        raise PdmOwnedFieldReadOnlyError(
            f"Field(s) {sorted(blocked)} are managed by PDM and cannot be changed here."
        )


def assert_part_number_not_pdm_reserved(part_number: str, pattern: str, *, enabled: bool) -> None:
    """Rejects a typed part number matching the PDM pattern while the
    integration is enabled, since that number space belongs to ingest."""
    if enabled and pattern and re.fullmatch(pattern, part_number):
        raise PartNumberReservedForPdmError(
            f"Part number {part_number!r} matches the external (PDM) pattern and is "
            "reserved for PDM ingest."
        )
