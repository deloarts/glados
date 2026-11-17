"""
Unit tests for TestUpdatePdmSettings. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime
from typing import ClassVar

import pytest

from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.external_data.application.dto.admin_settings_dto.pdm import PdmWatchedFolderCommand
from src.modules.external_data.application.dto.admin_settings_dto.pdm import PdmWatchedFolderResult
from src.modules.external_data.application.dto.admin_settings_dto.pdm import (
    UpdatePdmSettingsCommand,
)
from src.modules.external_data.application.use_cases.admin_settings.update_pdm_settings import (
    UpdatePdmSettings,
)
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.errors import PdmSettingsInvalidError
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.external_data.domain.value_objects.pdm_watched_folder import PdmWatchedFolder
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.admin_settings.fakes import FakePdmFileSnapshotRepository
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.ingest_pdm_file._helpers import make_bought_item
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file.fakes import FakeBoughtItemRepository
from tests.unit.ingest_pdm_file.fakes import FakeMadeItemRepository


def _complete(kind: str, mapped: dict[str, str]) -> dict[str, str]:
    """`mapped` with every other mappable field of `kind` left unmapped,
    the complete map an update must send."""
    return {f.field: "" for f in item_fields()[kind] if f.mappable} | mapped


def _snapshot(
    *,
    file_id: int,
    path: str,
    kind: str | None = None,
    item_id: int | None = None,
    sync_state: PdmFileSyncState = PdmFileSyncState.SKIPPED,
    last_error: str | None = None,
) -> PdmFileSnapshot:
    now = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
    return PdmFileSnapshot(
        id=file_id,
        vault_id="V1",
        file_id=file_id,
        kind=kind,
        name=path.rsplit("\\", 1)[-1],
        path=path,
        parent_folder_id=1,
        version=1,
        state_id=1,
        state="Released",
        modified_at=None,
        first_seen_at=now,
        last_seen_at=now,
        last_ingested_version=None,
        sync_state=sync_state,
        last_error=last_error,
        part_number=None,
        revision=None,
        item_id=item_id,
        parked_payload=None,
    )


class TestUpdatePdmSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.snapshots = FakePdmFileSnapshotRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdatePdmSettings(
            self.repo, snapshot_repo=self.snapshots, uow=FakeUnitOfWork()
        )

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "article_name": "Glados.ArticleName",
                    },
                )
            ),
        )
        assert result.made_item_variable_map["article_name"] == "Glados.ArticleName"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdatePdmSettingsCommand())

    async def test_partial_update_preserves_bought_item_variable_map(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                    },
                )
            ),
        )
        assert result.bought_item_variable_map == self.repo.pdm.bought_item_variable_map

    async def test_unknown_made_item_field_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(made_item_variable_map={"not_a_field": "X"}),
            )

    async def test_unknown_bought_item_field_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(bought_item_variable_map={"not_a_field": "X"}),
            )

    async def test_variable_map_missing_a_mappable_field_rejected(self):
        with pytest.raises(
            PdmSettingsInvalidError, match=r"Missing made item field\(s\).*'article_name'"
        ):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map={
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                    }
                ),
            )

    async def test_duplicate_variable_name_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "article_name": "PDM.Revision",
                        },
                    )
                ),
            )

    async def test_blank_variable_names_do_not_collide(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "note": "",
                        "weblink": "",
                    },
                )
            ),
        )
        assert result.made_item_variable_map["note"] == ""
        assert result.made_item_variable_map["weblink"] == ""

    async def test_label_field_can_be_mapped_like_any_other_field(self):
        # A label is a normal mappable field, with no special derivation
        # or collision rule of its own, see item_field_ownership.
        # MADE_ITEM_LABEL_FIELDS/BOUGHT_ITEM_LABEL_FIELDS.
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                bought_item_variable_map=_complete(
                    "bought",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "manufacturer_id": "Glados.ManufacturerId",
                        "manufacturer_name": "Vault.Manufacturer",
                    },
                )
            ),
        )
        assert result.bought_item_variable_map["manufacturer_name"] == "Vault.Manufacturer"

    async def test_label_field_colliding_with_another_field_is_rejected(self):
        # A label field's own custom property is just another map value;
        # the plain duplicate-value check catches it colliding with
        # article_name's, the same as any other two fields would.
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    bought_item_variable_map=_complete(
                        "bought",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "manufacturer_id": "Glados.ManufacturerId",
                            "manufacturer_name": "Glados.ManufacturerName",
                            "article_name": "Glados.ManufacturerName",
                        },
                    )
                ),
            )

    async def test_label_field_colliding_on_made_items_is_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "processes": "Glados.Processes",
                            "process_names": "Glados.ProcessNames",
                            "article_name": "Glados.ProcessNames",
                        },
                    )
                ),
            )

    async def test_feature_tree_field_can_be_mapped(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "feature_tree_representation": "Glados.FeatureTreeRepresentation",
                    },
                )
            ),
        )
        assert (
            result.made_item_variable_map["feature_tree_representation"]
            == "Glados.FeatureTreeRepresentation"
        )

    async def test_compiled_in_default_variable_maps_pass_validation(self):
        """The shipped defaults (admin_settings_model.py's
        _MADE_ITEM_VARIABLE_MAP_DEFAULT/_BOUGHT_ITEM_VARIABLE_MAP_DEFAULT)
        never collide with each other, labels included."""
        made_defaults = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            "revision_date": "PDM.RevisionDate",
            "revision_note": "PDM.RevisionNote",
            "article_name": "Glados.ArticleName",
            "material": "Glados.Material",
            "mass": "Glados.Mass",
            "base_size": "Glados.BaseSize",
            "note": "Glados.Note",
            "weblink": "Glados.Weblink",
            "article_group_ids": "Glados.ArticleGroupIds",
            "bought_item_id": "Glados.BoughtItemId",
            "source_item_id": "Glados.SourceItemId",
            "processes": "Glados.Processes",
            "article_group_names": "Glados.ArticleGroupNames",
            "process_names": "Glados.ProcessNames",
            "source_item_name": "Glados.SourceItemName",
            "customer_id": "Glados.CustomerId",
            "customer_name": "Glados.CustomerName",
            "customer_part_number": "Glados.CustomerPartNumber",
            "customer_revision": "Glados.CustomerRevision",
            "feature_tree_representation": "Glados.FeatureTreeRepresentation",
            "kind": "Glados.Kind",
            "glados_ids": "Glados.Ids",
            "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
            "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
        }
        bought_defaults = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            "article_name": "Glados.ArticleName",
            "order_code_1": "Glados.OrderCode1",
            "order_code_2": "Glados.OrderCode2",
            "gtin": "Glados.Gtin",
            "ean": "Glados.Ean",
            "tariff_number": "Glados.TariffNumber",
            "mass": "Glados.Mass",
            "note": "Glados.Note",
            "weblink": "Glados.Weblink",
            "manufacturer_id": "Glados.ManufacturerId",
            "article_group_ids": "Glados.ArticleGroupIds",
            "edp_part_id": "Glados.EdpPartId",
            "manufacturer_name": "Glados.ManufacturerName",
            "article_group_names": "Glados.ArticleGroupNames",
            "feature_tree_representation": "Glados.FeatureTreeRepresentation",
            "kind": "Glados.Kind",
            "glados_ids": "Glados.Ids",
            "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
            "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
        }

        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=made_defaults,
                bought_item_variable_map=bought_defaults,
            ),
        )

        assert result.made_item_variable_map == made_defaults
        assert result.bought_item_variable_map == bought_defaults

    async def test_missing_part_number_mapping_rejected_when_other_field_mapped(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "revision": "PDM.Revision",
                            "article_name": "Glados.ArticleName",
                        },
                    )
                ),
            )

    async def test_missing_revision_mapping_rejected_when_other_field_mapped(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "part_number": "PDM.PartNumber",
                            "article_name": "Glados.ArticleName",
                        },
                    )
                ),
            )

    async def test_empty_map_without_identity_is_allowed(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(bought_item_variable_map=_complete("bought", {})),
        )
        assert result.bought_item_variable_map == _complete("bought", {})

    # ── kind (docs/FIELD_OWNERSHIP.md, principle 1) ────────────

    async def test_kind_unmapped_in_both_maps_is_allowed(self):
        """kind has no forced default written back: a settings save that
        leaves it blank in both maps stores it unmapped, same as any other
        field."""
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                    },
                ),
                bought_item_variable_map=_complete(
                    "bought",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                    },
                ),
            ),
        )
        assert result.made_item_variable_map["kind"] == ""
        assert result.bought_item_variable_map["kind"] == ""

    async def test_kind_set_on_only_one_map_is_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "kind": "Glados.Kind",
                        },
                    ),
                    bought_item_variable_map=_complete(
                        "bought",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                        },
                    ),
                ),
            )

    async def test_kind_disagreeing_between_maps_is_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "kind": "Glados.Kind",
                        },
                    ),
                    bought_item_variable_map=_complete(
                        "bought",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "kind": "Other.Kind",
                        },
                    ),
                ),
            )

    async def test_kind_agreeing_between_maps_is_accepted(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "kind": "Custom.Kind",
                    },
                ),
                bought_item_variable_map=_complete(
                    "bought",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "kind": "Custom.Kind",
                    },
                ),
            ),
        )
        assert result.made_item_variable_map["kind"] == "Custom.Kind"
        assert result.bought_item_variable_map["kind"] == "Custom.Kind"

    async def test_kind_left_as_stored_when_neither_map_is_sent(self):
        """Partial update: sending neither variable map keeps whatever
        kind mapping (if any) was already stored, same as every other
        field on an omitted map."""
        self.repo.pdm.made_item_variable_map = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            "kind": "Glados.Kind",
        }
        self.repo.pdm.bought_item_variable_map = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            "kind": "Glados.Kind",
        }

        result = await self.use_case.execute(actor=self.actor, cmd=UpdatePdmSettingsCommand())

        assert result.made_item_variable_map["kind"] == "Glados.Kind"
        assert result.bought_item_variable_map["kind"] == "Glados.Kind"

    # ── connection fields ────────────────────────────────────────────

    async def test_unset_connection_fields_are_preserved(self):
        self.repo.pdm.base_url = "https://pdm.example.com"
        self.repo.pdm.vault_name = "MainVault"
        self.repo.pdm.username = "svc-account"
        self.repo.pdm.password = "s3cret"

        result = await self.use_case.execute(actor=self.actor, cmd=UpdatePdmSettingsCommand())

        assert result.base_url == "https://pdm.example.com"
        assert result.vault_name == "MainVault"
        assert result.username == "svc-account"
        assert result.password_configured is True

    async def test_vault_name_and_username_are_stripped(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(vault_name="  MainVault  ", username="  svc  "),
        )
        assert result.vault_name == "MainVault"
        assert result.username == "svc"

    async def test_base_url_requires_http_scheme(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(base_url="ftp://pdm.example.com")
            )

    async def test_base_url_trailing_slash_is_stripped(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(base_url="http://pdm.example.com:65453/"),
        )
        assert result.base_url == "http://pdm.example.com:65453"

    async def test_base_url_can_be_cleared(self):
        self.repo.pdm.base_url = "http://pdm.example.com"
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(base_url="")
        )
        assert result.base_url == ""

    def test_timeout_seconds_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(timeout_seconds=0)
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(timeout_seconds=301)

    async def test_password_none_keeps_existing_password(self):
        self.repo.pdm.password = "original"
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(vault_name="Renamed")
        )
        assert result.password_configured is True
        assert self.repo.pdm.password == "original"

    async def test_password_can_be_replaced(self):
        self.repo.pdm.password = "original"
        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(password="new-pass")
        )
        assert self.repo.pdm.password == "new-pass"

    async def test_enabled_toggle_is_merged(self):
        # enabled=True requires a configured connection, an enabled
        # watched folder, and a released state. See the tests below for
        # each rule rejected on its own.
        self.repo.pdm.base_url = "http://host:65453"
        self.repo.pdm.vault_name = "Vault"
        self.repo.pdm.username = "svc"
        self.repo.pdm.password = "secret"
        self.repo.pdm.watched_folders = [
            PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
        ]
        self.repo.pdm.made_released_state_ids = [5]

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=True)
        )

        assert result.enabled is True

    async def test_enabling_without_configured_connection_rejected(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=True)
            )

    async def test_enabling_without_an_enabled_watched_folder_rejected(self):
        self.repo.pdm.base_url = "http://host:65453"
        self.repo.pdm.vault_name = "Vault"
        self.repo.pdm.username = "svc"
        self.repo.pdm.password = "secret"
        self.repo.pdm.made_released_state_ids = [5]
        self.repo.pdm.watched_folders = [
            PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=False)
        ]

        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=True)
            )

    async def test_enabling_without_a_released_state_rejected(self):
        self.repo.pdm.base_url = "http://host:65453"
        self.repo.pdm.vault_name = "Vault"
        self.repo.pdm.username = "svc"
        self.repo.pdm.password = "secret"
        self.repo.pdm.watched_folders = [
            PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
        ]

        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=True)
            )

    def _ready_with_documents_folder(self) -> None:
        self.repo.pdm.base_url = "http://host:65453"
        self.repo.pdm.vault_name = "Vault"
        self.repo.pdm.username = "svc"
        self.repo.pdm.password = "secret"
        self.repo.pdm.made_released_state_ids = [5]
        self.repo.pdm.watched_folders = [
            PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True),
            PdmWatchedFolder(
                path="\\Export",
                kind="documents",
                recursive=True,
                enabled=True,
                match_by="datacard",
            ),
        ]

    async def test_enabled_documents_folder_without_a_document_state_rejected(self):
        self._ready_with_documents_folder()

        with pytest.raises(PdmSettingsInvalidError, match="exported documents"):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=True)
            )

    async def test_enabled_documents_folder_with_a_document_state_accepted(self):
        self._ready_with_documents_folder()

        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(enabled=True, document_released_state_ids=[7]),
        )

        assert result.document_released_state_ids == [7]

    async def test_changed_document_states_requeue_skipped_files(self):
        self.repo.pdm.vault_id = "V1"

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(document_released_state_ids=[7])
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_changed_document_excluded_kinds_requeue_skipped_files(self):
        self.repo.pdm.vault_id = "V1"

        await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(document_excluded_kinds={"pdf": ["bought"]}),
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_disabling_does_not_require_configuration(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=False)
        )
        assert result.enabled is False

    async def test_made_released_and_obsolete_state_ids_must_be_disjoint(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_released_state_ids=[5, 9], made_obsolete_state_ids=[9]
                ),
            )

    async def test_bought_released_and_obsolete_state_ids_must_be_disjoint(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    bought_released_state_ids=[5, 9], bought_obsolete_state_ids=[9]
                ),
            )

    async def test_same_state_id_may_be_released_for_one_kind_and_obsolete_for_the_other(self):
        # Disjointness is checked per kind only: made and bought need not
        # agree on what a given state id means.
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_released_state_ids=[9], bought_obsolete_state_ids=[9]
            ),
        )
        assert result.made_released_state_ids == [9]
        assert result.bought_obsolete_state_ids == [9]

    async def test_disjointness_resolves_against_the_stored_side_when_only_one_is_sent(self):
        self.repo.pdm.made_obsolete_state_ids = [9]
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(made_released_state_ids=[9])
            )

    async def test_watched_folders_are_stored_and_returned(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Made-Parts", kind="made", recursive=True, enabled=True
                    )
                ]
            ),
        )
        assert result.watched_folders == [
            PdmWatchedFolderResult(
                path="\\Made-Parts",
                kind="made",
                recursive=True,
                enabled=True,
                match_by=None,
                filename_pattern=None,
                folder_id=None,
            )
        ]

    def test_poll_interval_minutes_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(poll_interval_minutes=0)
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(poll_interval_minutes=1441)

    def test_cold_folder_max_multiplier_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(cold_folder_max_multiplier=0)
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(cold_folder_max_multiplier=65)

    async def test_cold_folder_max_multiplier_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(cold_folder_max_multiplier=16)
        )
        assert result.cold_folder_max_multiplier == 16

    async def test_cold_folder_max_multiplier_defaults_to_the_stored_value_when_omitted(self):
        result = await self.use_case.execute(actor=self.actor, cmd=UpdatePdmSettingsCommand())
        assert result.cold_folder_max_multiplier == self.repo.pdm.cold_folder_max_multiplier

    async def test_cad_items_read_only_is_merged(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(cad_items_read_only=False)
        )
        assert result.cad_items_read_only is False

    async def test_changing_base_url_clears_the_stored_session(self):
        self.repo.pdm.base_url = "http://old-host:65453"
        self.repo.pdm.session_token = "token-123"
        self.repo.pdm.session_user_id = 5
        self.repo.pdm.session_obtained_at = datetime.now(UTC)

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(base_url="http://new-host:65453")
        )

        assert result.session.active is False
        assert self.repo.pdm.session_token is None
        assert self.repo.pdm.session_user_id is None
        assert self.repo.pdm.session_obtained_at is None

    async def test_changing_password_clears_the_stored_session(self):
        self.repo.pdm.password = "original"
        self.repo.pdm.session_token = "token-123"
        self.repo.pdm.session_obtained_at = datetime.now(UTC)

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(password="changed")
        )

        assert self.repo.pdm.session_token is None

    async def test_unrelated_update_preserves_the_stored_session(self):
        self.repo.pdm.base_url = "http://host:65453"
        self.repo.pdm.vault_name = "Vault"
        self.repo.pdm.username = "svc"
        self.repo.pdm.password = "secret"
        self.repo.pdm.watched_folders = [
            PdmWatchedFolder(path="\\Made-Parts", kind="made", recursive=True, enabled=True)
        ]
        self.repo.pdm.made_released_state_ids = [5]
        self.repo.pdm.session_token = "token-123"
        self.repo.pdm.session_obtained_at = datetime.now(UTC)

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(enabled=True)
        )

        assert result.session.active is True
        assert self.repo.pdm.session_token == "token-123"

    # ── requeuing skipped files on a settings-scope change ────────────

    async def test_changed_variable_map_requeues_skipped_files(self):
        self.repo.pdm.vault_id = "V1"
        self.snapshots.reset_count = 3

        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                        "article_name": "Glados.ArticleName",
                    },
                )
            ),
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]
        assert result.made_item_variable_map["article_name"] == "Glados.ArticleName"

    async def test_changed_watched_folders_requeues_skipped_files(self):
        self.repo.pdm.vault_id = "V1"
        self.snapshots.reset_count = 1

        await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Made-Parts", kind="made", recursive=True, enabled=True
                    )
                ]
            ),
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_changed_made_released_state_ids_requeues_skipped_files(self):
        self.repo.pdm.vault_id = "V1"
        self.snapshots.reset_count = 1

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(made_released_state_ids=[99])
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_changed_made_obsolete_state_ids_requeues_skipped_files(self):
        self.repo.pdm.vault_id = "V1"
        self.repo.pdm.made_released_state_ids = [5]
        self.snapshots.reset_count = 1

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(made_obsolete_state_ids=[99])
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_changed_bought_released_state_ids_requeues_skipped_files(self):
        # sync_scope_differs tracks all four per-kind lists, not just
        # made's, so a bought-only change must requeue too.
        self.repo.pdm.vault_id = "V1"
        self.snapshots.reset_count = 1

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(bought_released_state_ids=[99])
        )

        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_unrelated_field_change_does_not_requeue(self):
        self.repo.pdm.vault_id = "V1"

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(cad_items_read_only=False)
        )

        assert self.snapshots.reset_skipped_to_pending_calls == []

    async def test_empty_vault_id_does_not_requeue_even_when_scope_changes(self):
        assert self.repo.pdm.vault_id == ""

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(made_released_state_ids=[99])
        )

        assert self.snapshots.reset_skipped_to_pending_calls == []

    async def test_no_snapshot_repo_injected_does_not_requeue(self):
        """The default-None snapshot_repo keeps older construction sites
        (no snapshot repo available) working without touching this
        behaviour at all."""
        repo = FakeAdminSettingsRepository()
        repo.pdm.vault_id = "V1"
        use_case = UpdatePdmSettings(repo, uow=FakeUnitOfWork())

        result = await use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(made_released_state_ids=[99])
        )

        assert result.made_released_state_ids == [99]

    async def test_requeue_count_is_mentioned_in_the_audit_summary(self):
        self.repo.pdm.vault_id = "V1"
        self.snapshots.reset_count = 4

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(made_released_state_ids=[99])
        )

        summary = self.repo.audit_log[-1].summary
        assert "4 skipped files queued for re-evaluation" in summary

    # ── snapshots left outside every watched folder ──────────────────

    def _scope_change_rig(
        self, rows: list[PdmFileSnapshot]
    ) -> tuple[UpdatePdmSettings, FakeMadeItemRepository, FakeBoughtItemRepository]:
        self.repo.pdm.vault_id = "V1"
        self.snapshots.rows = rows
        made_items = FakeMadeItemRepository([make_made_item(1, part_number="I-1")])
        bought_items = FakeBoughtItemRepository([make_bought_item(2, part_number="I-2")])
        use_case = UpdatePdmSettings(
            self.repo,
            snapshot_repo=self.snapshots,
            uow=FakeUnitOfWork(),
            made_item_repo=made_items,
            bought_item_repo=bought_items,
        )
        return use_case, made_items, bought_items

    @staticmethod
    def _watch(path: str, *, enabled: bool = True) -> UpdatePdmSettingsCommand:
        return UpdatePdmSettingsCommand(
            watched_folders=[
                PdmWatchedFolderCommand(path=path, kind="by_kind", recursive=True, enabled=enabled)
            ]
        )

    async def test_scope_change_marks_snapshots_outside_every_folder_missing(self):
        old = _snapshot(
            file_id=1, path="\\Old\\Parts\\I-1.SLDPRT", sync_state=PdmFileSyncState.PENDING
        )
        kept = _snapshot(file_id=2, path="\\New\\I-3.SLDPRT", sync_state=PdmFileSyncState.SKIPPED)
        use_case, _, _ = self._scope_change_rig([old, kept])

        await use_case.execute(actor=self.actor, cmd=self._watch("New"))

        assert self.snapshots.upserted == [old]
        assert old.sync_state == "missing"
        assert old.last_error == "file is no longer under a watched folder"
        # The in-scope skipped row is left to the requeue, as before.
        assert kept.sync_state == "skipped"
        assert self.snapshots.reset_skipped_to_pending_calls == ["V1"]

    async def test_out_of_scope_linked_items_are_marked_missing(self):
        made = _snapshot(file_id=1, path="\\Old\\I-1.SLDPRT", kind="made", item_id=1)
        bought = _snapshot(file_id=2, path="\\Old\\I-2.SLDPRT", kind="bought", item_id=2)
        use_case, made_items, bought_items = self._scope_change_rig([made, bought])

        await use_case.execute(actor=self.actor, cmd=self._watch("New"))

        assert (await made_items.get_by_id(1)).pdm_sync_state == "missing"
        assert (await bought_items.get_by_id(2)).pdm_sync_state == "missing"

    async def test_out_of_scope_document_snapshot_leaves_its_item_alone(self):
        document = _snapshot(file_id=1, path="\\Old\\I-1.pdf", kind="document", item_id=1)
        use_case, made_items, _ = self._scope_change_rig([document])

        await use_case.execute(actor=self.actor, cmd=self._watch("New"))

        assert document.sync_state == "missing"
        assert (await made_items.get_by_id(1)).pdm_sync_state is None

    async def test_disabled_folder_counts_as_out_of_scope(self):
        row = _snapshot(file_id=1, path="\\New\\I-1.SLDPRT")
        use_case, _, _ = self._scope_change_rig([row])

        await use_case.execute(actor=self.actor, cmd=self._watch("New", enabled=False))

        assert row.sync_state == "missing"

    async def test_already_missing_snapshot_is_not_rewritten(self):
        row = _snapshot(
            file_id=1,
            path="\\Old\\I-1.SLDPRT",
            sync_state=PdmFileSyncState.MISSING,
            last_error="gone",
        )
        use_case, _, _ = self._scope_change_rig([row])

        await use_case.execute(actor=self.actor, cmd=self._watch("New"))

        assert self.snapshots.upserted == []
        assert row.last_error == "gone"

    async def test_unrelated_change_does_not_mark_out_of_scope_snapshots(self):
        row = _snapshot(file_id=1, path="\\Old\\I-1.SLDPRT")
        use_case, _, _ = self._scope_change_rig([row])

        await use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(cad_items_read_only=False)
        )

        assert row.sync_state == "skipped"

    async def test_out_of_scope_count_is_mentioned_in_the_audit_summary(self):
        row = _snapshot(file_id=1, path="\\Old\\I-1.SLDPRT")
        use_case, _, _ = self._scope_change_rig([row])

        await use_case.execute(actor=self.actor, cmd=self._watch("New"))

        summary = self.repo.audit_log[-1].summary
        assert "1 files outside every watched folder marked missing" in summary

    async def test_no_requeue_omits_the_count_from_the_audit_summary(self):
        self.repo.pdm.vault_id = "V1"

        await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(cad_items_read_only=False)
        )

        summary = self.repo.audit_log[-1].summary
        assert "queued for re-evaluation" not in summary

    # ── write-back to PDM ──────────────────────────────────────────────

    _WRITE_BACK_FIELDS: ClassVar[dict[str, str]] = {
        "glados_ids": "Glados.Ids",
        "newest_revision_sync_state": "Glados.NewestRevisionSyncState",
        "newest_revision_synced_at": "Glados.NewestRevisionSyncedAt",
    }

    async def test_writeback_enabled_requires_all_three_variables_mapped_in_both_maps(self):
        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    writeback_enabled=True,
                    made_item_variable_map=_complete(
                        "made",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                        },
                    ),
                    bought_item_variable_map=_complete(
                        "bought",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                        },
                    ),
                ),
            )

    async def test_writeback_enabled_requires_the_same_variable_name_in_both_maps(self):
        made_map = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            **self._WRITE_BACK_FIELDS,
        }
        bought_map = dict(made_map)
        bought_map["glados_ids"] = "Other.Ids"

        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    writeback_enabled=True,
                    made_item_variable_map=_complete("made", made_map),
                    bought_item_variable_map=_complete("bought", bought_map),
                ),
            )

    async def test_writeback_enabled_accepted_when_all_three_agree(self):
        made_map = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            **self._WRITE_BACK_FIELDS,
        }
        bought_map = dict(made_map)

        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                writeback_enabled=True,
                made_item_variable_map=_complete("made", made_map),
                bought_item_variable_map=_complete("bought", bought_map),
            ),
        )

        assert result.writeback_enabled is True

    async def test_writeback_disabled_does_not_require_the_variables_mapped(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                writeback_enabled=False,
                made_item_variable_map=_complete(
                    "made",
                    {
                        "part_number": "PDM.PartNumber",
                        "revision": "PDM.Revision",
                    },
                ),
            ),
        )

        assert result.writeback_enabled is False

    async def test_writeback_enabled_left_as_stored_when_not_sent(self):
        self.repo.pdm.writeback_enabled = True
        self.repo.pdm.made_item_variable_map = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            **self._WRITE_BACK_FIELDS,
        }
        self.repo.pdm.bought_item_variable_map = dict(self.repo.pdm.made_item_variable_map)

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(cad_items_read_only=False)
        )

        assert result.writeback_enabled is True

    async def test_writeback_enabled_checked_against_the_resolved_maps_on_a_partial_update(self):
        """Only made_item_variable_map is sent this time; the stored
        bought map (still missing the three fields) is what the check
        resolves against. A partial update cannot bypass the rule by
        omitting the map that would fail it."""
        self.repo.pdm.made_item_variable_map = {
            "part_number": "PDM.PartNumber",
            "revision": "PDM.Revision",
            **self._WRITE_BACK_FIELDS,
        }

        with pytest.raises(PdmSettingsInvalidError):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdatePdmSettingsCommand(writeback_enabled=True)
            )

    # ── documents, thumbnails, file type rule (docs/reference/pdm-documents.md) ──

    async def test_extensions_are_lowercased_and_dot_stripped(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_item_extensions=[".SLDPRT"], bought_item_extensions=["SldAsm"]
            ),
        )
        assert result.made_item_extensions == ["sldprt"]
        assert result.bought_item_extensions == ["sldasm"]

    def test_empty_extensions_list_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(made_item_extensions=[])
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(bought_item_extensions=[])

    def test_non_alphanumeric_extension_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(made_item_extensions=["sld.prt"])
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(made_item_extensions=[""])

    async def test_document_categories_are_normalised_and_stored(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(document_categories={".PDF": "drawing", "STP": "step"}),
        )
        assert result.document_categories == {"pdf": "drawing", "stp": "step"}

    def test_document_categories_accept_image_and_thumbnail(self):
        cmd = UpdatePdmSettingsCommand(document_categories={"jpg": "image_and_thumbnail"})
        assert cmd.document_categories == {"jpg": "image_and_thumbnail"}

    def test_document_categories_unknown_category_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(document_categories={"pdf": "not-a-real-category"})

    def test_document_categories_invalid_extension_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(document_categories={"p df": "drawing"})

    async def test_document_excluded_kinds_are_normalised_and_stored(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                document_excluded_kinds={".STEP": ["bought", "bought"], "pdf": []}
            ),
        )
        assert result.document_excluded_kinds == {"step": ["bought"]}

    async def test_document_excluded_kinds_drop_extensions_without_a_category(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                document_categories={"pdf": "drawing"},
                document_excluded_kinds={"pdf": ["made"], "step": ["bought"]},
            ),
        )
        assert result.document_excluded_kinds == {"pdf": ["made"]}

    def test_document_excluded_kinds_unknown_kind_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(document_excluded_kinds={"step": ["source"]})

    def test_document_excluded_kinds_invalid_extension_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(document_excluded_kinds={"st ep": ["bought"]})

    async def test_thumbnails_enabled_is_merged(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(thumbnails_enabled=True)
        )
        assert result.thumbnails_enabled is True

    async def test_stuck_after_days_is_merged(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(stuck_after_days=30)
        )
        assert result.stuck_after_days == 30

    def test_stuck_after_days_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(stuck_after_days=0)
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(stuck_after_days=366)

    async def test_stuck_after_days_unset_preserves_current(self):
        result = await self.use_case.execute(actor=self.actor, cmd=UpdatePdmSettingsCommand())
        assert result.stuck_after_days == self.repo.pdm.stuck_after_days

    async def test_reconcile_requested_deep_is_never_settable_through_update(self):
        """RequestPdmReconciliation sets this, a settings PUT must never
        clobber a request already queued, see update_pdm_settings.py's
        module docstring."""
        self.repo.pdm.reconcile_requested_deep = True
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdatePdmSettingsCommand(thumbnails_enabled=True)
        )
        assert result is not None
        assert self.repo.pdm.reconcile_requested_deep is True

    def test_documents_folder_without_match_by_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Documents", kind="documents", recursive=True, enabled=True
                    )
                ]
            )

    def test_documents_folder_filename_without_pattern_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Documents",
                        kind="documents",
                        recursive=True,
                        enabled=True,
                        match_by="filename",
                    )
                ]
            )

    def test_documents_folder_filename_pattern_missing_named_groups_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Documents",
                        kind="documents",
                        recursive=True,
                        enabled=True,
                        match_by="filename",
                        filename_pattern=r"^(?P<part_number>[A-Z0-9-]+)\.pdf$",
                    )
                ]
            )

    def test_documents_folder_filename_pattern_non_compiling_is_rejected(self):
        with pytest.raises(ValueError):
            UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Documents",
                        kind="documents",
                        recursive=True,
                        enabled=True,
                        match_by="filename",
                        filename_pattern="(unclosed",
                    )
                ]
            )

    async def test_documents_folder_with_valid_filename_match_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Documents",
                        kind="documents",
                        recursive=True,
                        enabled=True,
                        match_by="filename",
                        filename_pattern=(
                            r"^(?P<part_number>[A-Z0-9-]+)_(?P<revision>[A-Z0-9]+)\.pdf$"
                        ),
                    )
                ]
            ),
        )
        assert result.watched_folders[0].match_by == "filename"
        assert result.watched_folders[0].filename_pattern == (
            r"^(?P<part_number>[A-Z0-9-]+)_(?P<revision>[A-Z0-9]+)\.pdf$"
        )

    async def test_documents_folder_with_datacard_match_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                watched_folders=[
                    PdmWatchedFolderCommand(
                        path="Documents",
                        kind="documents",
                        recursive=True,
                        enabled=True,
                        match_by="datacard",
                    )
                ]
            ),
        )
        assert result.watched_folders[0].match_by == "datacard"
        assert result.watched_folders[0].filename_pattern is None

    async def test_required_fields_absent_keeps_stored_selection(self):
        self.repo.pdm.required_fields = {"made": ["material"], "bought": []}
        result = await self.use_case.execute(actor=self.actor, cmd=UpdatePdmSettingsCommand())
        assert result.required_fields == {"made": ["material"], "bought": []}

    async def test_required_fields_replaces_the_stored_selection(self):
        self.repo.pdm.required_fields = {"made": ["material"], "bought": []}
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                required_fields={"made": ["fabrication_step"], "bought": []}
            ),
        )
        assert result.required_fields == {"made": ["fabrication_step"], "bought": []}

    async def test_required_fields_drops_a_locked_name_silently(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                required_fields={"made": ["part_number", "material"], "bought": []}
            ),
        )
        assert result.required_fields == {"made": ["material"], "bought": []}

    async def test_required_fields_drops_a_duplicate_silently(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                required_fields={"made": ["material", "material"], "bought": []}
            ),
        )
        assert result.required_fields == {"made": ["material"], "bought": []}

    async def test_required_fields_accepts_the_fabrication_step_pseudo_rule(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                required_fields={"made": ["fabrication_step"], "bought": []}
            ),
        )
        assert result.required_fields == {"made": ["fabrication_step"], "bought": []}

    async def test_required_fields_rejects_an_unknown_name(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    required_fields={"made": ["not_a_field"], "bought": []}
                ),
            )

    async def test_required_fields_rejects_a_bought_only_field_for_made(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    required_fields={"made": ["order_code_1"], "bought": []}
                ),
            )

    # ── feature-tree templates ─────────────────────────────────────────

    async def test_feature_tree_templates_absent_keep_the_stored_defaults(self):
        result = await self.use_case.execute(actor=self.actor, cmd=UpdatePdmSettingsCommand())
        assert result.made_feature_tree_template == (
            '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
        )
        assert result.bought_feature_tree_template == (
            '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
        )

    async def test_feature_tree_templates_are_stored_verbatim(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(
                made_feature_tree_template='$PRP:"Glados.ArticleName" {draft}',
                bought_feature_tree_template='$PRP:"SW-File Name" - $PRP:"Description"',
            ),
        )
        assert result.made_feature_tree_template == '$PRP:"Glados.ArticleName" {draft}'
        assert result.bought_feature_tree_template == '$PRP:"SW-File Name" - $PRP:"Description"'

    async def test_made_feature_tree_template_with_a_line_break_rejected(self):
        with pytest.raises(PdmSettingsInvalidError, match="single line"):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    made_feature_tree_template='$PRP:"PDM.PartNumber"\n$PRP:"PDM.Revision"'
                ),
            )

    async def test_feature_tree_template_linking_to_its_new_mapping_rejected(self):
        # Checked against the variable map of the same request, not the stored one.
        with pytest.raises(PdmSettingsInvalidError, match="its own property"):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdatePdmSettingsCommand(
                    bought_item_variable_map=_complete(
                        "bought",
                        {
                            "part_number": "PDM.PartNumber",
                            "revision": "PDM.Revision",
                            "feature_tree_representation": "Custom.Tree",
                        },
                    ),
                    bought_feature_tree_template='$PRP:"Custom.Tree"',
                ),
            )

    async def test_feature_tree_template_left_as_stored_when_the_other_kind_is_updated(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdatePdmSettingsCommand(made_feature_tree_template='$PRP:"Glados.ArticleName"'),
        )
        assert result.bought_feature_tree_template == (
            '$PRP:"Glados.ArticleName" - $PRP:"Glados.OrderCode1" - $PRP:"Glados.ManufacturerName"'
        )
