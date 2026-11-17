"""
The PAT surface's file history read (POST /api/v1/pat/pdm/files/history)
end to end, signed in with a real token minted through CreatePat: 200 with
the requested files' sync log entries merged newest first, each with its
run's trigger, reason and requester, and nothing of other files or vaults;
an empty list before the vault id is known; 401 without a token, 403 for a
token without use:pdm_addin even when its owner holds it, 400 for the wrong
vault, 409 while the integration is off and 422 for an empty or oversized
file list or a limit out of range.
"""

import dataclasses
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRun
from src.modules.external_data.domain.entities.pdm_sync_run import PdmSyncRunEntry
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

_URL = "/api/v1/pat/pdm/files/history"
_NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


async def _seed_pdm_enabled(db: AsyncSession, vault_id: str = "V1") -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm(
        dataclasses.replace(
            await repo.get_pdm(),
            enabled=True,
            base_url="http://pdm-host:65453",
            vault_name="MyVault",
            username="svc-account",
            password="secret",
            vault_id=vault_id,
        )
    )
    await db.commit()


def _run(started_at: datetime, trigger: PdmSyncTrigger, **overrides: object) -> PdmSyncRun:
    fields: dict[str, object] = dict(
        id=0,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=2),
        trigger=trigger,
        files_seen=1,
        changed=1,
        ingested=1,
        skipped=0,
        conflicts=0,
        errors=0,
        missing=0,
        error=None,
        summary=None,
        folders_walked=0,
    )
    fields.update(overrides)
    return PdmSyncRun(**fields)  # type: ignore[arg-type]


def _entry(file_id: int, created_at: datetime, **overrides: object) -> PdmSyncRunEntry:
    fields: dict[str, object] = dict(
        id=0,
        run_id=0,
        vault_id="V1",
        file_id=file_id,
        name=f"Part{file_id}.SLDPRT",
        path=f"\\Made-Parts\\Part{file_id}.SLDPRT",
        kind="made",
        action="updated",
        item_id=42,
        message="updated",
        created_at=created_at,
    )
    fields.update(overrides)
    return PdmSyncRunEntry(**fields)  # type: ignore[arg-type]


async def _seed_history(db: AsyncSession) -> None:
    """A scheduled poll that touched files 1 and 3, a released file 2 by a
    state-change trigger five minutes later, and file 1 in another vault."""
    repo = SqlAlchemyPdmSyncRunRepository(db)
    poll = await repo.start(_run(_NOW, PdmSyncTrigger.SCHEDULED))
    await repo.add_entries(
        poll.id,
        [
            _entry(1, _NOW),
            _entry(3, _NOW + timedelta(seconds=1)),
            _entry(1, _NOW, vault_id="V2"),
        ],
    )
    trigger = await repo.start(
        _run(
            _NOW + timedelta(minutes=5),
            PdmSyncTrigger.FILE_TRIGGER,
            change_reason="state_change",
            change_state="Released",
            requested_by_name="Ada Lovelace",
        )
    )
    await repo.add_entries(
        trigger.id,
        [_entry(2, _NOW + timedelta(minutes=5), action="revised", message="revision B")],
    )
    await db.commit()


@pytest.fixture
async def pat_owner(create_user) -> User:
    """Holds WRITE_PAT (required to mint a token at all) and both PDM
    add-in permissions (a token's scopes are capped at its owner's own)."""
    return await create_user(
        username="pat-owner-pdm-history",
        email="pat-owner-pdm-history@example.com",
        permissions=[Permission.WRITE_PAT, Permission.USE_PDM_ADDIN],
    )


@pytest.fixture
def mint_pat(db: AsyncSession, pat_owner: User) -> Callable[[list[str]], Awaitable[str]]:
    async def _mint(permissions: list[str]) -> str:
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(
            actor=pat_owner,
            cmd=CreatePatCommand(name="PDM Addin", permissions=permissions),
        )
        return result.token

    return _mint


class TestHappyPath:
    async def test_merges_the_requested_files_newest_first_with_their_run(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        await _seed_history(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={"vault_name": "myvault", "file_ids": [1, 2]},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        entries = resp.json()["entries"]
        assert [(e["file_id"], e["action"]) for e in entries] == [(2, "revised"), (1, "updated")]
        newest = entries[0]
        assert newest["trigger"] == "file_trigger"
        assert newest["change_reason"] == "state_change"
        assert newest["change_state"] == "Released"
        assert newest["requested_by_name"] == "Ada Lovelace"
        assert newest["message"] == "revision B"
        assert newest["name"] == "Part2.SLDPRT"
        assert entries[1]["trigger"] == "scheduled"
        assert entries[1]["requested_by_name"] is None
        assert "item_id" not in newest

    async def test_limit_caps_the_merged_list(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        await _seed_history(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL,
            json={"vault_name": "MyVault", "file_ids": [1, 2, 3], "limit": 1},
            headers={"X-Api-Key": token},
        )

        assert resp.status_code == 200, resp.text
        assert [e["file_id"] for e in resp.json()["entries"]] == [2]

    async def test_no_resolved_vault_id_yet_is_an_empty_list(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db, vault_id="")
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL, json={"vault_name": "MyVault", "file_ids": [1]}, headers={"X-Api-Key": token}
        )

        assert resp.status_code == 200, resp.text
        assert resp.json() == {"entries": []}


class TestAuth:
    async def test_missing_token_is_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(_URL, json={"vault_name": "MyVault", "file_ids": [1]})

        assert resp.status_code == 401

    async def test_token_without_use_pdm_addin_is_403(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([])

        resp = await client.post(
            _URL, json={"vault_name": "MyVault", "file_ids": [1]}, headers={"X-Api-Key": token}
        )

        assert resp.status_code == 403


class TestRejections:
    async def test_wrong_vault_is_400(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL, json={"vault_name": "OtherVault", "file_ids": [1]}, headers={"X-Api-Key": token}
        )

        assert resp.status_code == 400

    async def test_unconfigured_integration_is_409(
        self,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
    ) -> None:
        # No _seed_pdm_enabled call: the autouse bare row is disabled.
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(
            _URL, json={"vault_name": "MyVault", "file_ids": [1]}, headers={"X-Api-Key": token}
        )

        assert resp.status_code == 409

    @pytest.mark.parametrize(
        "body",
        [
            {"vault_name": "MyVault", "file_ids": []},
            {"vault_name": "MyVault", "file_ids": list(range(1, 102))},
            {"vault_name": "MyVault", "file_ids": [1], "limit": 0},
            {"vault_name": "MyVault", "file_ids": [1], "limit": 201},
        ],
    )
    async def test_bad_file_list_or_limit_is_422(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        mint_pat: Callable[[list[str]], Awaitable[str]],
        body: dict[str, object],
    ) -> None:
        await _seed_pdm_enabled(db)
        token = await mint_pat([Permission.USE_PDM_ADDIN])

        resp = await client.post(_URL, json=body, headers={"X-Api-Key": token})

        assert resp.status_code == 422
