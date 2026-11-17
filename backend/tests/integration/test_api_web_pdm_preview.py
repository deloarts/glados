"""
GET /api/v1/web/pdm/preview end to end: authentication, the `kind` query
param's validation, and the disabled/populated response shapes. Snapshot
rows are seeded directly through SqlAlchemyPdmFileSnapshotRepository, no
PDM Web API call is ever made.
"""

from datetime import UTC
from datetime import datetime

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_file_snapshot_repository import (
    SqlAlchemyPdmFileSnapshotRepository,
)
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState

BASE = "/api/v1/web/pdm/preview"

_NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def _snapshot(
    *,
    vault_id: str = "V1",
    file_id: int,
    kind: str = "made",
    part_number: str | None = "CAD-1",
    version: int = 3,
    sync_state: PdmFileSyncState = PdmFileSyncState.SKIPPED,
    item_id: int | None = None,
    article_name: str | None = "Bracket",
) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=0,
        vault_id=vault_id,
        file_id=file_id,
        kind=kind,
        name="Bracket.SLDPRT",
        path="\\Made-Parts\\Bracket.SLDPRT",
        parent_folder_id=1,
        version=version,
        state_id=1,
        state="Released",
        modified_at=_NOW,
        first_seen_at=_NOW,
        last_seen_at=_NOW,
        last_ingested_version=None,
        sync_state=sync_state,
        last_error=None,
        part_number=part_number,
        revision="A",
        item_id=item_id,
        parked_payload=None,
        article_name=article_name,
    )


async def _enable_pdm(db, *, vault_id: str = "V1") -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=current.made_item_variable_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=True,
            base_url=current.base_url,
            vault_name=current.vault_name,
            username=current.username,
            password=current.password,
            verify_certificate=current.verify_certificate,
            timeout_seconds=current.timeout_seconds,
            session_token=current.session_token,
            session_user_id=current.session_user_id,
            session_obtained_at=current.session_obtained_at,
            watched_folders=current.watched_folders,
            made_released_state_ids=current.made_released_state_ids,
            made_obsolete_state_ids=current.made_obsolete_state_ids,
            made_replaced_state_ids=current.made_obsolete_state_ids,
            bought_released_state_ids=current.bought_released_state_ids,
            bought_obsolete_state_ids=current.bought_obsolete_state_ids,
            bought_replaced_state_ids=current.bought_obsolete_state_ids,
            poll_interval_minutes=current.poll_interval_minutes,
            vault_id=vault_id,
            cad_items_read_only=current.cad_items_read_only,
            last_poll_at=current.last_poll_at,
            last_poll_error=current.last_poll_error,
            last_poll_summary=current.last_poll_summary,
            writeback_enabled=current.writeback_enabled,
            made_item_extensions=current.made_item_extensions,
            bought_item_extensions=current.bought_item_extensions,
            document_categories=current.document_categories,
            thumbnails_enabled=current.thumbnails_enabled,
            stuck_after_days=current.stuck_after_days,
            reconcile_requested_deep=current.reconcile_requested_deep,
            required_fields=current.required_fields,
        )
    )
    await db.commit()


class TestAccessControl:
    async def test_requires_authentication(self, client):
        assert (await client.get(BASE, params={"kind": "made"})).status_code == 401

    async def test_unknown_kind_is_422(self, auth_client):
        client = await auth_client(permissions=[])
        resp = await client.get(BASE, params={"kind": "assembled"})
        assert resp.status_code == 422

    async def test_missing_kind_is_422(self, auth_client):
        client = await auth_client(permissions=[])
        assert (await client.get(BASE)).status_code == 422

    async def test_no_permission_required_to_read(self, auth_client):
        """Mirrors GET /made-items and GET /bought-items: any authenticated
        active user can read, no specific permission is required."""
        client = await auth_client(permissions=[])
        resp = await client.get(BASE, params={"kind": "made"})
        assert resp.status_code == 200


class TestPreviewShape:
    async def test_disabled_integration_returns_empty_lists(self, auth_client):
        """The autouse seeded admin_pdm_settings row starts disabled with
        no vault id, so the preview reports `enabled: false` without
        touching the snapshot table at all."""
        client = await auth_client(permissions=[])
        body = (await client.get(BASE, params={"kind": "made"})).json()
        assert body == {"kind": "made", "enabled": False, "unlinked": [], "newer": []}

    async def test_unlinked_file_is_reported_with_article_name(self, auth_client, db):
        await _enable_pdm(db, vault_id="V1")
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=1, part_number="CAD-1", article_name="Bracket")])
        await db.commit()

        client = await auth_client(permissions=[])
        body = (await client.get(BASE, params={"kind": "made"})).json()

        assert body["enabled"] is True
        assert body["newer"] == []
        assert len(body["unlinked"]) == 1
        row = body["unlinked"][0]
        assert row["file_id"] == 1
        assert row["part_number"] == "CAD-1"
        assert row["article_name"] == "Bracket"
        assert row["version"] == 3

    async def test_other_kind_is_not_mixed_in(self, auth_client, db):
        await _enable_pdm(db, vault_id="V1")
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.upsert_many([_snapshot(file_id=2, kind="bought", part_number="CAD-2")])
        await db.commit()

        client = await auth_client(permissions=[])
        body = (await client.get(BASE, params={"kind": "made"})).json()

        assert body["unlinked"] == []
