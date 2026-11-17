"""
Proves that the PDM writes on the admin_pdm_settings row which no admin
request makes persist on their own: the session token PdmSessionService
stores or clears, the poll status a failed poll records, and the queued
reconciliation flag the poll gate clears. Each case runs on one session,
rolls it back, and reads the row from a fresh session, so a write that is
never committed fails here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any
from typing import cast

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.external_data.adapters.outbound.persistence.repositories.pdm_sync_run_repository import (
    SqlAlchemyPdmSyncRunRepository,
)
from src.modules.external_data.application.services.pdm_session import PdmSessionService
from src.modules.external_data.application.use_cases.pdm.poll_pdm_vault import PollPdmVault
from src.modules.external_data.application.use_cases.pdm.run_pdm_poll_if_due import RunPdmPollIfDue
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.errors import PdmAuthenticationFailedError
from src.modules.external_data.domain.value_objects.pdm_sync_trigger import PdmSyncTrigger
from src.modules.external_data.ports.outbound.pdm_gateway_port import PdmAuthResult
from src.modules.platform.adapters.outbound.persistence.session import SessionLocal
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork


async def _stored_pdm() -> AdminPdmSettings:
    async with SessionLocal() as fresh:
        return await SqlAlchemyAdminSettingsRepository(fresh).get_pdm()


@pytest.fixture
async def configured(db) -> None:
    """A switched-on, fully configured connection with no stored token."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    current = await repo.get_pdm()
    await repo.save_pdm(
        replace(
            current,
            enabled=True,
            base_url="http://pdm.example.local:65453",
            vault_name="MainVault",
            username="svc-glados",
            password="s3cret",
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
        )
    )
    await db.commit()


class _Gateway:
    def __init__(self, *, reject: bool = False) -> None:
        self._reject = reject

    async def authenticate(self, username: str, password: str) -> PdmAuthResult:
        if self._reject:
            raise PdmAuthenticationFailedError("rejected")
        return PdmAuthResult(token="fresh-token", user_id=7)


def _session_service(db: Any, gateway: _Gateway) -> PdmSessionService:
    return PdmSessionService(
        repo=SqlAlchemyAdminSettingsRepository(db),
        gateway_factory=lambda connection: cast(Any, gateway),
        uow=SqlAlchemyUnitOfWork(db),
    )


async def test_a_fresh_session_token_is_committed(db, configured) -> None:
    async def fn(gateway: Any, token: str) -> str:
        return token

    assert await _session_service(db, _Gateway()).call(fn) == "fresh-token"
    await db.rollback()

    stored = await _stored_pdm()
    assert stored.session_token == "fresh-token"
    assert stored.session_user_id == 7


async def test_a_cleared_session_token_is_committed(db, configured) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_pdm_session(token="old-token", user_id=3, obtained_at=None)
    await db.commit()

    async def fn(gateway: Any, token: str) -> str:
        return token

    with pytest.raises(PdmAuthenticationFailedError):
        await _session_service(db, _Gateway(reject=True)).call(fn)
    await db.rollback()

    assert (await _stored_pdm()).session_token is None


class _UnreachableVault(SqlAlchemyAdminSettingsRepository):
    async def get_pdm(self) -> AdminPdmSettings:
        raise RuntimeError("vault unreachable")


def _unused() -> Any:
    return cast(Any, None)


async def test_a_failed_poll_commits_its_poll_status(db) -> None:
    poll = PollPdmVault(
        session=_unused(),
        admin_settings_repo=_UnreachableVault(db),
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
        await poll.execute(PdmSyncTrigger.SCHEDULED)
    await db.rollback()

    stored = await _stored_pdm()
    assert stored.last_poll_error == "vault unreachable"
    assert stored.last_poll_at is not None


class _FreeLock:
    @asynccontextmanager
    async def lock(self) -> AsyncIterator[bool]:
        yield True


class _Reconcile:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def execute(self, *, deep: bool) -> None:
        self.calls.append(deep)


class _Poll:
    async def execute(self, *, trigger: PdmSyncTrigger) -> None:
        return None


async def test_the_poll_gate_commits_clearing_a_queued_reconciliation(db, configured) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_pdm_reconcile_requested(True)
    await db.commit()
    reconcile = _Reconcile()

    await RunPdmPollIfDue(
        admin_settings_repo=SqlAlchemyAdminSettingsRepository(db),
        lock=_FreeLock(),
        poll=cast(Any, _Poll()),
        reconcile=cast(Any, reconcile),
        run_repo=SqlAlchemyPdmSyncRunRepository(db),
        uow=SqlAlchemyUnitOfWork(db),
    ).execute()
    await db.rollback()

    assert reconcile.calls == [True]
    assert (await _stored_pdm()).reconcile_requested_deep is None
