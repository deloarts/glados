"""
Tests for domain.services.feature_tree_template: a template is accepted
verbatim unless it spans more than one line, exceeds the length cap, or
links to the property it is written into.
"""

import pytest

from src.modules.external_data.domain.services.feature_tree_template import (
    MAX_FEATURE_TREE_TEMPLATE_LENGTH,
)
from src.modules.external_data.domain.services.feature_tree_template import (
    validate_feature_tree_template,
)

OWN = "Glados.FeatureTreeRepresentation"


class TestValidateFeatureTreeTemplate:
    def test_default_made_template_passes(self):
        validate_feature_tree_template(
            "made",
            '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")',
            OWN,
        )

    def test_link_to_a_property_glados_does_not_map_passes(self):
        validate_feature_tree_template("made", '$PRP:"SW-File Name" $PRP:"Description"', OWN)

    def test_static_text_and_braces_pass(self):
        validate_feature_tree_template("bought", "{Static} text", OWN)

    def test_empty_template_passes(self):
        validate_feature_tree_template("made", "", OWN)

    def test_template_at_the_length_cap_passes(self):
        validate_feature_tree_template("made", "x" * MAX_FEATURE_TREE_TEMPLATE_LENGTH, OWN)

    def test_template_over_the_length_cap_is_rejected(self):
        with pytest.raises(ValueError, match="longer than"):
            validate_feature_tree_template(
                "made", "x" * (MAX_FEATURE_TREE_TEMPLATE_LENGTH + 1), OWN
            )

    @pytest.mark.parametrize("separator", ["\n", "\r\n", "\t"])
    def test_line_break_or_control_character_is_rejected(self, separator):
        with pytest.raises(ValueError, match="single line"):
            validate_feature_tree_template(
                "made", f'$PRP:"PDM.PartNumber"{separator}$PRP:"PDM.Revision"', OWN
            )

    def test_link_to_its_own_property_is_rejected(self):
        with pytest.raises(ValueError, match="its own property"):
            validate_feature_tree_template("bought", f'$PRP:"Glados.ArticleName" $PRP:"{OWN}"', OWN)

    def test_self_reference_is_detected_regardless_of_case(self):
        with pytest.raises(ValueError, match="its own property"):
            validate_feature_tree_template("made", '$prp:"glados.featuretreerepresentation"', OWN)

    def test_unmapped_own_property_never_counts_as_a_self_reference(self):
        validate_feature_tree_template("made", f'$PRP:"{OWN}"', "")
