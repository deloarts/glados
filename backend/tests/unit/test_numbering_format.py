from datetime import date

import pytest

from src.modules.platform.domain.services.numbering_format import (
    assert_pattern_does_not_shadow_internal_formats,
)
from src.modules.platform.domain.services.numbering_format import render_example
from src.modules.platform.domain.services.numbering_format import render_prefix
from src.modules.platform.domain.services.numbering_format import validate_external_pattern
from src.modules.platform.domain.services.numbering_format import validate_numbering_format


class TestValidateNumberingFormat:
    def test_accepts_default_template(self):
        validate_numbering_format("ORD-{year}-{seq:04d}")

    def test_accepts_all_placeholders(self):
        validate_numbering_format("PO-{yy}{month}-{seq:03d}")

    def test_accepts_bare_seq(self):
        validate_numbering_format("ORD-{seq}")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_numbering_format("")

    def test_rejects_missing_seq(self):
        with pytest.raises(ValueError):
            validate_numbering_format("ORD-{year}")

    def test_rejects_seq_not_last(self):
        with pytest.raises(ValueError):
            validate_numbering_format("ORD-{seq:04d}-{year}")

    def test_rejects_unknown_placeholder(self):
        with pytest.raises(ValueError):
            validate_numbering_format("ORD-{day}-{seq:04d}")

    def test_rejects_format_injection_attempt(self):
        with pytest.raises(ValueError):
            validate_numbering_format("{0.__class__}-{seq:04d}")


class TestRenderPrefix:
    def test_default_template(self):
        prefix, width = render_prefix("ORD-{year}-{seq:04d}", today=date(2026, 7, 8))
        assert prefix == "ORD-2026-"
        assert width == 4

    def test_yy_and_month(self):
        prefix, width = render_prefix("PO-{yy}{month}-{seq:03d}", today=date(2026, 7, 8))
        assert prefix == "PO-2607-"
        assert width == 3

    def test_bare_seq_defaults_to_width_one(self):
        prefix, width = render_prefix("ORD-{seq}", today=date(2026, 7, 8))
        assert prefix == "ORD-"
        assert width == 1


class TestRenderExample:
    def test_renders_seq_one_by_default(self):
        assert render_example("ORD-{year}-{seq:04d}", today=date(2026, 7, 8)) == "ORD-2026-0001"

    def test_renders_given_seq(self):
        assert (
            render_example("ORD-{year}-{seq:04d}", today=date(2026, 7, 8), seq=42)
            == "ORD-2026-0042"
        )


class TestValidateExternalPattern:
    def test_empty_is_valid(self):
        validate_external_pattern("")

    def test_valid_regex_is_accepted(self):
        validate_external_pattern(r"^EXT-\d+$")

    def test_invalid_regex_raises(self):
        with pytest.raises(ValueError):
            validate_external_pattern("[")


class TestAssertPatternDoesNotShadowInternalFormats:
    def test_empty_pattern_is_a_noop(self):
        assert_pattern_does_not_shadow_internal_formats(
            "", ["ORD-{year}-{seq:04d}"], today=date(2026, 7, 8)
        )

    def test_non_overlapping_pattern_is_accepted(self):
        assert_pattern_does_not_shadow_internal_formats(
            r"^EXT-\d+$", ["ORD-{year}-{seq:04d}"], today=date(2026, 7, 8)
        )

    def test_overlapping_pattern_is_rejected(self):
        with pytest.raises(ValueError):
            assert_pattern_does_not_shadow_internal_formats(
                r"^ORD-\d{4}-\d{4}$", ["ORD-{year}-{seq:04d}"], today=date(2026, 7, 8)
            )

    def test_checks_every_format_in_the_list(self):
        with pytest.raises(ValueError):
            assert_pattern_does_not_shadow_internal_formats(
                r"^PUR-\d{4}-\d{4}$",
                ["ORD-{year}-{seq:04d}", "PUR-{year}-{seq:04d}"],
                today=date(2026, 7, 8),
            )

    def test_partial_match_is_not_enough(self):
        """fullmatch semantics: a pattern that matches only a substring of
        the rendered example does not count as an overlap."""
        assert_pattern_does_not_shadow_internal_formats(
            r"^ORD$", ["ORD-{year}-{seq:04d}"], today=date(2026, 7, 8)
        )
