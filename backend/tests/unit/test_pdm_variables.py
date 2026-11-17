"""
Unit tests for src.modules.external_data.application.services.pdm_variables: configuration
selection, field-mapping resolution and the per-field coercions
IngestPdmFile relies on being tolerant of garbage input.
"""

from datetime import date

import pytest

from src.modules.external_data.application.services.pdm_variables import kind_variable_name
from src.modules.external_data.application.services.pdm_variables import map_variables
from src.modules.external_data.application.services.pdm_variables import parse_date
from src.modules.external_data.application.services.pdm_variables import parse_int
from src.modules.external_data.application.services.pdm_variables import parse_int_list
from src.modules.external_data.application.services.pdm_variables import parse_mass
from src.modules.external_data.application.services.pdm_variables import parse_processes
from src.modules.external_data.application.services.pdm_variables import process_entry_missing_role
from src.modules.external_data.application.services.pdm_variables import resolve_file_kind
from src.modules.external_data.application.services.pdm_variables import select_configuration
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmConfigVariables


def make_pdm_settings(
    *, made_item_variable_map: dict[str, str] | None = None, **overrides: object
) -> AdminPdmSettings:
    defaults: dict[str, object] = dict(
        id=1,
        made_item_variable_map=(
            made_item_variable_map
            if made_item_variable_map is not None
            else {"kind": "Glados.Kind"}
        ),
        bought_item_variable_map={},
        enabled=False,
        base_url="",
        vault_name="",
        username="",
        password=None,
        verify_certificate=True,
        timeout_seconds=15,
        session_token=None,
        session_user_id=None,
        session_obtained_at=None,
        watched_folders=[],
        made_released_state_ids=[],
        made_obsolete_state_ids=[],
        made_replaced_state_ids=[],
        bought_released_state_ids=[],
        bought_obsolete_state_ids=[],
        bought_replaced_state_ids=[],
        poll_interval_minutes=15,
        vault_id="",
        cad_items_read_only=True,
        last_poll_at=None,
        last_poll_error=None,
        last_poll_summary=None,
        writeback_enabled=False,
        made_item_extensions=["sldprt"],
        bought_item_extensions=["sldprt", "sldasm"],
        document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        thumbnails_enabled=False,
        stuck_after_days=7,
        reconcile_requested_deep=None,
        required_fields={"made": [], "bought": []},
    )
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class TestSelectConfiguration:
    def test_empty_list_returns_empty_dict(self):
        assert select_configuration([]) == {}

    def test_prefers_at_configuration(self):
        configs = [
            PdmConfigVariables(
                configuration_name="Default", configuration_id=1, variables={"A": "1"}
            ),
            PdmConfigVariables(configuration_name="@", configuration_id=2, variables={"B": "2"}),
        ]
        assert select_configuration(configs) == {"B": "2"}

    def test_returns_none_when_no_at_configuration_among_several(self):
        # Every SolidWorks file always carries a file-level "@" card, so a
        # non-empty list missing one is reported by the caller as "no
        # file-level datacard configuration" rather than guessing at some
        # other configuration's values, such as configs[0] ("Default" here).
        configs = [
            PdmConfigVariables(
                configuration_name="Default", configuration_id=1, variables={"A": "1"}
            ),
            PdmConfigVariables(
                configuration_name="Other", configuration_id=2, variables={"B": "2"}
            ),
        ]
        assert select_configuration(configs) is None


