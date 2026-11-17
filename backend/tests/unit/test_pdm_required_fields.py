"""
Unit tests for required-field validation (docs/reference/pdm-ingest.md section 7):
the locked set and candidate catalogue in
src.modules.external_data.domain.services.pdm_required_fields, and the evaluator in
src.modules.external_data.application.services.pdm_required_fields. No database, no HTTP.
"""

import pytest

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.external_data.application.services.pdm_required_fields import (
    format_missing_required_fields_reason,
)
from src.modules.external_data.application.services.pdm_required_fields import (
    missing_required_fields,
)
from src.modules.external_data.application.services.pdm_required_fields import (
    split_missing_required_fields,
)
from src.modules.external_data.domain.services.pdm_required_fields import LOCKED_REQUIRED_FIELDS
from src.modules.external_data.domain.services.pdm_required_fields import (
    normalize_required_fields_selection,
)
from src.modules.external_data.domain.services.pdm_required_fields import required_field_candidates
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings

# ── Domain: locked set and candidate catalogue ──────────────────────────


class TestLockedRequiredFields:
    def test_made_locked_fields(self):
        assert LOCKED_REQUIRED_FIELDS["made"] == ("part_number", "revision", "article_name")

    def test_bought_locked_fields(self):
        # revision is not part of a bought item's identity (docs/
        # FIELD_OWNERSHIP.md principle 2), so unlike made items it is not
        # locked; it is a configurable candidate instead, see
        # TestRequiredFieldCandidates.test_bought_candidates_include_revision.
        assert LOCKED_REQUIRED_FIELDS["bought"] == (
            "part_number",
            "article_name",
            "order_code_1",
            "manufacturer_id",
        )


class TestRequiredFieldCandidates:
    def test_made_candidates_exclude_locked_fields(self):
        candidates = required_field_candidates("made")
        for field in LOCKED_REQUIRED_FIELDS["made"]:
            assert field not in candidates

    def test_made_candidates_include_mappable_fields_and_the_pseudo_rule(self):
        candidates = required_field_candidates("made")
        assert "material" in candidates
        assert "mass" in candidates
        assert "fabrication_step" in candidates
        # The pseudo-rule is last, after every real field.
        assert candidates[-1] == "fabrication_step"

    def test_made_candidates_exclude_non_mappable_fields(self):
        candidates = required_field_candidates("made")
        assert "status" not in candidates  # web-owned, not mappable
        assert "public_id" not in candidates  # server-owned, not mappable

    def test_bought_candidates_exclude_locked_fields(self):
        candidates = required_field_candidates("bought")
        for field in LOCKED_REQUIRED_FIELDS["bought"]:
            assert field not in candidates

    def test_bought_candidates_include_mappable_fields_and_have_no_pseudo_rule(self):
        candidates = required_field_candidates("bought")
        assert "gtin" in candidates
        assert "mass" in candidates
        assert "fabrication_step" not in candidates

    def test_bought_candidates_include_revision(self):
        # Unlike made items, revision is data for a bought item, not part
        # of its identity, so it is a configurable candidate rather than
        # locked; see TestLockedRequiredFields.test_bought_locked_fields.
        assert "revision" in required_field_candidates("bought")

    def test_made_candidate_never_appears_for_bought(self):
        assert "base_size" not in required_field_candidates("bought")

    def test_made_candidates_exclude_labels_and_the_feature_tree_field(self):
        """A label or the feature-tree render field is mappable but never
        something ingest reads (item_field_ownership.addin_written_fields);
        requiring one would be permanently unsatisfiable, since
        map_variables() never includes it in what it reads."""
        candidates = required_field_candidates("made")
        assert "article_group_names" not in candidates
        assert "process_names" not in candidates
        assert "source_item_name" not in candidates
        assert "feature_tree_representation" not in candidates

    def test_bought_candidates_exclude_labels_and_the_feature_tree_field(self):
        candidates = required_field_candidates("bought")
        assert "manufacturer_name" not in candidates
        assert "article_group_names" not in candidates
        assert "feature_tree_representation" not in candidates


