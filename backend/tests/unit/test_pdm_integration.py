"""
Unit tests for is_pdm_enabled(), assert_part_number_not_pdm_reserved()
and is_private_state(). No database, no HTTP.
"""

import pytest

from src.modules.catalogue.domain.errors import PartNumberReservedForPdmError
from src.modules.catalogue.domain.policies.pdm_ownership import assert_part_number_not_pdm_reserved
from src.modules.external_data.application.services.pdm_integration import is_pdm_enabled
from src.modules.external_data.application.services.pdm_integration import is_private_state
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmObjectInfo


def make_pdm_settings(**overrides: object) -> AdminPdmSettings:
    defaults: dict[str, object] = {
        "id": 1,
        "made_item_variable_map": {},
        "bought_item_variable_map": {},
        "enabled": False,
        "base_url": "http://pdm-host:65453",
        "vault_name": "MyVault",
        "username": "svc-account",
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


class TestIsPdmEnabled:
    def test_false_when_toggle_off_even_if_configured(self):
        assert is_pdm_enabled(make_pdm_settings(enabled=False)) is False

    def test_false_when_toggle_on_but_not_configured(self):
        assert is_pdm_enabled(make_pdm_settings(enabled=True, base_url="")) is False

    def test_true_when_toggle_on_and_configured(self):
        assert is_pdm_enabled(make_pdm_settings(enabled=True)) is True


class TestAssertPartNumberNotPdmReserved:
    def test_no_op_when_disabled(self):
        assert_part_number_not_pdm_reserved("EXT-1", r"EXT-\d+", enabled=False)

    def test_no_op_when_pattern_blank(self):
        assert_part_number_not_pdm_reserved("EXT-1", "", enabled=True)

    def test_no_op_when_number_does_not_match_pattern(self):
        assert_part_number_not_pdm_reserved("INT-1", r"EXT-\d+", enabled=True)

    def test_raises_when_enabled_and_pattern_matches(self):
        with pytest.raises(PartNumberReservedForPdmError):
            assert_part_number_not_pdm_reserved("EXT-1", r"EXT-\d+", enabled=True)


def make_object(*, state: str = "Released", state_id: int = 10) -> PdmObjectInfo:
    return PdmObjectInfo(
        id=1,
        name="part.sldprt",
        size=0,
        modified_at=None,
        version=1,
        state=state,
        state_id=state_id,
        parent_folder_id=1,
        path="\\Made-Parts\\part.sldprt",
        object_type=1,
        is_locked=False,
        locked_by=0,
        is_shared=False,
        is_toolbox=False,
        is_deleted=False,
    )


class TestIsPrivateState:
    def test_true_for_empty_state_name_with_the_vault_private_state_id(self):
        # Observed on a live vault: private-state files carry an empty
        # name and a real, non-zero state id.
        assert is_private_state(make_object(state="", state_id=89)) is True

    def test_true_for_empty_state_name_with_zero_state_id(self):
        assert is_private_state(make_object(state="", state_id=0)) is True

    def test_false_for_a_real_workflow_state(self):
        assert is_private_state(make_object(state="Released", state_id=10)) is False

    def test_false_when_only_the_id_is_zero(self):
        assert is_private_state(make_object(state="Work in progress", state_id=0)) is False
