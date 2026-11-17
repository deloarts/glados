"""
The /admin/settings/pdm/runs surface end to end: the paged runs list
(newest-first, paging), the paged entries list for one run (action filter,
paging, 404 on an unknown run id), and permission checks. Runs/entries are
seeded directly through SqlAlchemyPdmSyncRunRepository, no PDM Web API call
is ever made.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from typing import cast

import pytest

from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollPdmVault
from src.modules.external_data.application.use_cases.pdm.reconcile_pdm_vault import (
    ReconcilePdmVault,
)
from src.modules.external_data.application.use_cases.pdm.refresh_pdm_file import RefreshPdmFile
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/pdm/runs"

_NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _run(
    *,
    started_at: datetime = _NOW,
    trigger: PdmSyncTrigger = PdmSyncTrigger.SCHEDULED,
    **overrides: object,
) -> PdmSyncRun:
    defaults: dict[str, object] = dict(
        id=0,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=5),
        trigger=trigger,
        files_seen=1,
        changed=1,
        ingested=1,
        skipped=0,
        conflicts=0,
        errors=0,
        missing=0,
        error=None,
        summary="1 files seen, 1 changed, 1 ingested, 0 skipped, 0 conflicts, 0 errors, 0 missing.",
        folders_walked=1,
    )
    defaults.update(overrides)
    return PdmSyncRun(**defaults)  # type: ignore[arg-type]


def _entry(
    *, run_id: int, file_id: int = 1, action: str = "created", **overrides: object
) -> PdmSyncRunEntry:
    defaults: dict[str, object] = dict(
        id=0,
        run_id=run_id,
        vault_id="V1",
        file_id=file_id,
        name="Bracket.SLDPRT",
        path="\\Made-Parts\\Bracket.SLDPRT",
        kind="made",
        action=action,
        item_id=None,
        message="ok",
        created_at=_NOW,
    )
    defaults.update(overrides)
    return PdmSyncRunEntry(**defaults)  # type: ignore[arg-type]


# ── Access control ────────────────────────────────────────────────────


class TestAccessControl:
    async def test_list_runs_requires_authentication(self, client):
        assert (await client.get(BASE)).status_code == 401

    async def test_list_runs_requires_read_settings(self, auth_client):
        assert (await (await auth_client(permissions=[])).get(BASE)).status_code == 403

    async def test_list_entries_requires_authentication(self, client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        assert (await client.get(f"{BASE}/{run.id}/entries")).status_code == 401

    async def test_list_entries_requires_read_settings(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        client = await auth_client(permissions=[])
        assert (await client.get(f"{BASE}/{run.id}/entries")).status_code == 403


# ── List runs ────────────────────────────────────────────────────────


class TestListPdmSyncRuns:
    async def test_lists_newest_first(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        older = await repo.start(_run(started_at=_NOW - timedelta(hours=1)))
        newer = await repo.start(_run(started_at=_NOW))
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE)).json()

        assert body["total"] == 2
        assert [row["id"] for row in body["items"]] == [newer.id, older.id]
        row = body["items"][0]
        assert row["trigger"] == "scheduled"
        assert row["files_seen"] == 1
        assert row["ingested"] == 1

    async def test_paging(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        for i in range(3):
            await repo.start(_run(started_at=_NOW + timedelta(minutes=i)))
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE, params={"skip": 1, "limit": 1})).json()

        assert body["total"] == 3
        assert body["skip"] == 1
        assert body["limit"] == 1
        assert len(body["items"]) == 1


# ── List run entries ───────────────────────────────────────────────────


class TestListPdmSyncRunEntries:
    async def test_lists_a_run_s_entries(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        await repo.add_entries(
            run.id,
            [
                _entry(run_id=run.id, file_id=1, action="created"),
                _entry(run_id=run.id, file_id=2, action="missing"),
            ],
        )
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(f"{BASE}/{run.id}/entries")).json()

        assert body["total"] == 2
        assert {row["file_id"] for row in body["items"]} == {1, 2}
        row = next(r for r in body["items"] if r["file_id"] == 1)
        assert row["run_id"] == run.id
        assert row["action"] == "created"
        assert row["vault_id"] == "V1"

    async def test_filters_by_action(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        await repo.add_entries(
            run.id,
            [
                _entry(run_id=run.id, file_id=1, action="created"),
                _entry(run_id=run.id, file_id=2, action="missing"),
                _entry(run_id=run.id, file_id=3, action="missing"),
            ],
        )
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(f"{BASE}/{run.id}/entries", params={"action": "missing"})).json()

        assert body["total"] == 2
        assert {row["file_id"] for row in body["items"]} == {2, 3}

    async def test_paging(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        run = await repo.start(_run())
        await repo.add_entries(run.id, [_entry(run_id=run.id, file_id=i) for i in range(1, 4)])
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(f"{BASE}/{run.id}/entries", params={"skip": 1, "limit": 1})).json()

        assert body["total"] == 3
        assert body["skip"] == 1
        assert body["limit"] == 1
        assert len(body["items"]) == 1

    async def test_unknown_run_is_404(self, auth_client):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        resp = await client.get(f"{BASE}/999999/entries")
        assert resp.status_code == 404


# ── Runs written by a use case ─────────────────────────────────────────


class _FailingSettings:
    """Admin settings stub whose PDM read fails, so a poll or a
    reconciliation takes its error path without ever contacting PDM."""

    async def get_pdm(self) -> None:
        raise RuntimeError("vault unreachable")

    async def save_pdm_poll_status(self, **_: object) -> None:
        pass


class _RefreshSettings:
    async def get_pdm(self) -> SimpleNamespace:
        return SimpleNamespace(enabled=True, is_configured=True, vault_name="V", vault_id="V1")


class _NothingInPdm:
    """Session stub whose every lookup finds nothing."""

    async def call(self, _fn: object) -> None:
        return None


class _NoSnapshots:
    async def get_by_file(self, _vault_id: str, _file_id: int) -> None:
        return None


def _unused() -> Any:
    return cast(Any, None)


async def _failed_poll(db: Any) -> None:
    use_case = PollPdmVault(
        session=_unused(),
        admin_settings_repo=cast(Any, _FailingSettings()),
        snapshot_repo=_unused(),
        made_item_repo=_unused(),
        bought_item_repo=_unused(),
        ingest=_unused(),
        write_back=_unused(),
        document_sync=_unused(),
        thumbnails=_unused(),
        run_repo=SqlAlchemyPdmSyncRunRepository(db),
        folder_poll_state_repo=_unused(),
        uow=SqlAlchemyUnitOfWork(db),
    )
    with pytest.raises(RuntimeError, match="vault unreachable"):
        await use_case.execute(PdmSyncTrigger.SCHEDULED)


async def _failed_reconciliation(db: Any) -> None:
    use_case = ReconcilePdmVault(
        session=_unused(),
        admin_settings_repo=cast(Any, _FailingSettings()),
        snapshot_repo=_unused(),
        made_item_repo=_unused(),
        bought_item_repo=_unused(),
        document_link_repo=_unused(),
        part_number_registry=_unused(),
        supplier_repo=_unused(),
        run_repo=SqlAlchemyPdmSyncRunRepository(db),
        finding_repo=_unused(),
        uow=SqlAlchemyUnitOfWork(db),
    )
    with pytest.raises(RuntimeError, match="vault unreachable"):
        await use_case.execute(deep=False)


async def _missing_file_refresh(db: Any) -> None:
    await RefreshPdmFile(
        session=cast(Any, _NothingInPdm()),
        admin_settings_repo=cast(Any, _RefreshSettings()),
        snapshot_repo=cast(Any, _NoSnapshots()),
        made_item_repo=_unused(),
        bought_item_repo=_unused(),
        ingest=_unused(),
        write_back=_unused(),
        document_sync=_unused(),
        thumbnails=_unused(),
        run_repo=SqlAlchemyPdmSyncRunRepository(db),
        folder_poll_state_repo=_unused(),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute(vault_name="V", file_id=7, path=None)


class TestRunsWrittenByAUseCase:
    """Each case starts and finishes a run through a use case and reads it
    back through the API, after rolling back the session the use case
    wrote on, so a run log that is never committed fails here."""

    @pytest.mark.parametrize(
        ("write", "trigger", "error"),
        [
            (_failed_poll, PdmSyncTrigger.SCHEDULED, "vault unreachable"),
            (_failed_reconciliation, PdmSyncTrigger.RECONCILIATION, "vault unreachable"),
            (_missing_file_refresh, PdmSyncTrigger.FILE_TRIGGER, None),
        ],
        ids=["poll", "reconciliation", "refresh"],
    )
    async def test_the_run_is_persisted(self, auth_client, db, write, trigger, error):
        await write(db)
        await db.rollback()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(BASE)).json()

        assert body["total"] == 1
        row = body["items"][0]
        assert row["trigger"] == trigger.value
        assert row["error"] == error
        assert row["finished_at"] is not None

    async def test_a_refresh_run_s_entry_is_persisted(self, auth_client, db):
        await _missing_file_refresh(db)
        await db.rollback()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        run_id = (await client.get(BASE)).json()["items"][0]["id"]

        body = (await client.get(f"{BASE}/{run_id}/entries")).json()

        assert [(e["file_id"], e["action"]) for e in body["items"]] == [(7, "missing")]


# ── Sync activity ────────────────────────────────────────────────────

ACTIVITY = "/api/v1/web/admin/settings/pdm/sync-activity"


class TestSyncActivity:
    async def test_requires_read_settings(self, auth_client):
        assert (await (await auth_client(permissions=[])).get(ACTIVITY)).status_code == 403

    async def test_running_poll_with_its_progress_and_the_newest_entries(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        now = datetime.now(UTC)
        run = await repo.start(_run(started_at=now, finished_at=None))
        run.phase = "ingesting"
        run.current_path = "\\Made-Parts"
        run.files_queued = 12
        run.files_processed = 5
        run.progress_at = now
        await repo.save_progress(run)
        await repo.add_entries(run.id, [_entry(run_id=run.id, file_id=i) for i in range(1, 13)])
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        body = (await client.get(ACTIVITY)).json()

        assert body["run"]["phase"] == "ingesting"
        assert body["run"]["current_path"] == "\\Made-Parts"
        assert (body["run"]["files_queued"], body["run"]["files_processed"]) == (12, 5)
        assert [e["file_id"] for e in body["recent_entries"]] == list(range(12, 2, -1))

    async def test_run_without_recent_progress_is_not_reported_as_running(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        long_ago = datetime.now(UTC) - timedelta(hours=2)
        await repo.start(_run(started_at=long_ago, finished_at=None, progress_at=long_ago))
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        assert (await client.get(ACTIVITY)).json()["run"] is None

    async def test_single_file_refreshes_are_not_a_running_poll(self, auth_client, db):
        repo = SqlAlchemyPdmSyncRunRepository(db)
        now = datetime.now(UTC)
        await repo.start(
            _run(started_at=now, finished_at=None, trigger=PdmSyncTrigger.FILE_TRIGGER)
        )
        await db.commit()
        client = await auth_client(permissions=[Permission.READ_SETTINGS])

        assert (await client.get(ACTIVITY)).json()["run"] is None
