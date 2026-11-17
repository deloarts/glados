"""
Unit tests for the ZPL template engine, with emphasis on the injection
boundary: zpl_escape must neutralise ^ ~ , _ in substituted values, and
render_zpl must mark the receiving field ^FH so those escapes are actually
interpreted rather than printed literally.
"""

import pytest

from src.modules.quality.domain.services.zpl_template import placeholders_in
from src.modules.quality.domain.services.zpl_template import render_zpl
from src.modules.quality.domain.services.zpl_template import validate_zpl_template
from src.modules.quality.domain.services.zpl_template import zpl_escape

_TEMPLATE = "^XA^CI28^FO10,10^A0N,20,20^FD{part_number}^FS^FO10,40^A0N,20,20^FD{article_name}^FS^XZ"


class TestZplEscape:
    def test_escapes_caret(self):
        assert zpl_escape("^XA") == "_5EXA"

    def test_escapes_tilde(self):
        assert zpl_escape("~JA") == "_7EJA"

    def test_escapes_comma(self):
        assert zpl_escape("a,b") == "a_2Cb"

    def test_escapes_underscore(self):
        assert zpl_escape("Motor_Housing") == "Motor_5FHousing"

    def test_strips_control_characters(self):
        assert zpl_escape("abc\x00\x1fdef") == "abcdef"

    def test_plain_text_is_unchanged(self):
        assert zpl_escape("MI-004871") == "MI-004871"


class TestValidateZplTemplate:
    def test_valid_template_passes(self):
        validate_zpl_template(_TEMPLATE, {"part_number": "x", "article_name": "y"})

    def test_empty_template_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            validate_zpl_template("", {})

    def test_missing_xa_xz_raises(self):
        with pytest.raises(ValueError, match=r"\^XA"):
            validate_zpl_template("^FD{x}^FS", {"x": "field"})

    def test_unmapped_placeholder_raises(self):
        with pytest.raises(ValueError, match="unmapped placeholder"):
            validate_zpl_template(_TEMPLATE, {"part_number": "field"})

    def test_unmapped_error_lists_the_missing_name(self):
        with pytest.raises(ValueError, match="article_name"):
            validate_zpl_template(_TEMPLATE, {"part_number": "field"})


class TestPlaceholdersIn:
    def test_finds_every_distinct_placeholder(self):
        assert placeholders_in(_TEMPLATE) == {"part_number", "article_name"}

    def test_no_placeholders_returns_empty_set(self):
        assert placeholders_in("^XA^FD static ^FS^XZ") == set()


class TestRenderZpl:
    def test_substitutes_plain_values(self):
        result = render_zpl(_TEMPLATE, {"part_number": "MI-004871", "article_name": "Housing"})
        assert "MI-004871" in result
        assert "Housing" in result

    def test_marks_field_with_placeholder_as_hex(self):
        result = render_zpl(_TEMPLATE, {"part_number": "x", "article_name": "y"})
        # Bare ^FH, no explicit indicator argument: it must default to
        # `_` to match zpl_escape's _XX codes. ^FH\ or ^FH_ would also be
        # syntactically "marked" but wrongly, so assert the exact bare form.
        assert "^FH^FD" in result

    def test_does_not_pass_an_explicit_indicator_argument(self):
        # An explicit argument character right after ^FH (such as ^FH\)
        # overrides the indicator, which would silently
        # break every _XX escape zpl_escape produces.
        result = render_zpl(_TEMPLATE, {"part_number": "x", "article_name": "y"})
        assert "^FH\\" not in result

    def test_field_without_placeholder_is_not_marked(self):
        template = "^XA^FD static text ^FS^FD{value}^FS^XZ"
        result = render_zpl(template, {"value": "x"})
        assert "^FD static text ^FS" in result  # untouched, no ^FH prefix

    def test_caret_in_value_is_escaped_not_literal(self):
        result = render_zpl(_TEMPLATE, {"part_number": "A^XA", "article_name": "y"})
        # the literal ^XA must not appear mid-field, only as hex-escaped text
        assert "^FDA^XA" not in result
        assert "A_5EXA" in result

    def test_comma_in_value_is_escaped(self):
        result = render_zpl(_TEMPLATE, {"part_number": "a,b", "article_name": "y"})
        assert "a_2Cb" in result

    def test_tilde_in_value_is_escaped(self):
        result = render_zpl(_TEMPLATE, {"part_number": "~JA", "article_name": "y"})
        assert "_7EJA" in result

    def test_literal_template_text_outside_placeholders_is_untouched(self):
        # The QR field's "QA," prefix is literal template syntax, not a
        # substituted value: it must never be escaped.
        template = "^XA^BQN,2,3^FDQA,{qr_data}^FS^XZ"
        result = render_zpl(template, {"qr_data": "https://example.test/1"})
        assert "^FDQA," in result
        assert "_2C" not in result.split("^FD")[1]  # no escaping inside this field's literal part

    def test_attribute_traversal_payload_is_inert(self):
        # The whole point of regex substitution over str.format(): a value
        # that LOOKS like a format spec is just a string, never traversed;
        # it comes out escaped like any other value, never resolved to
        # "<class 'str'>" or similar.
        result = render_zpl(_TEMPLATE, {"part_number": "{0.__class__}", "article_name": "y"})
        assert "class 'str'" not in result
        assert "{0." in result

    def test_missing_value_substitutes_empty_string(self):
        result = render_zpl(_TEMPLATE, {"part_number": "x"})
        assert "^FD^FS" in result  # article_name had no value
