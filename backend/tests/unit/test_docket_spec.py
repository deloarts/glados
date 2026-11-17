"""
Docket spec parsing/validation: the docket counterpart of
test_zpl_template.py. No str.format()/eval() is involved anywhere in this
format: pydantic validates structure, and the renderer only ever reads
block fields.
"""

import pytest

from src.modules.quality.application.services.docket_spec import fields_in_docket_spec
from src.modules.quality.application.services.docket_spec import parse_docket_spec
from src.modules.quality.application.services.docket_spec import row_fields_in_docket_spec
from src.modules.quality.application.services.docket_spec import validate_docket_spec

_VALID_SPEC = """
{
  "page": {"width_mm": 100, "height_mm": 100},
  "blocks": [
    {"type": "rect", "x": 1, "y": 1, "w": 98, "h": 98},
    {"type": "text", "x": 5, "y": 5, "size_mm": 5, "text": "STATIC"},
    {"type": "text", "x": 5, "y": 15, "size_mm": 5, "field": "part_number"},
    {"type": "qr", "x": 5, "y": 30, "size_mm": 20, "field": "qr_payload"},
    {"type": "image", "x": 5, "y": 60, "w": 20, "h": 20, "field": "part_image"}
  ]
}
"""


class TestParseDocketSpec:
    def test_parses_a_valid_spec(self):
        spec = parse_docket_spec(_VALID_SPEC)
        assert spec.page.width_mm == 100
        assert len(spec.blocks) == 5

    def test_malformed_json_raises_value_error(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_docket_spec("{not json")

    def test_unknown_block_type_is_rejected_by_the_discriminated_union(self):
        source = '{"page": {"width_mm": 10, "height_mm": 10}, "blocks": [{"type": "circle"}]}'
        with pytest.raises(ValueError, match="failed validation"):
            parse_docket_spec(source)

    def test_text_block_requires_exactly_one_of_text_or_field(self):
        both = (
            '{"page": {"width_mm": 10, "height_mm": 10}, "blocks": '
            '[{"type": "text", "x": 0, "y": 0, "size_mm": 1, "text": "a", "field": "b"}]}'
        )
        with pytest.raises(ValueError):
            parse_docket_spec(both)

        neither = (
            '{"page": {"width_mm": 10, "height_mm": 10}, "blocks": '
            '[{"type": "text", "x": 0, "y": 0, "size_mm": 1}]}'
        )
        with pytest.raises(ValueError):
            parse_docket_spec(neither)

    def test_missing_page_is_rejected(self):
        with pytest.raises(ValueError):
            parse_docket_spec('{"blocks": []}')

    def test_empty_blocks_list_is_valid(self):
        spec = parse_docket_spec('{"page": {"width_mm": 10, "height_mm": 10}, "blocks": []}')
        assert spec.blocks == []


class TestFieldsInDocketSpec:
    def test_collects_text_image_and_qr_fields_but_not_literal_text(self):
        spec = parse_docket_spec(_VALID_SPEC)
        assert fields_in_docket_spec(spec) == {"part_number", "qr_payload", "part_image"}

    def test_rect_and_line_blocks_contribute_no_fields(self):
        source = (
            '{"page": {"width_mm": 10, "height_mm": 10}, "blocks": '
            '[{"type": "rect", "x": 0, "y": 0, "w": 1, "h": 1}, '
            '{"type": "line", "x": 0, "y": 0, "x2": 1, "y2": 1}]}'
        )
        spec = parse_docket_spec(source)
        assert fields_in_docket_spec(spec) == set()


class TestValidateDocketSpec:
    def test_passes_when_every_field_is_mapped(self):
        field_map = {
            "part_number": "made_item_part_number",
            "qr_payload": "@resolve_url",
            "part_image": "@part_image",
        }
        validate_docket_spec(_VALID_SPEC, field_map)  # must not raise

    def test_raises_when_a_block_field_is_unmapped(self):
        with pytest.raises(ValueError, match="unmapped field"):
            validate_docket_spec(_VALID_SPEC, {"part_number": "made_item_part_number"})

    def test_raises_on_malformed_json_too(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            validate_docket_spec("{broken", {})


_TABLE_SPEC = """
{
  "page": {"width_mm": 210, "height_mm": 297},
  "blocks": [
    {"type": "text", "x": 14, "y": 30, "size_mm": 5, "field": "order_number"},
    {"type": "text", "x": 14, "y": 285, "size_mm": 3, "field": "@page_label"}
  ],
  "table": {
    "row_height_mm": 22, "first_page_top_mm": 66,
    "next_page_top_mm": 30, "bottom_mm": 280,
    "columns": [
      {"header": "POS", "fields": ["position"], "width_mm": 8},
      {"header": "IMG", "fields": ["row_image"], "width_mm": 26, "kind": "image"}
    ]
  }
}
"""

_TABLE_FIELD_MAP = {
    "order_number": "order_number",
    "position": "item.position",
    "row_image": "@item_image",
}


class TestTableFieldCollection:
    def test_column_fields_are_collected_alongside_block_fields(self):
        fields = fields_in_docket_spec(parse_docket_spec(_TABLE_SPEC))
        assert {"order_number", "position", "row_image"} <= fields

    def test_renderer_provided_page_fields_need_no_mapping(self):
        assert "@page_label" not in fields_in_docket_spec(parse_docket_spec(_TABLE_SPEC))

    def test_row_fields_are_reported_separately(self):
        assert row_fields_in_docket_spec(parse_docket_spec(_TABLE_SPEC)) == {
            "position",
            "row_image",
        }

    def test_a_spec_without_a_table_has_no_row_fields(self):
        assert row_fields_in_docket_spec(parse_docket_spec(_VALID_SPEC)) == set()


class TestScopeValidation:
    def test_a_correctly_scoped_table_spec_passes(self):
        validate_docket_spec(_TABLE_SPEC, _TABLE_FIELD_MAP)  # must not raise

    def test_a_column_mapped_to_a_document_source_is_rejected(self):
        # Would silently print the order's status down every row.
        field_map = {**_TABLE_FIELD_MAP, "position": "status"}
        with pytest.raises(ValueError, match="wrong value scope"):
            validate_docket_spec(_TABLE_SPEC, field_map)

    def test_a_header_block_mapped_to_a_row_source_is_rejected(self):
        # Would print nothing at all: there is no row in document scope.
        field_map = {**_TABLE_FIELD_MAP, "order_number": "item.position"}
        with pytest.raises(ValueError, match="wrong value scope"):
            validate_docket_spec(_TABLE_SPEC, field_map)

    def test_an_image_column_takes_exactly_one_field(self):
        with pytest.raises(ValueError, match="image column takes exactly one field"):
            parse_docket_spec(
                """
                {"page": {"width_mm": 210, "height_mm": 297},
                 "table": {"row_height_mm": 22,
                           "first_page_top_mm": 66, "next_page_top_mm": 30, "bottom_mm": 280,
                           "columns": [{"header": "I", "fields": ["a", "b"],
                                        "width_mm": 26, "kind": "image"}]}}
                """
            )
