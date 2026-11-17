"""
Unit tests for src.modules.catalogue.domain.policies.pdm_ownership: pure functions, no
database, no HTTP. Reuses make_made_item/make_bought_item from the item
use-case test modules rather than duplicating entity construction.
"""

import pytest

from src.modules.catalogue.domain.errors import PdmOwnedFieldReadOnlyError
from src.modules.catalogue.domain.policies.pdm_ownership import assert_cad_row_writable
from src.modules.catalogue.domain.policies.pdm_ownership import blocked_pdm_owned_changes
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_owned_fields
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from tests.unit.made_item._helpers import make_made_item
from tests.unit.test_bought_item_use_cases import make_bought_item

# ── pdm_owned_fields ────────────────────────────────────────────────────


class TestPdmOwnedFieldsMade:
    def test_cad_authored_fields_are_owned(self):
        owned = pdm_owned_fields("made")
        for field in ("part_number", "revision", "article_name", "material", "mass", "processes"):
            assert field in owned

    def test_dual_owned_source_item_id_is_not_owned(self):
        # Principle 7: source_item_id is owner "addin_web", not blocked by
        # field-level enforcement: a web edit survives until the CAD value
        # itself changes.
        assert "source_item_id" not in pdm_owned_fields("made")

    def test_status_is_owned(self):
        # Lifecycle status feature: status is driven by PDM's own
        # workflow state, so it is PDM-owned like any other CAD-authored
        # field (docs/PDM_INTEGRATION.md's "lifecycle mapping" section).
        assert "status" in pdm_owned_fields("made")

    def test_web_and_server_fields_are_not_owned(self):
        owned = pdm_owned_fields("made")
        for field in ("successor_item_id", "approver_id", "files", "id", "data_source"):
            assert field not in owned


class TestPdmOwnedFieldsBought:
    def test_cad_authored_fields_are_owned(self):
        owned = pdm_owned_fields("bought")
        for field in ("part_number", "article_name", "order_code_1", "gtin", "manufacturer_id"):
            assert field in owned

    def test_status_is_owned(self):
        assert "status" in pdm_owned_fields("bought")

    def test_web_and_server_fields_are_not_owned(self):
        owned = pdm_owned_fields("bought")
        for field in ("successor_item_id", "approver_id", "files", "id", "data_source"):
            assert field not in owned


# ── blocked_pdm_owned_changes ────────────────────────────────────────────


class TestBlockedPdmOwnedChangesMade:
    def test_no_changes_blocks_nothing(self):
        item = make_made_item(article_name="Bracket")
        blocked = blocked_pdm_owned_changes("made", item, {"article_name": "Bracket"})
        assert blocked == set()

    def test_owned_scalar_change_is_blocked(self):
        item = make_made_item(article_name="Bracket")
        blocked = blocked_pdm_owned_changes("made", item, {"article_name": "Bracket Mk2"})
        assert blocked == {"article_name"}

    def test_status_change_is_blocked(self):
        # Lifecycle status is PDM-owned, so a proposed
        # change to it is blocked the same way any other CAD-authored
        # field's change is.
        item = make_made_item(status=MadeItemCatalogueStatus.ACTIVE)
        blocked = blocked_pdm_owned_changes("made", item, {"status": "inactive"})
        assert blocked == {"status"}

    def test_successor_item_id_change_is_never_blocked(self):
        item = make_made_item()
        item.successor_item_id = None
        blocked = blocked_pdm_owned_changes("made", item, {"successor_item_id": 5})
        assert blocked == set()

    def test_list_field_reordered_is_not_a_change(self):
        item = make_made_item()
        item.article_group_ids = [1, 2, 3]
        blocked = blocked_pdm_owned_changes("made", item, {"article_group_ids": [3, 1, 2]})
        assert blocked == set()

    def test_list_field_with_different_members_is_blocked(self):
        item = make_made_item()
        item.article_group_ids = [1, 2]
        blocked = blocked_pdm_owned_changes("made", item, {"article_group_ids": [1, 3]})
        assert blocked == {"article_group_ids"}

    def test_unowned_field_in_changes_is_ignored(self):
        item = make_made_item()
        blocked = blocked_pdm_owned_changes("made", item, {"nonexistent_field": "x"})
        assert blocked == set()

    def test_part_number_change_is_blocked_renumbering(self):
        item = make_made_item(part_number="SW-001")
        blocked = blocked_pdm_owned_changes("made", item, {"part_number": "SW-002"})
        assert blocked == {"part_number"}

    def test_multiple_changed_fields_all_reported(self):
        item = make_made_item(article_name="Bracket", status=MadeItemCatalogueStatus.ACTIVE)
        item.mass = 100
        changes = {"article_name": "Bracket Mk2", "mass": 150, "status": "inactive"}
        blocked = blocked_pdm_owned_changes("made", item, changes)
        assert blocked == {"article_name", "mass", "status"}


class TestBlockedPdmOwnedChangesBought:
    def test_owned_scalar_change_is_blocked(self):
        item = make_bought_item(article_name="Hex Bolt M8")
        blocked = blocked_pdm_owned_changes("bought", item, {"article_name": "Hex Bolt M10"})
        assert blocked == {"article_name"}

    def test_status_change_is_blocked(self):
        item = make_bought_item(status=BoughtItemCatalogueStatus.ACTIVE)
        blocked = blocked_pdm_owned_changes("bought", item, {"status": "inactive"})
        assert blocked == {"status"}

    def test_successor_item_id_change_is_never_blocked(self):
        item = make_bought_item()
        item.successor_item_id = None
        blocked = blocked_pdm_owned_changes("bought", item, {"successor_item_id": 5})
        assert blocked == set()


# ── assert_cad_row_writable ──────────────────────────────────────────────


class TestAssertCadRowWritable:
    def test_enforce_false_never_raises(self):
        assert_cad_row_writable(enforce=False, item_data_source="CAD", blocked={"article_name"})

    def test_web_row_never_raises_even_with_blocked_fields(self):
        assert_cad_row_writable(enforce=True, item_data_source="WEB", blocked={"article_name"})

    def test_cad_row_with_no_blocked_fields_does_not_raise(self):
        assert_cad_row_writable(enforce=True, item_data_source="CAD", blocked=set())

    def test_cad_row_with_blocked_fields_raises_naming_them(self):
        with pytest.raises(PdmOwnedFieldReadOnlyError) as exc_info:
            assert_cad_row_writable(
                enforce=True, item_data_source="CAD", blocked={"article_name", "mass"}
            )
        message = str(exc_info.value)
        assert "article_name" in message
        assert "mass" in message
