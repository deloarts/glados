"""
What a template's field map is allowed to reference, for the frontend's
field-map editor (GET /print-templates/{classifier}/field-sources) and for
validating a PATCH before it is saved. There are three namespaces:

- A bare name is a field on the classifier's result_dto, derived from
  pydantic model_fields so it stays in sync with the DTO automatically.
- An @computed name is supplied by the print root resolver at render time
  (dates, URLs, docket-only image sources).
- An @event_quantity name is only offered when the bound trigger carries a
  per-occurrence quantity (see TriggerSpec.has_event_quantity).

A root often denormalizes OTHER records' public_ids alongside its own:
e.g. production_order_label's root carries lot_public_id and
made_item_public_id, so a label can QR-code the lot or the item instead of
the production order itself. Every "*_public_id" bare field beyond the
root's own `public_id` gets a matching "@resolve_url:<field>" (and, for
dockets, "@qr_image:<field>") computed source, named and described after
the field so the field-map editor and @resolve_url's own listing both make
clear which record each one targets. See related_uuid_fields_for().
"""

from dataclasses import dataclass

from pydantic import BaseModel

from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_classifiers import TRIGGERS
from src.modules.quality.application.services.print_field_scopes import ROW_IMAGE_SOURCE
from src.modules.quality.application.services.print_field_scopes import ROW_SOURCE_PREFIX
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger


@dataclass(frozen=True)
class FieldSource:
    name: str
    kind: str  # "bare" | "computed" | "row"
    description: str


_COMPUTED_COMMON: tuple[FieldSource, ...] = (
    FieldSource("@today", "computed", "Today's date"),
    FieldSource("@actor_full_name", "computed", "Full name of the user who triggered the print"),
    FieldSource(
        "@resolve_url",
        "computed",
        "URL that resolves THIS record's own public_id (QR target)",
    ),
    # Text-valued, so it works for ZPL too, unlike the image-valued sources
    # below; resolve_field_values() resolves it the same way regardless
    # of output_kind, this list is the only thing that was gating it.
    FieldSource("@company_name", "computed", "Company name (admin settings)"),
)

_COMPUTED_DOCKET_ONLY: tuple[FieldSource, ...] = (
    FieldSource("@part_image", "computed", "Part photo, if the item has one on file"),
    FieldSource("@company_logo", "computed", "Company logo (admin settings)"),
    FieldSource("@qr_image", "computed", "QR code for THIS record's own public_id"),
)

_EVENT_QUANTITY = FieldSource(
    "@event_quantity", "computed", "The quantity of this specific occurrence (delivery, completion)"
)

# Document scope, not row scope: it describes the table rather than sitting
# in it, so a header block prints it ("POSITIONS: 5"). Only offered for a
# classifier that HAS a table; there is nothing to count otherwise.
_ROW_COUNT = FieldSource(
    "@row_count", "computed", "Number of rows in the positions table (e.g. POSITIONS)"
)


def _related_record_label(field_name: str) -> str:
    """The human-readable label for a related-record field name, e.g.
    "made_item_public_id" -> "made item", "lot_public_id" -> "lot"."""
    return field_name.removesuffix("_public_id").replace("_", " ")


def related_uuid_fields_for(classifier: PrintClassifier) -> list[str]:
    """Every bare "*_public_id" field on the classifier's root besides its
    own `public_id`; other records this root already carries the id of,
    denormalized by the repository mapper (see production_order_dto.py /
    production_lot_dto.py)."""
    return [
        name
        for name in CLASSIFIERS[classifier].result_dto.model_fields
        if name != "public_id" and name.endswith("_public_id")
    ]


def _is_scalar_field(annotation: object) -> bool:
    """Exclude the root's own child collection (OrderResult.items) from the
    bare list: it is the table's row source, not a value a text block can
    print. Nested single models (creator, …) stay; they stringify to
    something, however ugly, and excluding them would be a behaviour change
    for the existing classifiers."""
    return not str(annotation).startswith("list[")


def field_sources_for(
    classifier: PrintClassifier, trigger: PrintTrigger | None
) -> list[FieldSource]:
    spec = CLASSIFIERS[classifier]

    sources = [
        FieldSource(name, "bare", name)
        for name, info in spec.result_dto.model_fields.items()
        if _is_scalar_field(info.annotation)
    ]
    sources.extend(_COMPUTED_COMMON)
    for field_name in related_uuid_fields_for(classifier):
        label = _related_record_label(field_name)
        sources.append(
            FieldSource(
                f"@resolve_url:{field_name}",
                "computed",
                f"URL that resolves the {label}'s public_id ({field_name})",
            )
        )
    if spec.output_kind == PrintOutputKind.PDF_DOCKET:
        sources.extend(_COMPUTED_DOCKET_ONLY)
        for field_name in related_uuid_fields_for(classifier):
            label = _related_record_label(field_name)
            sources.append(
                FieldSource(
                    f"@qr_image:{field_name}",
                    "computed",
                    f"QR code for the {label}'s public_id ({field_name})",
                )
            )
    if spec.has_rows:
        sources.append(_ROW_COUNT)
        sources.extend(_row_sources(spec.row_dto))
    if trigger is not None and TRIGGERS[trigger].has_event_quantity:
        sources.append(_EVENT_QUANTITY)

    return sources


def _row_sources(row_dto: type[BaseModel] | None) -> list[FieldSource]:
    """The "item.*" namespace: one source per scalar field of the row DTO,
    plus the per-row part photo. Only offered for a classifier whose
    document repeats over a list, and only ever valid inside a table
    column; see validate_docket_spec, which rejects the two scopes being
    crossed."""
    if row_dto is None:
        return []

    sources = [
        FieldSource(f"{ROW_SOURCE_PREFIX}{name}", "row", f"{name} of this table row (per position)")
        for name, info in row_dto.model_fields.items()
        if _is_scalar_field(info.annotation)
    ]
    sources.append(
        FieldSource(ROW_IMAGE_SOURCE, "row", "Part photo of this table row's item, if any")
    )
    return sources


def valid_source_names(classifier: PrintClassifier, trigger: PrintTrigger | None) -> set[str]:
    return {source.name for source in field_sources_for(classifier, trigger)}
