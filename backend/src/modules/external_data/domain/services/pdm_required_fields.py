"""The required-field catalogue for PDM ingest (see docs/PDM_INTEGRATION.md):
the locked fields no row can be created without, pseudo-rules that are not
a single column, and the candidates an admin may additionally require.
The evaluation itself lives in application/services/pdm_required_fields.py
because it needs application-layer types."""

from collections.abc import Sequence
from dataclasses import dataclass

from src.modules.catalogue.domain.policies.item_field_ownership import addin_written_fields
from src.modules.catalogue.domain.policies.item_field_ownership import item_fields

# Never configurable, in the order a missing-fields message lists them.
# Bought items are keyed by part number alone, so their revision is only a
# candidate (required by default).
LOCKED_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "made": ("part_number", "revision", "article_name"),
    "bought": ("part_number", "article_name", "order_code_1", "manufacturer_id"),
}


@dataclass(frozen=True)
class RequiredFieldRule:
    """A required field satisfied by a condition on the parsed data rather
    than one non-empty column."""

    name: str


# Satisfied by at least one fabrication process with a method.
REQUIRED_FIELD_RULES: dict[str, tuple[RequiredFieldRule, ...]] = {
    "made": (RequiredFieldRule(name="fabrication_step"),),
    "bought": (),
}


def required_field_candidates(kind: str) -> list[str]:
    """Configurable required fields for `kind`: mappable fields that are
    neither locked nor add-in-written (ingest never reads those), then the
    pseudo-rules."""
    excluded = set(LOCKED_REQUIRED_FIELDS[kind]) | addin_written_fields(kind)
    field_names = [f.field for f in item_fields()[kind] if f.mappable and f.field not in excluded]
    rule_names = [rule.name for rule in REQUIRED_FIELD_RULES[kind]]
    return field_names + rule_names


def normalize_required_fields_selection(kind: str, names: Sequence[str]) -> list[str]:
    """Drops locked names and duplicates, keeping order, and raises
    ValueError for a name that is not a candidate."""
    candidates = set(required_field_candidates(kind))
    locked = set(LOCKED_REQUIRED_FIELDS[kind])
    result: list[str] = []
    seen: set[str] = set()
    unknown: list[str] = []
    for name in names:
        if name in locked or name in seen:
            continue
        seen.add(name)
        if name in candidates:
            result.append(name)
        else:
            unknown.append(name)
    if unknown:
        raise ValueError(f"Unknown required field(s) for {kind} items: {sorted(set(unknown))}.")
    return result
