"""
Turns one docket spec plus N resolved rows into the list of pages the
renderer draws. Pure geometry and block generation, no Pillow, no I/O,
no DB, which is exactly why it lives here and not in the renderer: how
many rows fit on a page, which blocks belong on which page, and where a
cell's second line sits are layout decisions, while rasterising is the
adapter's job (docket_renderer.py).

Two things it owns that the stored template deliberately does NOT:

- Cell layout. A DocketColumn declares a header, a width and a stack of
  fields; the pixel-level arrangement of that stack (primary line bold,
  secondaries smaller beneath, image inset) is decided here so an admin
  editing columns in the docket editor cannot misalign anything.
- Page numbering. @page_number / @page_count / @page_label are supplied
  per page here, not by the field-map resolver, which has no idea how many
  pages there will be.

A spec with no `table` produces exactly one page whose blocks are the
spec's own, the pre-order behaviour, unchanged.
"""

from dataclasses import dataclass

from src.modules.quality.ports.outbound.docket_spec_dto import DocketBlock
from src.modules.quality.ports.outbound.docket_spec_dto import DocketColumn
from src.modules.quality.ports.outbound.docket_spec_dto import DocketSpec
from src.modules.quality.ports.outbound.docket_spec_dto import DocketTable
from src.modules.quality.ports.outbound.docket_spec_dto import ImageBlock
from src.modules.quality.ports.outbound.docket_spec_dto import LineBlock
from src.modules.quality.ports.outbound.docket_spec_dto import RenderPage
from src.modules.quality.ports.outbound.docket_spec_dto import TextBlock

# Renderer-provided pseudo-fields; see docket_spec._is_renderer_provided.
PAGE_NUMBER_FIELD = "@page_number"
PAGE_COUNT_FIELD = "@page_count"
PAGE_LABEL_FIELD = "@page_label"
PAGE_FIELDS = frozenset({PAGE_NUMBER_FIELD, PAGE_COUNT_FIELD, PAGE_LABEL_FIELD})

# Cell metrics, in millimetres relative to the top of a row band.
_PRIMARY_SIZE_MM = 3.5
_SECONDARY_SIZE_MM = 3.0
_PRIMARY_TOP_MM = 4.0
_SECONDARY_TOP_MM = 9.0
_SECONDARY_STEP_MM = 4.5
_CELL_PAD_MM = 2.0  # gutter between a cell's text and the next column

# An image cell keeps clear air on both sides so thumbnails never touch the
# columns beside them, and 1 mm top/bottom inside the row.
_IMAGE_PAD_X_MM = 3.0
_IMAGE_PAD_Y_MM = 1.0

# Column headers are centred in the header band, with the band's underline
# just above its bottom edge.
_HEADER_LABEL_SIZE_MM = 2.6
_HEADER_UNDERLINE_INSET_MM = 0.5


@dataclass(frozen=True)
class DocketRow:
    """One resolved table row: the values and images its cells draw from,
    keyed by the same placeholders the columns reference."""

    values: dict[str, str]
    images: dict[str, bytes | None]