class TestNormalizeRequiredFieldsSelection:
    def test_empty_selection_stays_empty(self):
        assert normalize_required_fields_selection("made", []) == []

    def test_valid_names_pass_through_in_order(self):
        assert normalize_required_fields_selection("made", ["fabrication_step", "material"]) == [
            "fabrication_step",
            "material",
        ]

    def test_locked_names_dropped_silently(self):
        result = normalize_required_fields_selection(
            "made", ["part_number", "material", "revision", "article_name"]
        )
        assert result == ["material"]

    def test_duplicates_dropped_silently_keeping_first_occurrence(self):
        result = normalize_required_fields_selection("made", ["material", "mass", "material"])
        assert result == ["material", "mass"]

    def test_unknown_name_raises_value_error(self):
        with pytest.raises(ValueError, match="not_a_field"):
            normalize_required_fields_selection("made", ["not_a_field"])

    def test_bought_only_field_is_unknown_for_made(self):
        with pytest.raises(ValueError):
            normalize_required_fields_selection("made", ["order_code_1"])

    def test_made_only_field_is_unknown_for_bought(self):
        with pytest.raises(ValueError):
            normalize_required_fields_selection("bought", ["base_size"])


# ── Application: the missing-fields evaluator ───────────────────────────


def _process(
    *, role: str = StepRole.FABRICATION.value, fabrication_method_id: int | None = 1
) -> CreateMadeItemProcessCommand:
    return CreateMadeItemProcessCommand(role=role, fabrication_method_id=fabrication_method_id)


class TestMissingRequiredFieldsLockedSet:
    def test_nothing_missing_when_every_locked_field_present(self):
        settings = make_pdm_settings()
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        assert missing_required_fields("made", mapped, settings) == []

    def test_reports_missing_locked_fields_in_order(self):
        settings = make_pdm_settings()
        assert missing_required_fields("made", {}, settings) == [
            "part_number",
            "revision",
            "article_name",
        ]

    def test_blank_value_counts_as_missing(self):
        settings = make_pdm_settings()
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "   "}
        assert missing_required_fields("made", mapped, settings) == ["article_name"]

    def test_bought_locked_fields_include_order_code_and_manufacturer(self):
        # revision is deliberately absent here: with nothing configured
        # (the fixture's default required_fields={"bought": []}), it is
        # neither locked nor selected, so it is not reported missing; see
        # test_bought_configured_revision_reported_after_the_locked_set.
        settings = make_pdm_settings()
        assert missing_required_fields("bought", {}, settings) == [
            "part_number",
            "article_name",
            "order_code_1",
            "manufacturer_id",
        ]

    def test_bought_configured_revision_reported_after_the_locked_set(self):
        # Once selected (the production default, see admin_settings_model.
        # py's _REQUIRED_FIELDS_DEFAULT), revision is evaluated as a
        # configured field, in item_fields() order, after the locked
        # fields, not in LOCKED_REQUIRED_FIELDS' old second position.
        settings = make_pdm_settings(required_fields={"made": [], "bought": ["revision"]})
        assert missing_required_fields("bought", {}, settings) == [
            "part_number",
            "article_name",
            "order_code_1",
            "manufacturer_id",
            "revision",
        ]


