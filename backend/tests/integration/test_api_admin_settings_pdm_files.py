"""
The /admin/settings/pdm/files surface end to end: the paged pending list
(filters, paging, the parked_payload -> has_parked_payload collapse), the
retry action (state reset, the PdmFileChangeRequested event on the
transactional bus, the audit entry, 404 on an unknown id), the dismiss
action (skip + drop the parked payload, audit entry, 404), and permission
checks. Snapshots are seeded directly through
SqlAlchemyPdmFileSnapshotRepository, no PDM Web API call is ever made.
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
from src.modules.external_data.domain.events.pdm_events import PdmFileChangeRequested
from src.modules.external_data.domain.value_objects.pdm_file_sync_state import PdmFileSyncState
from src.modules.platform.domain.value_objects.permission import Permission
from src.read.ports.outbound.repositories.admin_settings_repository import (
    AdminSettingsAuditFilterDto,
)

BASE = "/api/v1/web/admin/settings/pdm/files"

_NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def _snapshot(
    *,
    vault_id: str = "V1",
    file_id: int,
    kind: str = "made",
    name: str = "Bracket.SLDPRT",
    path: str = "\\Made-Parts\\Bracket.SLDPRT",
    sync_state: PdmFileSyncState = PdmFileSyncState.PENDING,
    part_number: str | None = None,
    last_error: str | None = None,
    parked_payload: dict[str, str] | None = None,
) -> PdmFileSnapshot:
    return PdmFileSnapshot(
        id=0,
        vault_id=vault_id,
        file_id=file_id,
        kind=kind,
        name=name,
        path=path,
        parent_folder_id=1,
        version=1,
        state_id=1,
        state="Released",
        modified_at=None,
        first_seen_at=_NOW,
        last_seen_at=_NOW,
        last_ingested_version=None,
        sync_state=sync_state,
        last_error=last_error,
        part_number=part_number,
        revision=None,
        item_id=None,
        parked_payload=parked_payload,
    )


async def _seed_pdm_vault_name(db, vault_name: str = "MyVault") -> None:
    """RetryPdmFile reads settings.vault_name for the outgoing
    PdmFileChangeRequested event; seed it on top of the autouse bare row
    the same way test_api_admin_settings_pdm.py's seeded_pdm fixture does."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(
        AdminPdmSettings(
            id=1,
            made_item_variable_map=current.made_item_variable_map,
            bought_item_variable_map=current.bought_item_variable_map,
            enabled=current.enabled,
            base_url=current.base_url,
            vault_name=vault_name,
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
            vault_id=current.vault_id,
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


# ── Access control ────────────────────────────────────────────────────


class TestAccessControl:
    async def test_list_requires_authentication(self, client):
        assert (await client.get(BASE)).status_code == 401

    async def test_list_requires_read_settings(self, auth_client):
        assert (await (await auth_client(permissions=[])).get(BASE)).status_code == 403

    async def test_retry_requires_write_settings(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(_snapshot(file_id=1))
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.post(f"{BASE}/{saved.id}/retry")
        assert resp.status_code == 403

    async def test_dismiss_requires_write_settings(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(_snapshot(file_id=1))
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.post(f"{BASE}/{saved.id}/dismiss")
        assert resp.status_code == 403


# ── List / filters / paging ──────────────────────────────────────────


class TestListPdmFiles:
    async def test_lists_and_hides_parked_payload(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(
            _snapshot(
                file_id=1,
                sync_state=PdmFileSyncState.CONFLICT,
                parked_payload={"PDM.PartNumber": "PN-1"},
            )
        )
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE)).json()

        assert body["total"] == 1
        row = body["items"][0]
        assert row["id"] == saved.id
        assert row["file_id"] == 1
        assert row["has_parked_payload"] is True
        assert "parked_payload" not in row

    async def test_filters_by_sync_state(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.save(_snapshot(file_id=1, sync_state=PdmFileSyncState.PENDING))
        await db.commit()
        await repo.save(_snapshot(file_id=2, sync_state=PdmFileSyncState.INGESTED))
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE, params={"sync_state": "ingested"})).json()

        assert body["total"] == 1
        assert body["items"][0]["file_id"] == 2

    async def test_filters_by_kind(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.save(_snapshot(file_id=1, kind="made"))
        await db.commit()
        await repo.save(_snapshot(file_id=2, kind="bought"))
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE, params={"kind": "bought"})).json()

        assert body["total"] == 1
        assert body["items"][0]["file_id"] == 2

    async def test_filters_by_kind_document(self, auth_client, db):
        """A `documents` watched folder's files snapshot kind "document"
        (singular, see PdmFileSnapshot's docstring); the pending list's
        kind filter accepts it like any other free-form value."""
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.save(_snapshot(file_id=1, kind="made"))
        await db.commit()
        await repo.save(
            _snapshot(
                file_id=2,
                kind="document",
                name="CAD-1_A.pdf",
                path="\\Exported Documents\\CAD-1_A.pdf",
            )
        )
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE, params={"kind": "document"})).json()

        assert body["total"] == 1
        assert body["items"][0]["file_id"] == 2
        assert body["items"][0]["kind"] == "document"

    async def test_search_matches_name_path_and_part_number(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        await repo.save(_snapshot(file_id=1, name="Housing.SLDPRT"))
        await db.commit()
        await repo.save(_snapshot(file_id=2, name="Widget.SLDPRT", part_number="PN-HOUSING-1"))
        await db.commit()
        await repo.save(
            _snapshot(file_id=3, name="Other.SLDPRT", path="\\Bought-Parts\\Other.SLDPRT")
        )
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE, params={"search": "Housing"})).json()

        assert {row["file_id"] for row in body["items"]} == {1, 2}

    async def test_paging(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        for i in range(1, 4):
            await repo.save(_snapshot(file_id=i))
            await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE, params={"skip": 1, "limit": 1})).json()

        assert body["total"] == 3
        assert body["skip"] == 1
        assert body["limit"] == 1
        assert len(body["items"]) == 1


