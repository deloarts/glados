"""
Mirrors the case matrix in the frontend's dimensionSpec.spec.ts: the two
implementations must agree, since one gates the create-dialog's warning and
the other gates the 409.
"""

from src.modules.catalogue.domain.services.dimension_spec import canonicalize_dimension


class TestCanonicalizeDimension:
    def test_permutes_any_ordering_of_a_box_dimension(self):
        assert canonicalize_dimension("100 × 200 × 20") == canonicalize_dimension("200 × 100 × 20")
        assert canonicalize_dimension("100 × 200 × 20") == canonicalize_dimension("20 × 200 × 100")
        assert canonicalize_dimension("100 × 200 × 20") == "200 × 100 × 20"

    def test_normalizes_trailing_zero_decimal_formatting(self):
        assert canonicalize_dimension("100.0 × 200 × 20") == canonicalize_dimension(
            "100 × 200 × 20"
        )
        assert canonicalize_dimension("12.50 × 1 × 1") == canonicalize_dimension("12.5 × 1 × 1")
        assert canonicalize_dimension("100.00 × 1 × 1") == "100 × 1 × 1"

    def test_normalizes_ascii_x_separator_the_same_as_multiplication_sign(self):
        assert canonicalize_dimension("100 x 200 x 20") == canonicalize_dimension("100 × 200 × 20")
        assert canonicalize_dimension("100X200X20") == canonicalize_dimension("200 × 100 × 20")

    def test_does_not_permute_a_rods_diameter_and_length(self):
        assert canonicalize_dimension("Ø20 × 100") != canonicalize_dimension("Ø100 × 20")
        assert canonicalize_dimension("Ø20 × 100") == canonicalize_dimension("Ø20 × 100")

    def test_does_not_permute_a_hollow_rods_numbers(self):
        assert canonicalize_dimension("Ø100 × 20 × 5") != canonicalize_dimension("Ø5 × 20 × 100")

    def test_does_not_permute_a_hollow_boxs_numbers(self):
        assert canonicalize_dimension("100 × 200 × 20 × 5") != canonicalize_dimension(
            "5 × 20 × 200 × 100"
        )
        assert canonicalize_dimension("100 × 200 × 20 × 5") == canonicalize_dimension(
            "100 × 200 × 20 × 5"
        )

    def test_collapses_whitespace_on_custom_unmatched_text_without_altering_content(self):
        assert canonicalize_dimension("  custom   shape  ") == "custom shape"
        assert canonicalize_dimension("custom shape") == canonicalize_dimension("custom  shape")
        assert canonicalize_dimension("custom shape A") != canonicalize_dimension("custom shape B")

    def test_none_and_empty_are_equal_only_to_each_other(self):
        assert canonicalize_dimension(None) is None
        assert canonicalize_dimension("") is None
        assert canonicalize_dimension("   ") is None
        assert canonicalize_dimension(None) == canonicalize_dimension("")
        assert canonicalize_dimension(None) != canonicalize_dimension("100 × 200 × 20")
