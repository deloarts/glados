"""
Localized names of the labeled catalogue entities end to end: the web
surface takes and returns language maps, needs a name in the tenant's
default language, rejects a name another live row holds in the same
language, searches every language and sorts in the user's language; the
pat surface answers with one string in the add-in language from the PDM
settings, falling back to the tenant's default language.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.adapters.outbound.persistence.repositories.pat_repository import (
    SqlAlchemyPatRepository,
)
from src.modules.platform.adapters.outbound.persistence.unit_of_work import SqlAlchemyUnitOfWork
from src.modules.platform.application.dto.pat_dto import CreatePatCommand
from src.modules.platform.application.use_cases.pat.create_pat import CreatePat
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission

WEB = "/api/v1/web/article-groups/"
PAT = "/api/v1/pat/article-groups/"


@pytest.fixture
async def writer(auth_client: Any) -> httpx.AsyncClient:
    client: httpx.AsyncClient = await auth_client(permissions=[Permission.WRITE_ARTICLE_GROUPS])
    return client


async def _create(client: httpx.AsyncClient, name: dict[str, str]) -> dict[str, Any]:
    resp = await client.post(WEB, json={"name": name, "description": {"enGB": "Hardware"}})
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


async def test_web_round_trip_keeps_every_language(writer: httpx.AsyncClient) -> None:
    created = await _create(writer, {"enGB": "Screws", "deAT": "Screws (deAT)"})
    assert created["name"] == {"enGB": "Screws", "deAT": "Screws (deAT)"}
    assert created["description"] == {"enGB": "Hardware"}

    resp = await writer.put(
        f"{WEB}{created['id']}", json={"name": {"enGB": "Bolts"}, "description": {}}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == {"enGB": "Bolts"}
    assert resp.json()["description"] == {}


async def test_a_name_needs_the_default_language(writer: httpx.AsyncClient) -> None:
    resp = await writer.post(WEB, json={"name": {"deAT": "Screws (deAT)"}})
    assert resp.status_code == 422, resp.text
    assert resp.json()["code"] == "LocalizedTextInvalidError"


async def test_a_name_held_in_the_same_language_is_rejected(writer: httpx.AsyncClient) -> None:
    await _create(writer, {"enGB": "Screws", "deAT": "Nuts (deAT)"})

    resp = await writer.post(WEB, json={"name": {"enGB": "Washers", "deAT": "nuts (deAT)"}})
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "LabelTranslationConflictError"

    resp = await writer.post(WEB, json={"name": {"enGB": "Nuts (deAT)"}})
    assert resp.status_code == 201, resp.text


async def test_search_matches_any_language(writer: httpx.AsyncClient) -> None:
    created = await _create(writer, {"enGB": "Screws", "deAT": "Fasteners (deAT)"})

    resp = await writer.get(WEB, params={"name": "fasteners"})
    assert resp.status_code == 200, resp.text
    assert [item["id"] for item in resp.json()["items"]] == [created["id"]]


async def test_sort_follows_the_users_language(db: AsyncSession, auth_client: Any) -> None:
    client: httpx.AsyncClient = await auth_client(permissions=[Permission.WRITE_ARTICLE_GROUPS])
    await db.execute(text("UPDATE user_table SET language = 'deAT' WHERE username = 'tester'"))
    await db.commit()
    await _create(client, {"enGB": "Alpha", "deAT": "Zulu"})
    await _create(client, {"enGB": "Zulu", "deAT": "Alpha"})

    resp = await client.get(WEB, params={"order_by": "name", "order_dir": "asc"})
    assert resp.status_code == 200, resp.text
    assert [item["name"]["deAT"] for item in resp.json()["items"]] == ["Alpha", "Zulu"]


@pytest.fixture
def mint_pat(db: AsyncSession, create_user: Any) -> Callable[[], Awaitable[str]]:
    async def _mint() -> str:
        owner: User = await create_user(
            username="label-pat-owner",
            email="label-pat-owner@example.com",
            permissions=[Permission.WRITE_PAT],
        )
        result = await CreatePat(
            SqlAlchemyPatRepository(db),
            settings_repo=SqlAlchemyAdminSettingsRepository(db),
            uow=SqlAlchemyUnitOfWork(db),
        ).execute(actor=owner, cmd=CreatePatCommand(name="labels", permissions=[]))
        return result.token

    return _mint


async def _set_addin_language(db: AsyncSession, language: str) -> None:
    repo = SqlAlchemyAdminSettingsRepository(db)
    pdm = await repo.get_pdm()
    pdm.addin_language = language
    await repo.save_pdm(pdm)
    await db.commit()


async def test_pat_answers_in_the_addin_language(
    db: AsyncSession,
    client: httpx.AsyncClient,
    writer: httpx.AsyncClient,
    mint_pat: Callable[[], Awaitable[str]],
) -> None:
    await _create(writer, {"enGB": "Screws", "deAT": "Screws (deAT)"})
    token = await mint_pat()

    resp = await client.get(PAT, headers={"X-Api-Key": token})
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["name"] == "Screws"

    await _set_addin_language(db, "deAT")
    resp = await client.get(PAT, headers={"X-Api-Key": token})
    assert resp.json()["items"][0]["name"] == "Screws (deAT)"
    assert resp.json()["items"][0]["description"] == "Hardware"
