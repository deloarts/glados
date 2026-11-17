"""
Unit tests for the docket paginator: capacity arithmetic, page scoping,
cell-block generation and page numbering. Pure functions over a parsed
spec: nothing here rasterises anything, which is the whole point of
pagination living in the application layer rather than in the renderer.
"""

import pytest

from src.modules.quality.application.services.docket_pagination import DocketRow
from src.modules.quality.application.services.docket_pagination import chunk_rows
from src.modules.quality.application.services.docket_pagination import paginate
from src.modules.quality.application.services.docket_pagination import rows_per_page
from src.modules.quality.application.services.docket_spec import parse_docket_spec
from src.modules.quality.ports.outbound.docket_spec_dto import ImageBlock
from src.modules.quality.ports.outbound.docket_spec_dto import TextBlock

# The order docket's real geometry: (280 - 66 - 8) / 22 = 9 rows on page 1,
# (280 - 30 - 8) / 22 = 11 on every continuation page.
_ORDER_SPEC = """
{
  "page": {"width_mm": 210, "height_mm": 297},
  "blocks": [
    {"type": "rect", "x": 8, "y": 8, "w": 194, "h": 281, "pages": "all"},
    {"type": "text", "x": 14, "y": 12, "size_mm": 6, "text": "ORDER", "pages": "first"},
    {"type": "text", "x": 14, "y": 12, "size_mm": 5, "text": "cont.", "pages": "continuation"},
    {"type": "text", "x": 14, "y": 285, "size_mm": 3, "field": "@page_label", "pages": "all"}
  ],
  "table": {
    "x_mm": 14,
    "row_height_mm": 22,
    "first_page_top_mm": 66,
    "next_page_top_mm": 30,
    "bottom_mm": 280,
    "header_height_mm": 8,
    "columns": [
      {"header": "POS", "fields": ["position"], "width_mm": 8},
      {"header": "IMAGE", "fields": ["row_image"], "width_mm": 26, "kind": "image"},
      {"header": "ARTICLE", "fields": ["article", "part_no", "dim"], "width_mm": 102}
    ]
  }
}
"""


def _rows(count: int) -> list[DocketRow]:
    return [
        DocketRow(
            values={"position": str(n + 1), "article": f"A{n}", "part_no": "", "dim": ""},
            images={"row_image": None},
        )
        for n in range(count)
    ]


def _texts(page) -> list[str]:
    return [b.text for b in page.blocks if isinstance(b, TextBlock) and b.text]


class TestCapacity:
    def test_first_page_holds_nine_rows(self):
        table = parse_docket_spec(_ORDER_SPEC).table
        assert rows_per_page(table, first_page=True) == 9

    def test_continuation_pages_hold_eleven(self):
        table = parse_docket_spec(_ORDER_SPEC).table
        assert rows_per_page(table, first_page=False) == 11

    def test_chunking_fills_the_first_page_before_spilling(self):
        table = parse_docket_spec(_ORDER_SPEC).table
        assert chunk_rows(table, 20) == [(0, 9), (9, 20)]

    def test_a_row_count_landing_exactly_on_a_boundary_adds_no_empty_page(self):
        table = parse_docket_spec(_ORDER_SPEC).table
        assert chunk_rows(table, 9) == [(0, 9)]

    def test_no_rows_still_yields_one_page(self):
        table = parse_docket_spec(_ORDER_SPEC).table
        assert chunk_rows(table, 0) == [(0, 0)]

    def test_a_band_too_short_for_one_row_is_rejected_at_parse_time(self):
        with pytest.raises(ValueError, match="No room for a single row"):
            parse_docket_spec(
                """
                {"page": {"width_mm": 210, "height_mm": 297},
                 "table": {"row_height_mm": 22,
                           "first_page_top_mm": 260, "next_page_top_mm": 30,
                           "bottom_mm": 280, "header_height_mm": 8,
                           "columns": [{"header": "P", "fields": ["p"], "width_mm": 8}]}}
                """
            )


class TestPageScoping:
    def test_first_page_blocks_appear_only_on_page_one(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        assert "ORDER" in _texts(pages[0])
        assert "ORDER" not in _texts(pages[1])

    def test_continuation_blocks_appear_only_after_page_one(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        assert "cont." not in _texts(pages[0])
        assert "cont." in _texts(pages[1])

    def test_all_scoped_blocks_appear_on_every_page(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        assert all(any(b.type == "rect" for b in page.blocks) for page in pages)


class TestPageNumbering:
    def test_page_label_counts_up_across_pages(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        assert [p.values["@page_label"] for p in pages] == ["1 / 2", "2 / 2"]

    def test_page_number_and_count_are_supplied_separately(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        assert pages[1].values["@page_number"] == "2"
        assert pages[1].values["@page_count"] == "2"


class TestRowBlocks:
    def test_rows_are_offset_by_the_row_height(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(2))
        images = [b for b in pages[0].blocks if isinstance(b, ImageBlock)]
        assert images[1].y - images[0].y == 22

    def test_row_values_are_namespaced_so_rows_cannot_collide(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(2))
        assert pages[0].values["__row0.position"] == "1"
        assert pages[0].values["__row1.position"] == "2"

    def test_row_indices_continue_across_a_page_break(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        assert "__row9.position" in pages[1].values
        assert "__row9.position" not in pages[0].values

    def test_a_stacked_cell_becomes_one_block_per_field(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(1))
        stacked = [
            b
            for b in pages[0].blocks
            if isinstance(b, TextBlock) and (b.field or "").startswith("__row0.")
        ]
        # POS (1) + the three-field ARTICLE stack.
        assert len(stacked) == 4

    def test_image_cell_keeps_clear_air_inside_its_column(self):
        spec = parse_docket_spec(_ORDER_SPEC)
        pages = paginate(spec, {}, {}, _rows(1))
        image = next(b for b in pages[0].blocks if isinstance(b, ImageBlock))
        column = spec.table.columns[1]
        assert image.w < column.width_mm
        assert image.x > spec.table.x_mm + spec.table.columns[0].width_mm

    def test_column_headers_repeat_on_every_page(self):
        pages = paginate(parse_docket_spec(_ORDER_SPEC), {}, {}, _rows(20))
        for page in pages:
            assert "ARTICLE" in _texts(page)


class TestNoTable:
    def test_a_spec_without_a_table_renders_exactly_one_page(self):
        spec = parse_docket_spec('{"page": {"width_mm": 148, "height_mm": 210}, "blocks": []}')
        pages = paginate(spec, {"a": "b"}, {"i": None})
        assert len(pages) == 1
        assert pages[0].values == {"a": "b"}