def rows_per_page(table: DocketTable, *, first_page: bool) -> int:
    """How many rows fit below the header band. At least 1, since the spec
    validator rejects a table whose band cannot hold a single row."""
    top = table.first_page_top_mm if first_page else table.next_page_top_mm
    usable = table.bottom_mm - top - table.header_height_mm
    return max(int(usable // table.row_height_mm), 1)


def chunk_rows(table: DocketTable, row_count: int) -> list[tuple[int, int]]:
    """(start, end) slice bounds per page. Always at least one page, so a
    table with no rows still prints its header band and the document
    header rather than nothing."""
    if row_count == 0:
        return [(0, 0)]

    bounds: list[tuple[int, int]] = []
    start = 0
    while start < row_count:
        size = rows_per_page(table, first_page=not bounds)
        bounds.append((start, min(start + size, row_count)))
        start += size
    return bounds


def paginate(
    spec: DocketSpec,
    values: dict[str, str],
    images: dict[str, bytes | None],
    rows: list[DocketRow] | None = None,
) -> list[RenderPage]:
    """The whole job: spec + rows -> pages ready to draw."""
    if spec.table is None:
        return [
            RenderPage(
                page=spec.page, blocks=list(spec.blocks), values=dict(values), images=dict(images)
            )
        ]

    rows = rows or []
    bounds = chunk_rows(spec.table, len(rows))
    page_count = len(bounds)

    pages: list[RenderPage] = []
    for index, (start, end) in enumerate(bounds):
        page_number = index + 1
        band_top = spec.table.first_page_top_mm if page_number == 1 else spec.table.next_page_top_mm

        blocks: list[DocketBlock] = [
            block for block in spec.blocks if _on_page(block.pages, page_number)
        ]
        blocks.extend(_header_band_blocks(spec.table, band_top))

        page_values = dict(values)
        page_images = dict(images)
        for offset, row in enumerate(rows[start:end]):
            row_top = band_top + spec.table.header_height_mm + offset * spec.table.row_height_mm
            row_key = f"__row{start + offset}"
            blocks.extend(_row_blocks(spec.table, row_top, row, row_key))
            page_values.update({f"{row_key}.{k}": v for k, v in row.values.items()})
            page_images.update({f"{row_key}.{k}": v for k, v in row.images.items()})

        page_values.update(_page_values(page_number, page_count))
        pages.append(
            RenderPage(page=spec.page, blocks=blocks, values=page_values, images=page_images)
        )

    return pages


# ── Block generation ──────────────────────────────────────────────────


def _on_page(scope: str, page_number: int) -> bool:
    if scope == "first":
        return page_number == 1
    if scope == "continuation":
        return page_number > 1
    return True


def _page_values(page_number: int, page_count: int) -> dict[str, str]:
    return {
        PAGE_NUMBER_FIELD: str(page_number),
        PAGE_COUNT_FIELD: str(page_count),
        PAGE_LABEL_FIELD: f"{page_number} / {page_count}",
    }


def _column_x(table: DocketTable) -> list[float]:
    """Left edge of each column, accumulated from the table's own origin."""
    edges, x = [], table.x_mm
    for column in table.columns:
        edges.append(x)
        x += column.width_mm
    return edges


def _header_band_blocks(table: DocketTable, band_top: float) -> list[DocketBlock]:
    """Column labels, vertically centred in the band, over an underline."""
    label_top = band_top + (table.header_height_mm - _HEADER_LABEL_SIZE_MM * 1.2) / 2
    blocks: list[DocketBlock] = [
        TextBlock(
            x=x,
            y=label_top,
            size_mm=_HEADER_LABEL_SIZE_MM,
            bold=True,
            text=column.header,
            max_width_mm=max(column.width_mm - _CELL_PAD_MM, 1.0),
            max_lines=1,
            align=column.align,
        )
        for column, x in zip(table.columns, _column_x(table), strict=True)
    ]

    underline_y = band_top + table.header_height_mm - _HEADER_UNDERLINE_INSET_MM
    right = table.x_mm + sum(column.width_mm for column in table.columns)
    blocks.append(LineBlock(x=table.x_mm, y=underline_y, x2=right, y2=underline_y, stroke_mm=0.3))
    return blocks


def _row_blocks(
    table: DocketTable, row_top: float, row: DocketRow, row_key: str
) -> list[DocketBlock]:
    blocks: list[DocketBlock] = []
    for column, x in zip(table.columns, _column_x(table), strict=True):
        blocks.extend(_cell_blocks(column, x, row_top, table.row_height_mm, row_key))

    if table.separator_stroke_mm:
        separator_y = row_top + table.row_height_mm
        right = table.x_mm + sum(column.width_mm for column in table.columns)
        blocks.append(
            LineBlock(
                x=table.x_mm,
                y=separator_y,
                x2=right,
                y2=separator_y,
                stroke_mm=table.separator_stroke_mm,
            )
        )
    return blocks


def _cell_blocks(
    column: DocketColumn, x: float, row_top: float, row_height: float, row_key: str
) -> list[DocketBlock]:
    """A cell is either one image, letterboxed with clear air either side,
    or a stack of text lines: the first bold and full size, the rest
    smaller beneath it."""
    if column.kind == "image":
        return [
            ImageBlock(
                x=x + _IMAGE_PAD_X_MM,
                y=row_top + _IMAGE_PAD_Y_MM,
                w=max(column.width_mm - 2 * _IMAGE_PAD_X_MM, 1.0),
                h=max(row_height - 2 * _IMAGE_PAD_Y_MM, 1.0),
                field=f"{row_key}.{column.fields[0]}",
                fallback_text=None,
            )
        ]

    width = max(column.width_mm - _CELL_PAD_MM, 1.0)
    blocks: list[DocketBlock] = []
    for index, field in enumerate(column.fields):
        if index == 0:
            y, size, bold = row_top + _PRIMARY_TOP_MM, _PRIMARY_SIZE_MM, True
        else:
            y = row_top + _SECONDARY_TOP_MM + (index - 1) * _SECONDARY_STEP_MM
            size, bold = _SECONDARY_SIZE_MM, False
        blocks.append(
            TextBlock(
                x=x,
                y=y,
                size_mm=size,
                bold=bold,
                field=f"{row_key}.{field}",
                max_width_mm=width,
                max_lines=1,
                align=column.align,
            )
        )
    return blocks