class TestMapVariables:
    def test_maps_configured_present_variables(self):
        variable_map = {"part_number": "PDM.PartNumber", "revision": "PDM.Revision"}
        variables = {"PDM.PartNumber": "CAD-1", "PDM.Revision": "A"}
        result = map_variables("made", variable_map, variables)
        assert result == {"part_number": "CAD-1", "revision": "A"}

    def test_unmapped_field_is_excluded(self):
        variable_map = {"part_number": "", "revision": "PDM.Revision"}
        variables = {"PDM.Revision": "A"}
        result = map_variables("made", variable_map, variables)
        assert result == {"revision": "A"}

    def test_variable_absent_from_payload_is_excluded(self):
        variable_map = {"part_number": "PDM.PartNumber"}
        variables = {}
        result = map_variables("made", variable_map, variables)
        assert result == {}

    def test_blank_value_is_still_included(self):
        variable_map = {"note": "Glados.Note"}
        variables = {"Glados.Note": ""}
        result = map_variables("made", variable_map, variables)
        assert result == {"note": ""}

    @pytest.mark.parametrize(
        "placeholder", ["Material <not specified>", "Material <nicht angegeben>", "<not specified>"]
    )
    def test_solidworks_material_placeholder_maps_to_blank(self, placeholder):
        variable_map = {"material": "Glados.Material"}
        result = map_variables("made", variable_map, {"Glados.Material": placeholder})
        assert result == {"material": ""}

    @pytest.mark.parametrize("material", ["1.0037", "S235JR", "AlMg3 <H22"])
    def test_a_real_material_is_kept(self, material):
        variable_map = {"material": "Glados.Material"}
        result = map_variables("made", variable_map, {"Glados.Material": material})
        assert result == {"material": material}

    def test_placeholder_text_in_another_field_is_kept(self):
        variable_map = {"note": "Glados.Note"}
        result = map_variables("made", variable_map, {"Glados.Note": "Material <not specified>"})
        assert result == {"note": "Material <not specified>"}

    def test_field_not_mappable_for_kind_is_ignored(self):
        # "order_code_1" is a bought-only field, not in MADE_ITEM_MAPPABLE_FIELDS.
        variable_map = {"order_code_1": "Glados.OrderCode1"}
        variables = {"Glados.OrderCode1": "OC-1"}
        result = map_variables("made", variable_map, variables)
        assert result == {}

    def test_bought_kind_uses_bought_mappable_fields(self):
        variable_map = {"order_code_1": "Glados.OrderCode1"}
        variables = {"Glados.OrderCode1": "OC-1"}
        result = map_variables("bought", variable_map, variables)
        assert result == {"order_code_1": "OC-1"}

    def test_kind_entry_is_never_included_in_the_field_values(self):
        """`kind` routes which catalogue a file belongs to, it is not a
        MadeItem/BoughtItem column; IngestPdmFile must never see it among
        the fields it writes, for either item kind."""
        variable_map = {"kind": "Glados.Kind"}
        variables = {"Glados.Kind": "made"}
        assert map_variables("made", variable_map, variables) == {}
        assert map_variables("bought", variable_map, variables) == {}

    def test_label_and_feature_tree_fields_are_never_included_in_the_field_values(self):
        """A label (item_field_ownership.MADE_ITEM_LABEL_FIELDS/
        BOUGHT_ITEM_LABEL_FIELDS) and the feature-tree render field are
        mappable rows the add-in writes, never something ingest reads,
        even when a variable name is configured and present in the
        payload, map_variables() must still exclude them."""
        made_map = {
            "article_group_names": "Glados.ArticleGroupNames",
            "process_names": "Glados.ProcessNames",
            "source_item_name": "Glados.SourceItemName",
            "feature_tree_representation": "Glados.FeatureTreeRepresentation",
        }
        made_variables = {
            "Glados.ArticleGroupNames": "Group A",
            "Glados.ProcessNames": "Turning",
            "Glados.SourceItemName": "Rod 10x100",
            "Glados.FeatureTreeRepresentation": "CAD-1001 RevA (Bracket)",
        }
        assert map_variables("made", made_map, made_variables) == {}

        bought_map = {
            "manufacturer_name": "Glados.ManufacturerName",
            "article_group_names": "Glados.ArticleGroupNames",
            "feature_tree_representation": "Glados.FeatureTreeRepresentation",
        }
        bought_variables = {
            "Glados.ManufacturerName": "Acme",
            "Glados.ArticleGroupNames": "Group A",
            "Glados.FeatureTreeRepresentation": "Bracket - OC-1 - Acme",
        }
        assert map_variables("bought", bought_map, bought_variables) == {}


