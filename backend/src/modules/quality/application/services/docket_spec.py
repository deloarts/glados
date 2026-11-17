"""
Parsing and validation for a docket's JSON block-list source: the docket
counterpart of zpl_template.py. No str.format()/eval() involved at all
here: pydantic validates structure, and rendering (docket_renderer.py)
only ever reads block fields, never executes anything from the JSON.
"""

import json

from pydantic import ValidationError

from src.modules.quality.application.services.print_field_scopes import is_row_source
from src.modules.quality.ports.outbound.docket_spec_dto import DocketSpec
from src.modules.quality.ports.outbound.docket_spec_dto import ImageBlock
from src.modules.quality.ports.outbound.docket_spec_dto import QrBlock
from src.modules.quality.ports.outbound.docket_spec_dto import TextBlock


def parse_docket_spec(source: str) -> DocketSpec:
    """Raises ValueError on malformed JSON or a spec that fails validation."""
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Docket spec is not valid JSON: {exc}") from exc

    try:
        return DocketSpec.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Docket spec failed validation: {exc}") from exc


def _is_renderer_provided(field: str) -> bool:
    """A block may reference a pseudo-field the RENDERER supplies per page
    (@page_number, @page_count, @page_label) rather than a field_map key.
    Those need no mapping and must not be reported as missing, see
    docket_pagination.PAGE_FIELDS."""
    return field.startswith("@")


def fields_in_docket_spec(spec: DocketSpec) -> set[str]:
    """Every field_map key the spec references: ordinary blocks plus the
    positions table's column stacks, for the frontend's auto-detected
    field-map editor and for validate_docket_spec below. Renderer-provided
    pseudo-fields are excluded: they are not mappable."""
    fields: set[str] = set()
    for block in spec.blocks:
        if isinstance(block, TextBlock) and block.field:  # TextBlock.field is
            # `str | None` (mutually exclusive with `text`) while ImageBlock/QrBlock.field is a
            # plain `str`; merging with `or` would lose the narrowing mypy needs for the `.add()`
            # call below to type-check.
            fields.add(block.field)
        elif isinstance(block, ImageBlock | QrBlock):
            fields.add(block.field)

    if spec.table:
        for column in spec.table.columns:
            fields.update(column.fields)

    return {field for field in fields if not _is_renderer_provided(field)}


def row_fields_in_docket_spec(spec: DocketSpec) -> set[str]:
    """Just the table's column fields: the placeholders resolved once PER
    ROW rather than once per document."""
    if not spec.table:
        return set()
    return {
        field
        for column in spec.table.columns
        for field in column.fields
        if not _is_renderer_provided(field)
    }


def validate_docket_spec(source: str, field_map: dict[str, str]) -> None:
    """Raises ValueError if the spec is malformed, references a field_map
    key that isn't mapped, or mixes the two value scopes up: the docket
    counterpart of validate_zpl_template.

    Scope matters because a row placeholder is resolved against an
    OrderItemResult and a document placeholder against the root: mapping a
    column to a root field would silently print the same value down every
    row, and mapping a header block to an "item.*" source would print
    nothing at all. Both are caught here instead of at render time."""
    spec = parse_docket_spec(source)
    referenced = fields_in_docket_spec(spec)

    missing = referenced - field_map.keys()
    if missing:
        raise ValueError(f"Docket spec references unmapped field(s): {', '.join(sorted(missing))}.")

    row_fields = row_fields_in_docket_spec(spec)
    wrong_scope = sorted(
        placeholder
        for placeholder in referenced
        if is_row_source(field_map[placeholder]) is not (placeholder in row_fields)
    )
    if wrong_scope:
        raise ValueError(
            "Docket spec maps field(s) to the wrong value scope "
            f"({', '.join(wrong_scope)}): table columns need an 'item.*' or row-image "
            "source, and every other block needs a document-level one."
        )
