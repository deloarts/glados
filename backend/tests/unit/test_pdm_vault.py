"""
The vault and file helpers the PDM poller, refresh, validation, write-back
and document sync share.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

from src.modules.external_data.application.services.pdm_vault import fetch_vault_id
from src.modules.external_data.application.services.pdm_vault import file_extension
from src.modules.external_data.application.services.pdm_vault import hold_file
from src.modules.external_data.application.services.pdm_vault import resolve_and_store_vault_id
from src.modules.external_data.application.services.pdm_vault import sync_run_entry
from src.modules.external_data.application.services.pdm_vault import vault_name_matches
from tests.unit.fakes import FakeUnitOfWork


class _Gateway:
    def __init__(self) -> None:
        self.calls = 0

    async def vault_info(self, token: str) -> Any:
        self.calls += 1
        return SimpleNamespace(vault_id="vault-from-api")


class _Session:
    def __init__(self, gateway: _Gateway) -> None:
        self._gateway = gateway

    async def call(self, fn: Any) -> Any:
        return await fn(self._gateway, "token")


class _AdminSettings:
    def __init__(self) -> None:
        self.saved: list[str] = []

    async def save_pdm_vault_id(self, vault_id: str) -> None:
        self.saved.append(vault_id)


class _Lock:
    def __init__(self) -> None:
        self.held: list[int] = []

    def hold(self, file_id: int) -> Any:
        @asynccontextmanager
        async def _held() -> AsyncIterator[None]:
            self.held.append(file_id)
            yield

        return _held()


async def test_pdm_vault_fetches_the_vault_id_from_the_web_api() -> None:
    assert await fetch_vault_id(_Session(_Gateway())) == "vault-from-api"  # type: ignore[arg-type]


async def test_pdm_vault_stores_and_commits_a_vault_id_fetched_for_the_first_time() -> None:
    gateway, repo, uow = _Gateway(), _AdminSettings(), FakeUnitOfWork()
    settings: Any = SimpleNamespace(vault_id=None)

    vault_id = await resolve_and_store_vault_id(settings, _Session(gateway), repo, uow)  # type: ignore[arg-type]

    assert vault_id == "vault-from-api"
    assert repo.saved == ["vault-from-api"]
    assert uow.commits == 1


async def test_pdm_vault_reuses_a_stored_vault_id_without_calling_pdm() -> None:
    gateway, repo, uow = _Gateway(), _AdminSettings(), FakeUnitOfWork()
    settings: Any = SimpleNamespace(vault_id="stored")

    vault_id = await resolve_and_store_vault_id(settings, _Session(gateway), repo, uow)  # type: ignore[arg-type]

    assert (vault_id, gateway.calls, repo.saved, uow.commits) == ("stored", 0, [], 0)


def test_pdm_vault_names_match_ignoring_case_and_surrounding_whitespace() -> None:
    assert vault_name_matches("  Glados ", "glados")
    assert not vault_name_matches("Glados2", "glados")


def test_pdm_vault_file_extension_is_lower_case_without_the_dot() -> None:
    assert file_extension("Part.SLDPRT") == "sldprt"
    assert file_extension("archive.tar.GZ") == "gz"
    assert file_extension("README") == ""


async def test_pdm_vault_holds_the_file_lock_or_nothing_without_one() -> None:
    lock = _Lock()
    async with hold_file(lock, 42):  # type: ignore[arg-type]
        pass
    async with hold_file(None, 43):
        pass
    assert lock.held == [42]


def test_pdm_vault_sync_run_entry_describes_the_file() -> None:
    obj: Any = SimpleNamespace(id=7, name="a.sldprt", path="\\Parts\\a.sldprt")

    entry = sync_run_entry(3, "V1", obj, "made", "ingested", 11, "ok")

    assert (entry.id, entry.run_id, entry.vault_id, entry.file_id) == (0, 3, "V1", 7)
    assert (entry.name, entry.path, entry.kind) == ("a.sldprt", "\\Parts\\a.sldprt", "made")
    assert (entry.action, entry.item_id, entry.message) == ("ingested", 11, "ok")
    assert entry.created_at.tzinfo is not None