class TestMissingRequiredFieldsConfiguredSelection:
    def test_nothing_reported_when_nothing_configured(self):
        settings = make_pdm_settings(required_fields={"made": [], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        assert missing_required_fields("made", mapped, settings) == []

    def test_configured_field_reported_bare_when_a_variable_is_mapped(self):
        settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        assert missing_required_fields("made", mapped, settings) == ["material"]

    def test_configured_field_present_is_not_reported(self):
        settings = make_pdm_settings(required_fields={"made": ["material"], "bought": []})
        mapped = {
            "part_number": "CAD-1",
            "revision": "A",
            "article_name": "Bracket",
            "material": "1.0037",
        }
        assert missing_required_fields("made", mapped, settings) == []

    def test_configured_field_annotated_when_no_variable_mapped(self):
        made_map = {"part_number": "PDM.PartNumber", "revision": "PDM.Revision"}
        settings = make_pdm_settings(
            made_map=made_map, required_fields={"made": ["material"], "bought": []}
        )
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        assert missing_required_fields("made", mapped, settings) == [
            "material (no PDM variable mapped)"
        ]

    def test_configured_fields_reported_in_item_fields_order_not_selection_order(self):
        settings = make_pdm_settings(required_fields={"made": ["mass", "material"], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        # material precedes mass in item_fields() order regardless of how
        # the admin's stored selection lists them.
        assert missing_required_fields("made", mapped, settings) == ["material", "mass"]


class TestMissingRequiredFieldsPseudoRule:
    def test_fabrication_step_missing_when_not_configured_is_not_reported(self):
        settings = make_pdm_settings(required_fields={"made": [], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        assert missing_required_fields("made", mapped, settings, []) == []

    def test_fabrication_step_missing_when_configured_and_no_processes(self):
        settings = make_pdm_settings(required_fields={"made": ["fabrication_step"], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        assert missing_required_fields("made", mapped, settings, []) == ["fabrication_step"]

    def test_fabrication_step_missing_when_only_an_inspection_step_present(self):
        settings = make_pdm_settings(required_fields={"made": ["fabrication_step"], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        processes = [_process(role=StepRole.INSPECTION.value, fabrication_method_id=None)]
        assert missing_required_fields("made", mapped, settings, processes) == ["fabrication_step"]

    def test_fabrication_step_missing_when_fabrication_method_id_is_none(self):
        settings = make_pdm_settings(required_fields={"made": ["fabrication_step"], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        processes = [_process(fabrication_method_id=None)]
        assert missing_required_fields("made", mapped, settings, processes) == ["fabrication_step"]

    def test_fabrication_step_satisfied_when_a_fabrication_step_is_present(self):
        settings = make_pdm_settings(required_fields={"made": ["fabrication_step"], "bought": []})
        mapped = {"part_number": "CAD-1", "revision": "A", "article_name": "Bracket"}
        processes = [_process()]
        assert missing_required_fields("made", mapped, settings, processes) == []

    def test_pseudo_rule_never_applies_to_bought(self):
        settings = make_pdm_settings(required_fields={"made": [], "bought": []})
        mapped = {
            "part_number": "CAD-2",
            "revision": "3",
            "article_name": "Bolt",
            "order_code_1": "OC-1",
            "manufacturer_id": "1",
        }
        assert missing_required_fields("bought", mapped, settings) == []


class TestMissingRequiredFieldsOrdering:
    def test_locked_then_configured_then_rule(self):
        settings = make_pdm_settings(
            required_fields={"made": ["fabrication_step", "material"], "bought": []}
        )
        assert missing_required_fields("made", {}, settings, []) == [
            "part_number",
            "revision",
            "article_name",
            "material",
            "fabrication_step",
        ]


class TestSplitMissingRequiredFields:
    """ValidatePdmPayload-only split of missing_required_fields' output by
    field ownership (docs/reference/pdm-ingest.md section 8): a PDM-owned
    field is pending assignment by the release workflow, never a reason
    an engineer is held to."""

    def test_pdm_owned_locked_fields_go_to_pending(self):
        missing = ["part_number", "revision", "article_name"]
        engineer, pending = split_missing_required_fields("made", missing)
        assert engineer == ["article_name"]
        assert pending == ["part_number", "revision"]

    def test_bought_part_number_is_the_only_pdm_owned_locked_field(self):
        missing = ["part_number", "article_name", "order_code_1", "manufacturer_id"]
        engineer, pending = split_missing_required_fields("bought", missing)
        assert engineer == ["article_name", "order_code_1", "manufacturer_id"]
        assert pending == ["part_number"]

    def test_pdm_owned_configured_field_goes_to_pending(self):
        # revision_date/revision_note are PDM-owned even though they are
        # only configurable required fields, not locked; see
        # src.modules.catalogue.domain.policies.item_field_ownership's made-item owner table.
        engineer, pending = split_missing_required_fields("made", ["revision_date"])
        assert engineer == []
        assert pending == ["revision_date"]

    def test_pending_is_ordered_like_item_fields_regardless_of_input_order(self):
        _engineer, pending = split_missing_required_fields("made", ["revision", "part_number"])
        assert pending == ["part_number", "revision"]

    def test_no_variable_mapped_annotation_stays_on_the_engineer_descriptor(self):
        missing = ["material (no PDM variable mapped)"]
        engineer, pending = split_missing_required_fields("made", missing)
        assert engineer == ["material (no PDM variable mapped)"]
        assert pending == []

    def test_pseudo_rule_name_is_never_pdm_owned(self):
        engineer, pending = split_missing_required_fields("made", ["fabrication_step"])
        assert engineer == ["fabrication_step"]
        assert pending == []

    def test_nothing_missing_splits_to_two_empty_lists(self):
        assert split_missing_required_fields("made", []) == ([], [])


class TestFormatMissingRequiredFieldsReason:
    def test_single_field(self):
        assert format_missing_required_fields_reason(["article_name"]) == (
            "required fields missing: article_name"
        )

    def test_multiple_fields(self):
        assert format_missing_required_fields_reason(["material", "fabrication_step"]) == (
            "required fields missing: material, fabrication_step"
        )