class TestKindVariableName:
    def test_reads_the_configured_variable_name(self):
        settings = make_pdm_settings(made_item_variable_map={"kind": "Custom.Kind"})
        assert kind_variable_name(settings) == "Custom.Kind"


class TestResolveFileKind:
    def test_by_kind_folder_resolves_made(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="by_kind", variables={"Glados.Kind": "made"}, settings=settings
        )
        assert result.kind == "made"
        assert result.raw == "made"
        assert result.conflict is None

    def test_by_kind_folder_resolves_bought(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="by_kind", variables={"Glados.Kind": "bought"}, settings=settings
        )
        assert result.kind == "bought"
        assert result.conflict is None

    def test_by_kind_folder_with_empty_value_is_unresolved(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="by_kind", variables={"Glados.Kind": ""}, settings=settings
        )
        assert result.kind is None
        assert result.raw == ""
        assert result.conflict is None

    def test_by_kind_folder_with_missing_variable_is_unresolved(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(folder_kind="by_kind", variables={}, settings=settings)
        assert result.kind is None
        assert result.raw == ""

    def test_by_kind_folder_with_unrecognised_value_is_unresolved(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="by_kind", variables={"Glados.Kind": "weldment"}, settings=settings
        )
        assert result.kind is None
        assert result.raw == "weldment"
        assert result.conflict is None

    def test_explicit_folder_ignores_a_blank_variable(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="made", variables={"Glados.Kind": ""}, settings=settings
        )
        assert result.kind == "made"
        assert result.conflict is None

    def test_explicit_folder_ignores_an_agreeing_variable(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="bought", variables={"Glados.Kind": "bought"}, settings=settings
        )
        assert result.kind == "bought"
        assert result.conflict is None

    def test_explicit_folder_flags_a_disagreeing_variable(self):
        settings = make_pdm_settings()
        result = resolve_file_kind(
            folder_kind="made", variables={"Glados.Kind": "bought"}, settings=settings
        )
        assert result.kind is None
        assert result.conflict == "kind variable says bought, folder says made"

    def test_uses_the_configured_kind_variable_name(self):
        settings = make_pdm_settings(made_item_variable_map={"kind": "Custom.Kind"})
        result = resolve_file_kind(
            folder_kind="by_kind", variables={"Custom.Kind": "bought"}, settings=settings
        )
        assert result.kind == "bought"


class TestParseMass:
    def test_dot_decimal(self):
        assert parse_mass("123.4") == 123

    def test_comma_decimal(self):
        assert parse_mass("123,6") == 124

    def test_empty_returns_none(self):
        assert parse_mass("") is None
        assert parse_mass("   ") is None
        assert parse_mass(None) is None

    def test_garbage_returns_none(self):
        assert parse_mass("not-a-number") is None

    def test_negative_rounds_away_from_zero(self):
        assert parse_mass("-2,5") == -3


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2026-09-03") == date(2026, 9, 3)

    def test_german_format(self):
        assert parse_date("03.09.2026") == date(2026, 9, 3)

    def test_empty_returns_none(self):
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_garbage_returns_none(self):
        assert parse_date("not-a-date") is None


class TestParseIntList:
    def test_comma_separated(self):
        assert parse_int_list("1,2,3") == [1, 2, 3]

    def test_skips_unparsable_tokens(self):
        assert parse_int_list("1,x,3") == [1, 3]

    def test_empty_returns_empty_list(self):
        assert parse_int_list("") == []
        assert parse_int_list(None) == []

    def test_all_garbage_returns_empty_list(self):
        assert parse_int_list("a,b,c") == []


class TestParseInt:
    def test_valid_int(self):
        assert parse_int("42") == 42

    def test_empty_returns_none(self):
        assert parse_int("") is None
        assert parse_int(None) is None

    def test_garbage_returns_none(self):
        assert parse_int("abc") is None


class TestParseProcesses:
    def test_valid_fabrication_step(self):
        raw = (
            '[{"role":"fabrication","fabrication_method_id":5,"group_index":0,'
            '"estimated_setup_minutes":10,"estimated_minutes_per_piece":1.5,"note":"turn"}]'
        )
        steps = parse_processes(raw)
        assert len(steps) == 1
        step = steps[0]
        assert step.role == "fabrication"
        assert step.fabrication_method_id == 5
        assert step.inspection_method_id is None
        assert step.group_index == 0
        assert step.estimated_setup_minutes == 10
        assert step.estimated_minutes_per_piece == 1.5
        assert step.note == "turn"

    def test_position_is_array_order(self):
        raw = (
            '[{"role":"fabrication","fabrication_method_id":1,"group_index":0},'
            '{"role":"fabrication","fabrication_method_id":2,"group_index":1}]'
        )
        steps = parse_processes(raw)
        assert [s.fabrication_method_id for s in steps] == [1, 2]

    def test_inspection_step(self):
        raw = '[{"role":"inspection","inspection_method_id":9,"group_index":0}]'
        steps = parse_processes(raw)
        assert steps[0].role == "inspection"
        assert steps[0].inspection_method_id == 9
        assert steps[0].fabrication_method_id is None

    def test_empty_returns_empty_list(self):
        assert parse_processes("") == []
        assert parse_processes(None) == []
        assert parse_processes("[]") == []

    def test_non_json_returns_empty_list(self):
        assert parse_processes("not json at all") == []

    def test_non_array_json_returns_empty_list(self):
        assert parse_processes('{"role": "fabrication"}') == []

    def test_malformed_entry_is_dropped_individually(self):
        # Second entry has a negative method id (fails CreateMadeItemProcessCommand's gt=0);
        # the first, valid entry must still come through.
        raw = (
            '[{"role":"fabrication","fabrication_method_id":1,"group_index":0},'
            '{"role":"fabrication","fabrication_method_id":-1,"group_index":1}]'
        )
        steps = parse_processes(raw)
        assert len(steps) == 1
        assert steps[0].fabrication_method_id == 1

    def test_entry_missing_role_is_dropped_not_defaulted(self):
        # The add-in always writes role, so a missing one is malformed and
        # must not be silently defaulted to "fabrication".
        raw = '[{"fabrication_method_id":1,"group_index":0}]'
        assert parse_processes(raw) == []

    def test_entry_with_blank_role_is_dropped(self):
        raw = '[{"role":"","fabrication_method_id":1,"group_index":0}]'
        assert parse_processes(raw) == []

    def test_entry_missing_role_does_not_drop_a_sibling_valid_entry(self):
        raw = (
            '[{"fabrication_method_id":1,"group_index":0},'
            '{"role":"fabrication","fabrication_method_id":2,"group_index":1}]'
        )
        steps = parse_processes(raw)
        assert len(steps) == 1
        assert steps[0].fabrication_method_id == 2


class TestProcessEntryMissingRole:
    def test_true_when_an_entry_has_no_role_key(self):
        raw = '[{"fabrication_method_id":1,"group_index":0}]'
        assert process_entry_missing_role(raw) is True

    def test_true_when_an_entry_has_a_blank_role(self):
        raw = '[{"role":"  ","fabrication_method_id":1,"group_index":0}]'
        assert process_entry_missing_role(raw) is True

    def test_true_when_only_one_of_several_entries_lacks_a_role(self):
        raw = (
            '[{"role":"fabrication","fabrication_method_id":1,"group_index":0},'
            '{"fabrication_method_id":2,"group_index":1}]'
        )
        assert process_entry_missing_role(raw) is True

    def test_false_when_every_entry_has_a_role(self):
        raw = '[{"role":"fabrication","fabrication_method_id":1,"group_index":0}]'
        assert process_entry_missing_role(raw) is False

    def test_false_for_empty_or_absent_payload(self):
        assert process_entry_missing_role(None) is False
        assert process_entry_missing_role("") is False
        assert process_entry_missing_role("[]") is False

    def test_false_for_garbage_top_level(self):
        assert process_entry_missing_role("not json") is False
        assert process_entry_missing_role('{"role": "fabrication"}') is False
