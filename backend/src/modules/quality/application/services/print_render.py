"""
The one place a print template's `source` becomes bytes ready to send to a
printer, hand back as a download, or preview, dispatching on the
classifier's output_kind exactly once. PrintDocument, DownloadPrintDocument
and RenderPrintTemplateImage all call this, so "docket printing should work
for every ipp_document printer, and as a bare download" is true by
construction: nothing downstream of this function is printer-specific, and
nothing here requires a printer at all.
"""

from dataclasses import dataclass
from dataclasses import field
from functools import partial

from anyio import to_thread
from pydantic import BaseModel

from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.docket_pagination import DocketRow
from src.modules.quality.application.services.docket_pagination import paginate
from src.modules.quality.application.services.docket_spec import parse_docket_spec
from src.modules.quality.application.services.docket_spec import row_fields_in_docket_spec
from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_classifiers import ClassifierSpec
from src.modules.quality.application.services.print_value_resolver import resolve_field_values
from src.modules.quality.application.services.print_value_resolver import resolve_image_sources
from src.modules.quality.application.services.print_value_resolver import resolve_row_images
from src.modules.quality.application.services.print_value_resolver import resolve_row_values
from src.modules.quality.domain.entities.print_template import PrintTemplate
from src.modules.quality.domain.services.zpl_template import render_zpl
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.modules.quality.ports.outbound.docket_spec_dto import DocketSpec

# Hard ceiling on positions rendered onto one docket.
MAX_TABLE_ROWS = 500


@dataclass(frozen=True)
class RenderedDocument:
    payload: bytes
    content_type: str
    rendered_zpl: str | None
    warnings: list[str] = field(default_factory=list)


async def render_print_document(
    template: PrintTemplate,
    root: BaseModel,
    root_type: str,
    *,
    domain_url: str,
    actor_full_name: str,
    docket_renderer: IDocketRenderer,
    asset_resolver: DocketAssetResolver | None,
    event_quantity: float | None = None,
) -> RenderedDocument:
    """Raises ValueError if a docket's `source` is not a valid block spec,
    should not happen for a saved template (UpdatePrintTemplate validates
    it), but a template resolved by classifier is trusted input, not
    reverified input, so this is not caught here; the caller decides
    whether that becomes a failed print_job or a 400."""
    spec = CLASSIFIERS[PrintClassifier(template.classifier)]

    values = await resolve_field_values(
        template.field_map,
        root,
        domain_url=domain_url,
        actor_full_name=actor_full_name,
        event_quantity=event_quantity,
        asset_resolver=asset_resolver,
    )

    if spec.output_kind == PrintOutputKind.ZPL:
        rendered = render_zpl(template.source or "", values)
        return RenderedDocument(
            payload=rendered.encode("utf-8"),
            content_type="application/x-zpl",
            rendered_zpl=rendered,
        )

    docket_spec = parse_docket_spec(template.source or "{}")
    rows = await build_rows(docket_spec, template.field_map, root, spec, asset_resolver)

    # Re-resolved now that the row count is known: @row_count is a document
    # value ("POSITIONS: 5") that only exists once the rows have been read.
    values = await resolve_field_values(
        template.field_map,
        root,
        domain_url=domain_url,
        actor_full_name=actor_full_name,
        event_quantity=event_quantity,
        asset_resolver=asset_resolver,
        row_count=len(rows) if spec.has_rows else None,
    )
    images = await resolve_image_sources(
        template.field_map,
        root,
        root_type,
        domain_url=domain_url,
        asset_resolver=asset_resolver,
        qr_renderer=docket_renderer,
    )

    pages = paginate(docket_spec, values, images, rows)
    pdf_bytes, warnings = await to_thread.run_sync(
        partial(docket_renderer.render_pdf, pages, paper=template.paper or "a4")
    )
    return RenderedDocument(
        payload=pdf_bytes, content_type="application/pdf", rendered_zpl=None, warnings=warnings
    )


async def build_rows(
    docket_spec: DocketSpec,
    field_map: dict[str, str],
    root: BaseModel,
    spec: ClassifierSpec,
    asset_resolver: DocketAssetResolver | None,
) -> list[DocketRow]:
    """Read the root's row list and resolve each row's cells. Empty for
    every classifier without a positions table, which is all of them bar
    order_docket, and for a table whose rows the root does not carry, so
    a mis-authored spec prints an empty table rather than failing.

    Rows are capped: a docket is a document a human reads, and rendering
    several hundred pages (each with its own storage round trips) on a
    misclick is a denial of service, not a feature. The cap surfaces as a
    warning through the renderer's own page count, not silently."""
    if docket_spec.table is None or not spec.has_rows:
        return []

    rows = getattr(root, spec.row_source or "", None)
    if not isinstance(rows, list):
        return []

    placeholders = row_fields_in_docket_spec(docket_spec)
    return [
        DocketRow(
            values=resolve_row_values(field_map, row, placeholders),
            images=await resolve_row_images(
                field_map, row, placeholders, asset_resolver=asset_resolver
            ),
        )
        for row in rows[:MAX_TABLE_ROWS]
    ]
