"""
Tests for item field ownership rules and policies: which fields are
web-editable versus PDM-owned, and how revision-copy and web-blocked-change
policies are derived per item kind.
"""

import dataclasses
from datetime import date
from types import SimpleNamespace

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.policies.item_field_ownership import BOUGHT_ITEM_LABEL_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import BOUGHT_ITEM_MAPPABLE_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import FEATURE_TREE_MAPPABLE_FIELD
from src.modules.catalogue.domain.policies.item_field_ownership import MADE_ITEM_LABEL_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import MADE_ITEM_MAPPABLE_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import REVISION_POLICY_FIELDS
from src.modules.catalogue.domain.policies.item_field_ownership import addin_written_fields
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.catalogue.domain.policies.item_field_ownership import web_blocked_changes
from src.modules.catalogue.domain.policies.pdm_ownership import pdm_owned_fields


def _item(**overrides):
    base = dict(
        article_name="Bracket",
        material="1.0037",
        mass=100,
        base_size="10x10x10",
        note="n",
        weblink=None,
        article_group_ids=[1, 2],
        bought_item_id=None,
        source_item_id=None,
        customer_id=None,
        customer_part_number=None,
        customer_revision=None,
        revision_date=date(2026, 1, 1),
        revision_note="initial",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _cmd(**overrides):
    # Same field set as the item fakes above; web_blocked_changes reads
    # both structurally, so a plain SimpleNamespace can stand in for the
    # real UpdateMadeItemCommand.
    return _item(**overrides)


class TestDefaultPolicy:
    def test_covers_every_policy_field_exactly_once(self):
        policy = default_policy()
        assert [p.field for p in policy] == list(REVISION_POLICY_FIELDS)

    def test_web_requires_revision_defaults(self):
        by_field = {p.field: p.web_requires_revision for p in default_policy()}
        assert by_field["article_name"] is True
        assert by_field["material"] is True
        assert by_field["mass"] is True
        assert by_field["base_size"] is True
        assert by_field["bought_item_id"] is True
        assert by_field["source_item_id"] is True
        assert by_field["note"] is False
        assert by_field["weblink"] is False
        assert by_field["article_group_ids"] is False
        assert by_field["revision_date"] is False
        assert by_field["revision_note"] is False
        assert by_field["processes"] is False

    def test_pdm_update_in_place_defaults(self):
        by_field = {p.field: p.pdm_update_in_place for p in default_policy()}
        assert by_field["mass"] is True
        assert by_field["note"] is True
        assert by_field["weblink"] is True
        assert by_field["article_group_ids"] is True
        assert by_field["revision_date"] is True
        assert by_field["revision_note"] is True
        assert by_field["article_name"] is False
        assert by_field["material"] is False
        assert by_field["base_size"] is False
        assert by_field["bought_item_id"] is False
        assert by_field["source_item_id"] is False
        assert by_field["processes"] is False


class TestWebBlockedChanges:
    def test_no_changes_blocks_nothing(self):
        item = _item()
        cmd = _cmd()
        assert web_blocked_changes(item, cmd, default_policy()) == set()

    def test_changing_a_requires_revision_field_is_blocked(self):
        item = _item()
        cmd = _cmd(article_name="Renamed Bracket")
        assert web_blocked_changes(item, cmd, default_policy()) == {"article_name"}

    def test_changing_an_in_place_field_is_not_blocked(self):
        item = _item()
        cmd = _cmd(note="updated note")
        assert web_blocked_changes(item, cmd, default_policy()) == set()

    def test_multiple_blocked_fields(self):
        item = _item()
        cmd = _cmd(material="1.4301", mass=200)
        assert web_blocked_changes(item, cmd, default_policy()) == {"material", "mass"}

    def test_article_group_ids_reorder_is_not_a_change(self):
        item = _item(article_group_ids=[1, 2])
        cmd = _cmd(article_group_ids=[2, 1])
        assert web_blocked_changes(item, cmd, default_policy()) == set()

    def test_article_group_ids_real_change_is_ignored_by_default_policy(self):
        # article_group_ids is web_requires_revision=False by default, so a
        # genuine change still isn't blocked. This only proves the
        # comparison itself (set-based) works when it IS flagged.
        item = _item(article_group_ids=[1, 2])
        cmd = _cmd(article_group_ids=[3])
        custom_policy = [
            p if p.field != "article_group_ids" else type(p)(p.field, True, p.pdm_update_in_place)
            for p in default_policy()
        ]
        assert web_blocked_changes(item, cmd, custom_policy) == {"article_group_ids"}

    def test_processes_never_appears_even_if_flagged(self):
        item = _item()
        cmd = _cmd()
        assert not hasattr(cmd, "processes")
        result = web_blocked_changes(item, cmd, default_policy())
        assert "processes" not in result


class TestItemFields:
    def test_made_item_owners_match_field_ownership_doc(self):
        by_field = {f.field: f for f in item_fields()["made"]}
        assert by_field["part_number"].owner == "pdm"
        assert by_field["revision"].owner == "pdm"
        assert by_field["article_name"].owner == "addin"
        assert by_field["source_item_id"].owner == "addin_web"
        # Lifecycle status feature: status is PDM-owned (driven by
        # workflow state, not a mapped variable); successor_item_id stays
        # web-owned.
        assert by_field["status"].owner == "pdm"
        assert by_field["successor_item_id"].owner == "web"
        assert by_field["id"].owner == "server"
        assert by_field["pdm_sync_state"].owner == "server"

    def test_bought_item_owners_match_field_ownership_doc(self):
        by_field = {f.field: f for f in item_fields()["bought"]}
        assert by_field["gtin"].owner == "addin"
        assert by_field["part_number"].owner == "pdm"
        assert by_field["revision"].owner == "pdm"
        assert by_field["status"].owner == "pdm"
        assert by_field["successor_item_id"].owner == "web"
        assert by_field["id"].owner == "server"

    def test_every_stored_entity_field_has_an_owner(self):
        # Loaded relations are not stored fields; everything else on the
        # entity must appear in the table, so a new column cannot slip
        # past the admin Item Fields tab or the PDM ownership guard.
        relations = {
            "made": {"article_groups", "bought_item", "source_item", "creator", "changed_by"},
            "bought": {"article_groups", "creator", "changed_by", "product_family"},
        }
        for kind, entity in (("made", MadeItem), ("bought", BoughtItem)):
            stored = {f.name for f in dataclasses.fields(entity)} - relations[kind]
            owned = {f.field for f in item_fields()[kind]}
            assert stored - owned == set(), kind

    def test_bought_item_portal_and_family_fields_are_not_pdm_owned(self):
        by_field = {f.field: f for f in item_fields()["bought"]}
        assert by_field["product_family_id"].owner == "web"
        # Dual-owned: set in the web and from the CAD file, see principle 7.
        assert by_field["edp_part_id"].owner == "addin_web"
        assert by_field["edp_part_id"].mappable is True
        assert by_field["pdm_edp_part_id"].owner == "server"
        assert by_field["pdm_edp_part_id"].mappable is False
        assert by_field["edp_synced_at"].owner == "server"
        assert "edp_part_id" not in pdm_owned_fields("bought")

    def test_mappable_matches_d22_lists(self):
        made = {f.field: f.mappable for f in item_fields()["made"]}
        assert made["part_number"] is True
        assert made["processes"] is True
        assert made["status"] is False
        assert set(f for f, m in made.items() if m) == set(MADE_ITEM_MAPPABLE_FIELDS)

        bought = {f.field: f.mappable for f in item_fields()["bought"]}
        assert bought["gtin"] is True
        assert bought["status"] is False
        assert set(f for f, m in bought.items() if m) == set(BOUGHT_ITEM_MAPPABLE_FIELDS)

    def test_policy_applicable_only_for_made_items(self):
        made = {f.field: f.policy_applicable for f in item_fields()["made"]}
        assert made["article_name"] is True
        assert made["processes"] is True
        assert made["part_number"] is False

        bought = item_fields()["bought"]
        assert all(f.policy_applicable is False for f in bought)

    def test_label_fields_are_addin_owned_mappable_and_not_policy_applicable(self):
        made = {f.field: f for f in item_fields()["made"]}
        for spec in MADE_ITEM_LABEL_FIELDS:
            row = made[spec.field]
            assert row.owner == "addin"
            assert row.mappable is True
            assert row.policy_applicable is False
            assert row.label_of == spec.source_field

        bought = {f.field: f for f in item_fields()["bought"]}
        for spec in BOUGHT_ITEM_LABEL_FIELDS:
            row = bought[spec.field]
            assert row.owner == "addin"
            assert row.mappable is True
            assert row.policy_applicable is False
            assert row.label_of == spec.source_field

    def test_non_label_fields_report_no_label_of(self):
        made = {f.field: f for f in item_fields()["made"]}
        assert made["article_name"].label_of is None
        assert made["article_group_ids"].label_of is None
        assert made[FEATURE_TREE_MAPPABLE_FIELD].label_of is None

        bought = {f.field: f for f in item_fields()["bought"]}
        assert bought["manufacturer_id"].label_of is None
        assert bought[FEATURE_TREE_MAPPABLE_FIELD].label_of is None

    def test_feature_tree_field_is_addin_owned_and_mappable_for_both_kinds(self):
        made = {f.field: f for f in item_fields()["made"]}
        bought = {f.field: f for f in item_fields()["bought"]}
        for row in (made[FEATURE_TREE_MAPPABLE_FIELD], bought[FEATURE_TREE_MAPPABLE_FIELD]):
            assert row.owner == "addin"
            assert row.mappable is True
            assert row.policy_applicable is False


class TestAddinWrittenFields:
    def test_made_includes_its_labels_and_the_feature_tree_field(self):
        result = addin_written_fields("made")
        assert result == {
            "article_group_names",
            "process_names",
            "source_item_name",
            "customer_name",
            FEATURE_TREE_MAPPABLE_FIELD,
        }

    def test_bought_includes_its_labels_and_the_feature_tree_field(self):
        result = addin_written_fields("bought")
        assert result == {
            "manufacturer_name",
            "article_group_names",
            FEATURE_TREE_MAPPABLE_FIELD,
        }
