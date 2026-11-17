"""Tests for revision scheme detection and incrementing: numeric and alpha
schemes, ambiguous-character skipping, and sort ordering."""

import pytest

from src.modules.catalogue.domain.errors import RevisionNotIncrementableError
from src.modules.catalogue.domain.policies.revision_scheme import START_REVISIONS
from src.modules.catalogue.domain.policies.revision_scheme import RevisionScheme
from src.modules.catalogue.domain.policies.revision_scheme import detect
from src.modules.catalogue.domain.policies.revision_scheme import next_revision
from src.modules.catalogue.domain.policies.revision_scheme import sort_key


class TestDetect:
    def test_numeric(self):
        assert detect("0") is RevisionScheme.NUMERIC
        assert detect("42") is RevisionScheme.NUMERIC

    def test_alpha(self):
        assert detect("A") is RevisionScheme.ALPHA
        assert detect("AZ") is RevisionScheme.ALPHA

    def test_unparseable_is_none(self):
        assert detect("A.1") is None
        assert detect("a") is None
        assert detect("-") is None
        assert detect("") is None
        assert detect("A1") is None


class TestNextRevisionNumeric:
    def test_zero_to_one(self):
        assert next_revision("0") == "1"

    def test_one_to_two(self):
        assert next_revision("1") == "2"

    def test_nine_to_ten(self):
        assert next_revision("9") == "10"


class TestNextRevisionAlpha:
    def test_a_to_b(self):
        assert next_revision("A") == "B"

    def test_z_to_aa(self):
        assert next_revision("Z") == "AA"

    def test_aa_to_ab(self):
        assert next_revision("AA") == "AB"

    def test_az_to_ba(self):
        assert next_revision("AZ") == "BA"

    def test_zz_to_aaa(self):
        assert next_revision("ZZ") == "AAA"


class TestNextRevisionSkipAmbiguous:
    def test_h_to_j(self):
        assert next_revision("H", skip_ambiguous=True) == "J"

    def test_n_to_p(self):
        assert next_revision("N", skip_ambiguous=True) == "P"

    def test_y_to_aa(self):
        assert next_revision("Y", skip_ambiguous=True) == "AA"

    def test_rejects_skipped_letter_in_current_revision(self):
        with pytest.raises(RevisionNotIncrementableError):
            next_revision("Z", skip_ambiguous=True)

    def test_non_skip_mode_still_accepts_z(self):
        assert next_revision("Z", skip_ambiguous=False) == "AA"


class TestNextRevisionInvalid:
    @pytest.mark.parametrize("value", ["A.1", "a", "-", "", "A1"])
    def test_raises_for_unparseable(self, value):
        with pytest.raises(RevisionNotIncrementableError) as exc_info:
            next_revision(value)
        assert value in str(exc_info.value)


class TestSortKey:
    def test_numeric_length_beats_lexicographic(self):
        assert sort_key("9") < sort_key("10")

    def test_alpha_length_beats_lexicographic(self):
        assert sort_key("Z") < sort_key("AA")

    def test_same_length_lexicographic(self):
        assert sort_key("A") < sort_key("B")
        assert sort_key("1") < sort_key("2")

    def test_ordering_of_a_family(self):
        revisions = ["AA", "9", "Z", "10", "A", "1"]
        assert sorted(revisions, key=sort_key) == ["1", "9", "A", "Z", "10", "AA"]


class TestStartRevisions:
    def test_contains_expected_values(self):
        assert START_REVISIONS == ("A", "0", "1")
