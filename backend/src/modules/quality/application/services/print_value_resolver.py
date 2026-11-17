"""
Turns a template's field_map (placeholder -> source name) plus a resolved
root DTO into the flat {placeholder: string} dict render_zpl() substitutes,
and (for dockets) the {placeholder: bytes|None} dict the docket renderer's
image blocks read. Shared by PreviewPrintTemplate, PrintDocument and
DownloadPrintDocument so preview, print and download always compute values
the same way.
"""

from datetime import date
from datetime import datetime
from typing import Any

from anyio import to_thread
from pydantic import BaseModel

from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.print_field_scopes import ROW_IMAGE_SOURCE
from src.modules.quality.application.services.print_field_scopes import is_row_source
from src.modules.quality.application.services.print_field_scopes import row_attribute
from src.modules.quality.ports.outbound.docket_renderer_port import IDocketRenderer
from src.shared_kernel.domain.services.clock import today_utc


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _resolve_url(root: BaseModel, domain_url: str, public_id_field: str = "public_id") -> str:
    public_id = getattr(root, public_id_field, None)
    return f"{domain_url}/resolve/{public_id}" if public_id else ""


async def resolve_field_values(
    field_map: dict[str, str],
    root: BaseModel,
    *,
    domain_url: str,
    actor_full_name: str,
    event_quantity: float | None = None,
    asset_resolver: DocketAssetResolver | None = None,
    row_count: int | None = None,
) -> dict[str, str]:
    """The remaining docket-only computed sources (@part_image,
    @company_logo, @qr_image) are image-valued, not string-valued; see
    resolve_image_sources below. They resolve to an empty string here so a
    ZPL template referencing one (which cannot happen through the field-map
    validator, but costs nothing to guard) prints blank rather than
    failing."""
    values: dict[str, str] = {}

    # Order-dependent: the exact-match "@resolve_url" branch must precede
    # the "@resolve_url:" prefix branch,
    # and both must precede the generic "@" prefix catch-all and the final
    # plain-attribute fallthrough, or a more specific source would never be
    # reached.
    for placeholder, source in field_map.items():
        if source == "@today":
            # The tenant's day; only a preview without an asset resolver,
            # which shows no company data either, falls back to UTC.
            today = await asset_resolver.resolve_today() if asset_resolver else today_utc()
            values[placeholder] = today.isoformat()
        elif source == "@actor_full_name":
            values[placeholder] = actor_full_name
        elif source == "@resolve_url":
            values[placeholder] = _resolve_url(root, domain_url)
        elif source.startswith("@resolve_url:"):
            field = source.removeprefix("@resolve_url:")
            values[placeholder] = _resolve_url(root, domain_url, field)
        elif source == "@event_quantity":
            values[placeholder] = _stringify(event_quantity) if event_quantity is not None else ""
        elif source == "@company_name":
            values[placeholder] = (
                await asset_resolver.resolve_company_name() if asset_resolver else ""
            )
        elif source == "@row_count":
            values[placeholder] = str(row_count) if row_count is not None else ""
        elif is_row_source(source):
            # Row-scoped: meaningless against the root. Resolved per row by
            # resolve_row_values instead, so leave the document-level slot
            # empty rather than reading a nonexistent root attribute.
            values[placeholder] = ""
        elif source.startswith("@"):
            values[placeholder] = ""
        else:
            values[placeholder] = _stringify(getattr(root, source, None))

    return values


def resolve_row_values(
    field_map: dict[str, str], row: BaseModel, row_placeholders: set[str]
) -> dict[str, str]:
    """The per-row counterpart of resolve_field_values: only the
    placeholders a table column references, resolved against ONE row DTO.
    A non-row source among them would be a scope error, which
    validate_docket_spec rejects before a template can be saved; here it
    simply resolves to an empty cell rather than raising mid-print."""
    values: dict[str, str] = {}
    for placeholder in row_placeholders:
        source = field_map.get(placeholder, "")
        if is_row_source(source) and source != ROW_IMAGE_SOURCE:
            values[placeholder] = _stringify(getattr(row, row_attribute(source), None))
        else:
            values[placeholder] = ""
    return values


async def resolve_row_images(
    field_map: dict[str, str],
    row: BaseModel,
    row_placeholders: set[str],
    *,
    asset_resolver: DocketAssetResolver | None,
) -> dict[str, bytes | None]:
    """@item_image for one row. None whenever the line has no catalogue
    item behind it, the item has no photo, or storage is unavailable;
    the row still prints, just without a picture."""
    images: dict[str, bytes | None] = {}
    for placeholder in row_placeholders:
        if field_map.get(placeholder) != ROW_IMAGE_SOURCE:
            continue
        images[placeholder] = (
            await asset_resolver.resolve_row_image(row) if asset_resolver else None
        )
    return images


async def resolve_image_sources(
    field_map: dict[str, str],
    root: BaseModel,
    root_type: str,
    *,
    domain_url: str,
    asset_resolver: DocketAssetResolver | None,
    qr_renderer: IDocketRenderer | None,
) -> dict[str, bytes | None]:
    """The image-valued counterpart of resolve_field_values, for a docket's
    "image" blocks. Every source resolves to None (never raises) when the
    resolver or renderer needed to produce it is unavailable; a docket
    must still print without a part photo, a company logo, or storage
    configured at all."""
    images: dict[str, bytes | None] = {}

    for placeholder, source in field_map.items():
        if source == "@part_image":
            images[placeholder] = (
                await asset_resolver.resolve_part_image(root_type, root) if asset_resolver else None
            )
        elif source == "@company_logo":
            images[placeholder] = (
                await asset_resolver.resolve_company_logo() if asset_resolver else None
            )
        elif source == "@qr_image":
            payload = _resolve_url(root, domain_url)
            images[placeholder] = (
                await to_thread.run_sync(qr_renderer.render_qr_png, payload)
                if payload and qr_renderer
                else None
            )
        elif source.startswith("@qr_image:"):
            field = source.removeprefix("@qr_image:")
            payload = _resolve_url(root, domain_url, field)
            images[placeholder] = (
                await to_thread.run_sync(qr_renderer.render_qr_png, payload)
                if payload and qr_renderer
                else None
            )

    return images
