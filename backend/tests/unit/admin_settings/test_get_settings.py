"""
Unit tests for the read-side admin settings use cases:
TestGetAllAdminSettings, TestGetAdminSettingsAudit, TestGetPdmSettings and
TestGetFieldMapping. No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.external_data.application.use_cases.admin_settings.get_field_mapping import (
    GetFieldMapping,
)
from src.modules.external_data.application.use_cases.admin_settings.get_pdm_settings import (
    GetPdmSettings,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.platform.application.use_cases.admin_settings.get_admin_settings import (
    GetAdminSettingsAudit,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.read.application.use_cases.admin_settings.get_all_admin_settings import GetAllAdminSettings
from src.read.ports.outbound.repositories.admin_settings_repository import (
    AdminSettingsAuditFilterDto,
)
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.admin_settings.fakes import FakePdmFileSnapshotRepository


class TestGetAllAdminSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])
        self.use_case = GetAllAdminSettings(self.repo, domain="example.com")

    async def test_pdm_section_carries_the_deployment_switch_for_mutating_operations(self):
        allowed = GetAllAdminSettings(
            self.repo, domain="example.com", pdm_mutating_operations_enabled=True
        )

        assert (await allowed.execute(actor=self.actor)).pdm.mutating_operations_enabled is True
        assert (
            await self.use_case.execute(actor=self.actor)
        ).pdm.mutating_operations_enabled is False

    async def test_returns_all_domains(self):
        result = await self.use_case.execute(actor=self.actor)
        assert result.host.domain == "example.com"
        assert result.features.enable_email_notifications is True
        assert result.storage.provider == "local"
        assert result.auth.ldap_enabled is False
        assert result.auth.ldap_port == 636

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor)


class TestGetAdminSettingsAudit:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])

    async def test_returns_appended_entries(self):
        await self.repo.append_audit(
            AdminSettingsAuditEntry(
                id=0,
                changed_at=datetime.now(UTC),
                changed_by_id=1,
                changed_by_username="testuser",
                settings_domain="host",
                summary="Host settings updated.",
            )
        )
        total, entries = await GetAdminSettingsAudit(self.repo).execute(
            actor=self.actor, filters=AdminSettingsAuditFilterDto()
        )
        assert total == 1
        assert entries[0].settings_domain == "host"

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await GetAdminSettingsAudit(self.repo).execute(
                actor=actor, filters=AdminSettingsAuditFilterDto()
            )


class TestGetPdmSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.snapshot_repo = FakePdmFileSnapshotRepository()
        self.actor = make_user(permissions=[Permission.READ_SETTINGS])
        self.use_case = GetPdmSettings(self.repo, self.snapshot_repo)

    async def test_mutating_operations_are_off_unless_the_deployment_allows_them(self):
        assert (await self.use_case.execute(actor=self.actor)).mutating_operations_enabled is False

        allowed = GetPdmSettings(self.repo, self.snapshot_repo, mutating_operations_enabled=True)
        assert (await allowed.execute(actor=self.actor)).mutating_operations_enabled is True

    async def test_returns_settings_and_item_fields(self):
        result = await self.use_case.execute(actor=self.actor)
        assert result.made_item_variable_map == self.repo.pdm.made_item_variable_map
        made_fields = {f.field for f in result.item_fields.made}
        bought_fields = {f.field for f in result.item_fields.bought}
        assert "part_number" in made_fields
        assert "gtin" in bought_fields

    async def test_returns_the_stored_required_field_selection(self):
        self.repo.pdm.required_fields = {"made": ["material"], "bought": []}
        result = await self.use_case.execute(actor=self.actor)
        assert result.required_fields == {"made": ["material"], "bought": []}

    async def test_locked_required_fields_are_always_served(self):
        # revision is locked for made items (identity) but not for bought
        # ones (data, not identity, per docs/FIELD_OWNERSHIP.md principle 2).
        result = await self.use_case.execute(actor=self.actor)
        assert result.locked_required_fields == {
            "made": ["part_number", "revision", "article_name"],
            "bought": ["part_number", "article_name", "order_code_1", "manufacturer_id"],
        }

    async def test_required_field_rules_are_always_served(self):
        result = await self.use_case.execute(actor=self.actor)
        assert result.required_field_rules == {"made": ["fabrication_step"], "bought": []}

    async def test_snapshot_counts_empty_when_vault_id_unresolved(self):
        result = await self.use_case.execute(actor=self.actor)
        assert result.snapshot_counts == {}
        assert self.snapshot_repo.counts_by_state_calls == []

    async def test_snapshot_counts_populated_once_vault_id_is_known(self):
        self.repo.pdm.vault_id = "a1b2c3d4-0000-0000-0000-000000000000"
        self.snapshot_repo.counts = {"ingested": 3, "conflict": 1}

        result = await self.use_case.execute(actor=self.actor)

        assert result.snapshot_counts == {"ingested": 3, "conflict": 1}
        assert self.snapshot_repo.counts_by_state_calls == ["a1b2c3d4-0000-0000-0000-000000000000"]

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor)


class TestGetFieldMapping:
    """GET /pat/settings/field-mapping's use case (no actor, no permission
    check: see the module docstring). FakeAdminSettingsRepository's own
    default `.pdm` only maps part_number/revision, so most fields already
    exercise the "unmapped -> null" path without extra setup."""

    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.use_case = GetFieldMapping(self.repo)

    async def test_served_fields_and_order_match_the_wire_contract(self):
        result = await self.use_case.execute()
        assert [e.field for e in result.made_items] == [
            "part_number",
            "revision",
            "revision_date",
            "revision_note",
            "article_name",
            "material",
            "mass",
            "base_size",
            "note",
            "weblink",
            "article_group_ids",
            "bought_item_id",
            "source_item_id",
            "processes",
            "status",
            "successor_item_id",
            "approver_id",
            "files",
            "data_source",
            "kind",
            "glados_ids",
            "newest_revision_sync_state",
            "newest_revision_synced_at",
            "article_group_names",
            "process_names",
            "source_item_name",
            "feature_tree_representation",
            "customer_id",
            "customer_part_number",
            "customer_revision",
            "customer_name",
        ]
        assert [e.field for e in result.bought_items] == [
            "part_number",
            "revision",
            "article_name",
            "order_code_1",
            "order_code_2",
            "gtin",
            "ean",
            "tariff_number",
            "mass",
            "note",
            "weblink",
            "manufacturer_id",
            "article_group_ids",
            "status",
            "successor_item_id",
            "approver_id",
            "files",
            "data_source",
            "kind",
            "glados_ids",
            "newest_revision_sync_state",
            "newest_revision_synced_at",
            "manufacturer_name",
            "article_group_names",
            "feature_tree_representation",
            "edp_part_id",
        ]

    async def test_owners_come_from_item_field_ownership(self):
        result = await self.use_case.execute()
        made = {e.field: e.owner for e in result.made_items}
        bought = {e.field: e.owner for e in result.bought_items}
        assert made["part_number"] == "pdm"
        assert made["article_name"] == "addin"
        assert made["source_item_id"] == "addin_web"
        # Lifecycle status feature: status is PDM-owned (driven by
        # workflow state, not a mapped variable), successor_item_id
        # stays web-owned, see item_field_ownership.py's matching
        # comment.
        assert made["status"] == "pdm"
        assert made["successor_item_id"] == "web"
        assert made["data_source"] == "server"
        assert bought["gtin"] == "addin"
        assert bought["part_number"] == "pdm"
        assert made["kind"] == "addin"
        assert bought["kind"] == "addin"

    async def test_label_of_names_the_source_field(self):
        result = await self.use_case.execute()
        made = {e.field: e.label_of for e in result.made_items}
        bought = {e.field: e.label_of for e in result.bought_items}
        assert made["article_group_names"] == "article_group_ids"
        assert made["process_names"] == "processes"
        assert made["source_item_name"] == "source_item_id"
        assert made["feature_tree_representation"] is None
        assert made["article_name"] is None
        assert bought["manufacturer_name"] == "manufacturer_id"
        assert bought["article_group_names"] == "article_group_ids"
        assert bought["feature_tree_representation"] is None

    async def test_templates_come_from_the_stored_settings(self):
        self.repo.pdm.made_feature_tree_template = '$PRP:"Glados.ArticleName"'
        self.repo.pdm.bought_feature_tree_template = '$PRP:"Glados.ArticleName" (x)'
        result = await self.use_case.execute()
        assert result.templates.made == '$PRP:"Glados.ArticleName"'
        assert result.templates.bought == '$PRP:"Glados.ArticleName" (x)'

    async def test_configured_variable_map_is_reflected(self):
        self.repo.pdm = AdminPdmSettings(
            id=1,
            made_item_variable_map={
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
                "article_name": "Glados.ArticleName",
            },
            bought_item_variable_map={"gtin": "Glados.Gtin"},
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
        result = await self.use_case.execute()
        made = {e.field: e.custom_property for e in result.made_items}
        bought = {e.field: e.custom_property for e in result.bought_items}
        assert made["article_name"] == "Glados.ArticleName"
        assert bought["gtin"] == "Glados.Gtin"

    async def test_unmapped_field_is_null(self):
        result = await self.use_case.execute()
        made = {e.field: e.custom_property for e in result.made_items}
        # FakeAdminSettingsRepository's default pdm map has no "material" key at all.
        assert made["material"] is None

    async def test_empty_string_mapping_is_treated_as_unmapped(self):
        self.repo.pdm = AdminPdmSettings(
            id=1,
            made_item_variable_map={
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
                "note": "",
            },
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
        result = await self.use_case.execute()
        made = {e.field: e.custom_property for e in result.made_items}
        assert made["note"] is None

    async def test_update_in_place_from_revision_policy_default(self):
        result = await self.use_case.execute()
        made = {e.field: e.update_in_place for e in result.made_items}
        # default_policy(): mass is "update in place", article_name is not;
        # non-policy fields (identity, web, server) are always null.
        assert made["mass"] is True
        assert made["article_name"] is False
        assert made["part_number"] is None
        assert made["status"] is None
        assert made["data_source"] is None

    async def test_bought_items_update_in_place_always_null(self):
        result = await self.use_case.execute()
        assert all(e.update_in_place is None for e in result.bought_items)

    async def test_locked_fields_are_always_required(self):
        result = await self.use_case.execute()
        made = {e.field: e.required for e in result.made_items}
        bought = {e.field: e.required for e in result.bought_items}
        assert made["part_number"] is True
        assert made["revision"] is True
        assert made["article_name"] is True
        assert bought["order_code_1"] is True
        assert bought["manufacturer_id"] is True
        # Not locked, and nothing configured by FakeAdminSettingsRepository's default.
        assert made["material"] is False
        assert bought["gtin"] is False

    async def test_configured_field_is_reported_required(self):
        self.repo.pdm.required_fields = {"made": ["material"], "bought": []}
        result = await self.use_case.execute()
        made = {e.field: e.required for e in result.made_items}
        assert made["material"] is True

    async def test_bought_revision_is_configurable_not_locked(self):
        """Unlike made items, a bought item's revision is not part of
        LOCKED_REQUIRED_FIELDS (docs/FIELD_OWNERSHIP.md principle 2), so
        `required` for it follows required_fields["bought"] the same way
        "material" does for made above, rather than being always true."""
        result = await self.use_case.execute()
        bought = {e.field: e.required for e in result.bought_items}
        assert bought["revision"] is False  # nothing configured by the fake's default

        self.repo.pdm.required_fields = {"made": [], "bought": ["revision"]}
        result = await self.use_case.execute()
        bought = {e.field: e.required for e in result.bought_items}
        assert bought["revision"] is True

    async def test_rules_report_configured_state(self):
        result = await self.use_case.execute()
        made_rules = {r.name: r.required for r in result.rules["made"]}
        assert made_rules == {"fabrication_step": False}
        assert result.rules["bought"] == []

        self.repo.pdm.required_fields = {"made": ["fabrication_step"], "bought": []}
        result = await self.use_case.execute()
        made_rules = {r.name: r.required for r in result.rules["made"]}
        assert made_rules == {"fabrication_step": True}
