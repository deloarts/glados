"""
Unit tests for AdminPdmSettings' own logic: is_configured,
connection_differs, sync_scope_differs, released_state_ids_for/
obsolete_state_ids_for/replaced_state_ids_for,
assert_state_id_lists_disjoint and normalized_required_fields. No
database, no HTTP.
"""

import pytest

from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmSettingsInvalidError


def _pdm(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = {
        "id": 1,
        "made_item_variable_map": {},
        "bought_item_variable_map": {},
        "enabled": False,
        "base_url": "http://pdm.example.local:65453",
        "vault_name": "MainVault",
        "username": "svc-glados",
        "password": "secret",
        "verify_certificate": True,
        "timeout_seconds": 15,
        "session_token": None,
        "session_user_id": None,
        "session_obtained_at": None,
        "watched_folders": [],
        "made_released_state_ids": [],
        "made_obsolete_state_ids": [],
        "made_replaced_state_ids": [],
        "bought_released_state_ids": [],
        "bought_obsolete_state_ids": [],
        "bought_replaced_state_ids": [],
        "poll_interval_minutes": 15,
        "vault_id": "",
        "cad_items_read_only": True,
        "last_poll_at": None,
        "last_poll_error": None,
        "last_poll_summary": None,
        "writeback_enabled": False,
        "made_item_extensions": ["sldprt"],
        "bought_item_extensions": ["sldprt", "sldasm"],
        "document_categories": {"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
        "thumbnails_enabled": False,
        "stuck_after_days": 7,
        "reconcile_requested_deep": None,
        "required_fields": {"made": [], "bought": []},
    }
    defaults.update(overrides)
    return AdminPdmSettings(**defaults)  # type: ignore[arg-type]


class TestIsConfigured:
    def test_true_when_every_connection_field_is_set(self):
        assert _pdm().is_configured is True

    def test_false_when_base_url_is_blank(self):
        assert _pdm(base_url="").is_configured is False

    def test_false_when_vault_name_is_blank(self):
        assert _pdm(vault_name="").is_configured is False

    def test_false_when_username_is_blank(self):
        assert _pdm(username="").is_configured is False

    def test_false_when_password_is_none(self):
        assert _pdm(password=None).is_configured is False

    def test_false_when_password_is_empty_string(self):
        assert _pdm(password="").is_configured is False

    def test_enabled_and_session_fields_do_not_affect_configured(self):
        """`enabled` does not affect "configured", and a stored session is
        never required for "configured": re-authentication is what
        configured gates."""
        assert (
            _pdm(
                enabled=False,
                session_token=None,
                session_user_id=None,
                session_obtained_at=None,
            ).is_configured
            is True
        )


class TestConnectionDiffers:
    def test_false_for_identical_connections(self):
        a = _pdm()
        b = _pdm()
        assert a.connection_differs(b) is False

    def test_true_when_base_url_differs(self):
        a = _pdm()
        b = _pdm(base_url="http://other.example.local:65453")
        assert a.connection_differs(b) is True

    def test_true_when_vault_name_differs(self):
        a = _pdm()
        b = _pdm(vault_name="OtherVault")
        assert a.connection_differs(b) is True

    def test_true_when_username_differs(self):
        a = _pdm()
        b = _pdm(username="other-user")
        assert a.connection_differs(b) is True

    def test_true_when_password_differs(self):
        a = _pdm()
        b = _pdm(password="different-secret")
        assert a.connection_differs(b) is True

    def test_false_when_only_non_connection_fields_differ(self):
        """enabled, timeout_seconds, verify_certificate and the session
        fields are not part of "the connection" for this method. Only
        UpdatePdmSettings' own base_url/vault_name/username/password
        change decides whether a stored session must be cleared."""
        a = _pdm()
        b = _pdm(
            enabled=True,
            verify_certificate=False,
            timeout_seconds=30,
            session_token="tok",
            session_user_id=7,
        )
        assert a.connection_differs(b) is False


class TestStateIdsForKind:
    """released_state_ids_for/obsolete_state_ids_for resolve the pair
    matching a given item kind. IngestPdmFile's Rule 3 reads them this
    way instead of one shared list."""

    def test_released_state_ids_for_made(self):
        settings = _pdm(made_released_state_ids=[1, 2], bought_released_state_ids=[3])
        assert settings.released_state_ids_for("made") == [1, 2]

    def test_released_state_ids_for_bought(self):
        settings = _pdm(made_released_state_ids=[1, 2], bought_released_state_ids=[3])
        assert settings.released_state_ids_for("bought") == [3]

    def test_obsolete_state_ids_for_made(self):
        settings = _pdm(made_obsolete_state_ids=[4], bought_obsolete_state_ids=[5, 6])
        assert settings.obsolete_state_ids_for("made") == [4]

    def test_obsolete_state_ids_for_bought(self):
        settings = _pdm(made_obsolete_state_ids=[4], bought_obsolete_state_ids=[5, 6])
        assert settings.obsolete_state_ids_for("bought") == [5, 6]

    def test_replaced_state_ids_for_made(self):
        settings = _pdm(made_replaced_state_ids=[7], bought_replaced_state_ids=[8, 9])
        assert settings.replaced_state_ids_for("made") == [7]

    def test_replaced_state_ids_for_bought(self):
        settings = _pdm(made_replaced_state_ids=[7], bought_replaced_state_ids=[8, 9])
        assert settings.replaced_state_ids_for("bought") == [8, 9]


class TestAssertStateIdListsDisjoint:
    """assert_state_id_lists_disjoint raises PdmSettingsInvalidError,
    naming the overlap, whenever a kind's released/obsolete/replaced
    lists are not pairwise disjoint. This is checked independently for made and
    bought, and for each of the three possible pairings."""

    def test_disjoint_lists_do_not_raise(self):
        settings = _pdm(
            made_released_state_ids=[1],
            made_obsolete_state_ids=[2],
            made_replaced_state_ids=[3],
            bought_released_state_ids=[4],
            bought_obsolete_state_ids=[5],
            bought_replaced_state_ids=[6],
        )
        settings.assert_state_id_lists_disjoint()

    def test_made_released_and_obsolete_overlap_raises(self):
        settings = _pdm(made_released_state_ids=[1, 2], made_obsolete_state_ids=[2, 3])
        with pytest.raises(PdmSettingsInvalidError):
            settings.assert_state_id_lists_disjoint()

    def test_made_released_and_replaced_overlap_raises(self):
        settings = _pdm(made_released_state_ids=[1], made_replaced_state_ids=[1])
        with pytest.raises(PdmSettingsInvalidError):
            settings.assert_state_id_lists_disjoint()

    def test_made_obsolete_and_replaced_overlap_raises(self):
        settings = _pdm(made_obsolete_state_ids=[1], made_replaced_state_ids=[1])
        with pytest.raises(PdmSettingsInvalidError):
            settings.assert_state_id_lists_disjoint()

    def test_bought_replaced_overlap_raises(self):
        settings = _pdm(bought_released_state_ids=[9], bought_replaced_state_ids=[9])
        with pytest.raises(PdmSettingsInvalidError):
            settings.assert_state_id_lists_disjoint()

    def test_overlap_message_names_the_ids(self):
        settings = _pdm(made_released_state_ids=[1, 2], made_replaced_state_ids=[2])
        with pytest.raises(PdmSettingsInvalidError) as exc_info:
            settings.assert_state_id_lists_disjoint()
        assert "2" in str(exc_info.value)


class TestSyncScopeDiffers:
    """sync_scope_differs tracks all six per-kind released/obsolete/
    replaced lists independently. UpdatePdmSettings uses it to decide
    whether to requeue skipped files (see
    tests/unit/admin_settings/test_update_pdm_settings.py's own coverage
    of that requeue behaviour)."""

    def test_false_for_identical_settings(self):
        a = _pdm()
        b = _pdm()
        assert a.sync_scope_differs(b) is False

    def test_true_when_made_released_state_ids_differ(self):
        a = _pdm(made_released_state_ids=[1])
        b = _pdm(made_released_state_ids=[2])
        assert a.sync_scope_differs(b) is True

    def test_true_when_made_obsolete_state_ids_differ(self):
        a = _pdm(made_obsolete_state_ids=[1])
        b = _pdm(made_obsolete_state_ids=[2])
        assert a.sync_scope_differs(b) is True

    def test_true_when_bought_released_state_ids_differ(self):
        a = _pdm(bought_released_state_ids=[1])
        b = _pdm(bought_released_state_ids=[2])
        assert a.sync_scope_differs(b) is True

    def test_true_when_bought_obsolete_state_ids_differ(self):
        a = _pdm(bought_obsolete_state_ids=[1])
        b = _pdm(bought_obsolete_state_ids=[2])
        assert a.sync_scope_differs(b) is True

    def test_true_when_made_replaced_state_ids_differ(self):
        a = _pdm(made_replaced_state_ids=[1])
        b = _pdm(made_replaced_state_ids=[2])
        assert a.sync_scope_differs(b) is True

    def test_true_when_bought_replaced_state_ids_differ(self):
        a = _pdm(bought_replaced_state_ids=[1])
        b = _pdm(bought_replaced_state_ids=[2])
        assert a.sync_scope_differs(b) is True

    def test_false_when_only_non_scope_fields_differ(self):
        a = _pdm()
        b = _pdm(cad_items_read_only=False, poll_interval_minutes=30)
        assert a.sync_scope_differs(b) is False


class TestNormalizedRequiredFields:
    """normalized_required_fields() drops a locked or duplicate name from
    the stored selection silently and raises ValueError for an unknown
    one. See src.modules.external_data.domain.services.pdm_required_fields."""

    def test_empty_selection_stays_empty(self):
        settings = _pdm(required_fields={"made": [], "bought": []})
        assert settings.normalized_required_fields() == {"made": [], "bought": []}

    def test_configured_field_passes_through(self):
        settings = _pdm(required_fields={"made": ["material"], "bought": []})
        assert settings.normalized_required_fields() == {"made": ["material"], "bought": []}

    def test_pseudo_rule_passes_through(self):
        settings = _pdm(required_fields={"made": ["fabrication_step"], "bought": []})
        assert settings.normalized_required_fields() == {
            "made": ["fabrication_step"],
            "bought": [],
        }

    def test_locked_names_are_dropped_silently(self):
        settings = _pdm(
            required_fields={
                "made": ["part_number", "revision", "article_name", "material"],
                "bought": ["order_code_1", "manufacturer_id"],
            }
        )
        assert settings.normalized_required_fields() == {"made": ["material"], "bought": []}

    def test_duplicates_are_dropped_silently(self):
        settings = _pdm(required_fields={"made": ["material", "material"], "bought": []})
        assert settings.normalized_required_fields() == {"made": ["material"], "bought": []}

    def test_order_is_preserved(self):
        settings = _pdm(required_fields={"made": ["fabrication_step", "material"], "bought": []})
        assert settings.normalized_required_fields()["made"] == ["fabrication_step", "material"]

    def test_unknown_name_raises(self):
        settings = _pdm(required_fields={"made": ["not_a_field"], "bought": []})
        with pytest.raises(ValueError):
            settings.normalized_required_fields()

    def test_a_field_not_on_the_other_kind_is_unknown(self):
        """order_code_1 is a bought-only field: naming it for made items is
        rejected the same way an entirely made-up name is."""
        settings = _pdm(required_fields={"made": ["order_code_1"], "bought": []})
        with pytest.raises(ValueError):
            settings.normalized_required_fields()

    def test_missing_kind_key_defaults_to_empty(self):
        settings = _pdm(required_fields={"made": ["material"]})
        assert settings.normalized_required_fields() == {"made": ["material"], "bought": []}

    def test_bought_revision_is_configurable_but_made_revision_is_still_locked(self):
        """revision is data for a bought item, not part of its identity
        (docs/FIELD_OWNERSHIP.md principle 2), so it survives normalization
        for bought while a made item's revision (locked, part of its
        identity) is still dropped silently."""
        settings = _pdm(required_fields={"made": ["revision", "material"], "bought": ["revision"]})
        assert settings.normalized_required_fields() == {
            "made": ["material"],
            "bought": ["revision"],
        }


MADE_DEFAULT = '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
BOUGHT_DEFAULT = (
    '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
)
FEATURE_TREE_MAP = {"feature_tree_representation": "Glados.FeatureTreeRepresentation"}


class TestFeatureTreeTemplateDefaults:
    def test_defaults_match_the_documented_templates(self):
        settings = _pdm()
        assert settings.made_feature_tree_template == MADE_DEFAULT
        assert settings.bought_feature_tree_template == BOUGHT_DEFAULT


class TestAssertFeatureTreeTemplatesValid:
    def test_default_templates_pass(self):
        _pdm(
            made_item_variable_map=FEATURE_TREE_MAP, bought_item_variable_map=FEATURE_TREE_MAP
        ).assert_feature_tree_templates_valid()

    def test_link_to_an_unmapped_property_passes(self):
        settings = _pdm(made_feature_tree_template='$PRP:"SW-File Name"')
        settings.assert_feature_tree_templates_valid()

    def test_made_multi_line_template_raises(self):
        settings = _pdm(made_feature_tree_template='$PRP:"PDM.PartNumber"\n$PRP:"PDM.Revision"')
        with pytest.raises(PdmSettingsInvalidError, match="made feature tree template"):
            settings.assert_feature_tree_templates_valid()

    def test_made_link_to_its_own_mapped_property_raises(self):
        settings = _pdm(
            made_item_variable_map=FEATURE_TREE_MAP,
            made_feature_tree_template='$PRP:"Glados.FeatureTreeRepresentation"',
        )
        with pytest.raises(PdmSettingsInvalidError, match="its own property"):
            settings.assert_feature_tree_templates_valid()

    def test_bought_self_reference_checks_the_bought_mapping(self):
        settings = _pdm(
            made_item_variable_map=FEATURE_TREE_MAP,
            bought_item_variable_map={"feature_tree_representation": "Custom.Tree"},
            bought_feature_tree_template='$PRP:"Glados.FeatureTreeRepresentation"',
        )
        settings.assert_feature_tree_templates_valid()
        settings.bought_feature_tree_template = '$PRP:"Custom.Tree"'
        with pytest.raises(PdmSettingsInvalidError, match="bought feature tree template"):
            settings.assert_feature_tree_templates_valid()