# ── Retry ────────────────────────────────────────────────────────────


class TestRetryPdmFile:
    async def test_resets_state_publishes_event_and_audits(self, auth_client, db, published_events):
        await _seed_pdm_vault_name(db, vault_name="MyVault")
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(
            _snapshot(
                file_id=7,
                path="\\Made-Parts\\Bracket.SLDPRT",
                sync_state=PdmFileSyncState.ERROR,
                last_error="boom",
            )
        )
        await db.commit()
        client = await auth_client(permissions=Permission.ALL, username="retry-user")

        resp = await client.post(f"{BASE}/{saved.id}/retry")

        assert resp.status_code == 202
        assert resp.json() == {"accepted": True}

        refreshed = await repo.get_by_id(saved.id)
        assert refreshed is not None
        assert refreshed.sync_state == "pending"
        assert refreshed.last_error is None

        change_events = [e for e in published_events if isinstance(e, PdmFileChangeRequested)]
        assert len(change_events) == 1
        event = change_events[0]
        assert event.vault_name == "MyVault"
        assert event.file_id == 7
        assert event.path == "\\Made-Parts\\Bracket.SLDPRT"
        assert event.version is None

        settings_repo = SqlAlchemyAdminSettingsRepository(db)
        total, entries = await settings_repo.get_audit(
            AdminSettingsAuditFilterDto(settings_domain="pdm")
        )
        assert total >= 1
        assert entries[0].settings_domain == "pdm"

    async def test_unknown_snapshot_is_404(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.post(f"{BASE}/999999/retry")
        assert resp.status_code == 404


# ── Dismiss ──────────────────────────────────────────────────────────


class TestDismissPdmFile:
    async def test_skips_and_drops_parked_payload(self, auth_client, db):
        repo = SqlAlchemyPdmFileSnapshotRepository(db)
        saved = await repo.save(
            _snapshot(
                file_id=8,
                sync_state=PdmFileSyncState.CONFLICT,
                parked_payload={"PDM.PartNumber": "PN-1"},
            )
        )
        await db.commit()
        client = await auth_client(permissions=Permission.ALL, username="dismisser")

        resp = await client.post(f"{BASE}/{saved.id}/dismiss")

        assert resp.status_code == 200
        body = resp.json()
        assert body["sync_state"] == "skipped"
        assert body["last_error"] == "dismissed by dismisser"
        assert body["has_parked_payload"] is False
        assert "parked_payload" not in body

        refreshed = await repo.get_by_id(saved.id)
        assert refreshed is not None
        assert refreshed.parked_payload is None
        assert refreshed.sync_state == "skipped"

    async def test_unknown_snapshot_is_404(self, auth_client):
        client = await auth_client(permissions=Permission.ALL)
        resp = await client.post(f"{BASE}/999999/dismiss")
        assert resp.status_code == 404
